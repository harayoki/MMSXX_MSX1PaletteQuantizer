#include "MSX1PQCore.h"

#include <algorithm>
#include <cmath>
#include <cctype>
#include <fstream>
#include <sstream>

namespace MSX1PQCore {
namespace {

inline float max3f(float a, float b, float c)
{
    float m = (a > b) ? a : b;
    return (m > c) ? m : c;
}

inline float min3f(float a, float b, float c)
{
    float m = (a < b) ? a : b;
    return (m < c) ? m : c;
}

// パレットのHSBを一度だけ計算してキャッシュ
bool  g_palette_hsb_initialized = false;
float g_palette_h[256];
float g_palette_s[256];
float g_palette_b[256];

inline float sample_lut_channel(const PreprocessLut& lut, int r, int g, int b, int channel)
{
    int size = lut.size;
    if (size <= 0) {
        return 0.0f;
    }

    if (r < 0) r = 0; else if (r >= size) r = size - 1;
    if (g < 0) g = 0; else if (g >= size) g = size - 1;
    if (b < 0) b = 0; else if (b >= size) b = size - 1;
    if (channel < 0) channel = 0; else if (channel > 2) channel = 2;

    std::size_t idx = static_cast<std::size_t>((r * size * size + g * size + b) * 3 + channel);
    if (idx >= lut.values.size()) {
        return 0.0f;
    }
    return lut.values[idx];
}

void apply_lut(const PreprocessLut* lut, std::uint8_t &r8, std::uint8_t &g8, std::uint8_t &b8)
{
    if (!lut || lut->size <= 1 || lut->values.empty()) {
        return;
    }

    auto normalize = [&](float value, float min_v, float max_v) {
        if (max_v <= min_v) {
            return 0.0f;
        }
        return clamp01f((value - min_v) / (max_v - min_v));
    };

    float r = normalize(r8 / 255.0f, lut->domain_min[0], lut->domain_max[0]);
    float g = normalize(g8 / 255.0f, lut->domain_min[1], lut->domain_max[1]);
    float b = normalize(b8 / 255.0f, lut->domain_min[2], lut->domain_max[2]);

    const float max_index = static_cast<float>(lut->size - 1);
    float rf = r * max_index;
    float gf = g * max_index;
    float bf = b * max_index;

    int r0 = static_cast<int>(floorf(rf));
    int g0 = static_cast<int>(floorf(gf));
    int b0 = static_cast<int>(floorf(bf));

    int r1 = std::min(r0 + 1, lut->size - 1);
    int g1 = std::min(g0 + 1, lut->size - 1);
    int b1 = std::min(b0 + 1, lut->size - 1);

    float tr = rf - static_cast<float>(r0);
    float tg = gf - static_cast<float>(g0);
    float tb = bf - static_cast<float>(b0);

    auto interp = [&](int channel) {
        float c000 = sample_lut_channel(*lut, r0, g0, b0, channel);
        float c100 = sample_lut_channel(*lut, r1, g0, b0, channel);
        float c010 = sample_lut_channel(*lut, r0, g1, b0, channel);
        float c110 = sample_lut_channel(*lut, r1, g1, b0, channel);
        float c001 = sample_lut_channel(*lut, r0, g0, b1, channel);
        float c101 = sample_lut_channel(*lut, r1, g0, b1, channel);
        float c011 = sample_lut_channel(*lut, r0, g1, b1, channel);
        float c111 = sample_lut_channel(*lut, r1, g1, b1, channel);

        float c00 = c000 + (c100 - c000) * tr;
        float c01 = c001 + (c101 - c001) * tr;
        float c10 = c010 + (c110 - c010) * tr;
        float c11 = c011 + (c111 - c011) * tr;

        float c0 = c00 + (c10 - c00) * tg;
        float c1 = c01 + (c11 - c01) * tg;
        return c0 + (c1 - c0) * tb;
    };

    float lr = clamp01f(interp(0));
    float lg = clamp01f(interp(1));
    float lb = clamp01f(interp(2));

    r8 = static_cast<std::uint8_t>(lr * 255.0f + 0.5f);
    g8 = static_cast<std::uint8_t>(lg * 255.0f + 0.5f);
    b8 = static_cast<std::uint8_t>(lb * 255.0f + 0.5f);
}

} // namespace

float clamp01f(float v)
{
    if (v < 0.0f) return 0.0f;
    if (v > 1.0f) return 1.0f;
    return v;
}

void rgb_to_hsb(std::uint8_t r8, std::uint8_t g8, std::uint8_t b8,
                float &h, float &s, float &v)
{
    float r = r8 / 255.0f;
    float g = g8 / 255.0f;
    float b = b8 / 255.0f;

    float maxc = max3f(r, g, b);
    float minc = min3f(r, g, b);
    float delta = maxc - minc;

    v = maxc;

    if (maxc <= 0.0f) {
        s = 0.0f;
        h = 0.0f;
        return;
    }

    s = (delta <= 0.0f) ? 0.0f : (delta / maxc);

    if (delta <= 0.0f) {
        h = 0.0f;
    } else {
        float hue;
        if (maxc == r) {
            hue = (g - b) / delta;
        } else if (maxc == g) {
            hue = 2.0f + (b - r) / delta;
        } else {
            hue = 4.0f + (r - g) / delta;
        }
        hue *= 60.0f;
        if (hue < 0.0f) {
            hue += 360.0f;
        }
        h = hue / 360.0f; // 0〜1 に正規化
    }
}

void hsb_to_rgb(float h, float s, float v,
                std::uint8_t &r8, std::uint8_t &g8, std::uint8_t &b8)
{
    h = h - floorf(h);      // 念のため 0〜1 に丸め
    s = clamp01f(s);
    v = clamp01f(v);

    float r, g, b;

    if (s <= 0.0f) {
        r = g = b = v;
    } else {
        float hh = h * 6.0f;
        int   i  = static_cast<int>(floorf(hh));
        float ff = hh - static_cast<float>(i);
        float p  = v * (1.0f - s);
        float q  = v * (1.0f - s * ff);
        float t  = v * (1.0f - s * (1.0f - ff));

        switch (i) {
        case 0: r = v; g = t; b = p; break;
        case 1: r = q; g = v; b = p; break;
        case 2: r = p; g = v; b = t; break;
        case 3: r = p; g = q; b = v; break;
        case 4: r = t; g = p; b = v; break;
        default: // case 5:
            r = v; g = p; b = q; break;
        }
    }

    r8 = static_cast<std::uint8_t>(clamp01f(r) * 255.0f + 0.5f);
    g8 = static_cast<std::uint8_t>(clamp01f(g) * 255.0f + 0.5f);
    b8 = static_cast<std::uint8_t>(clamp01f(b) * 255.0f + 0.5f);
}

void apply_preprocess(const QuantInfo *qi,
                      std::uint8_t &r8,
                      std::uint8_t &g8,
                      std::uint8_t &b8)
{
    if (!qi) return;

    const bool has_adjustments = (qi->pre_sat > 0.0f || qi->pre_gamma > 0.0f ||
                                  qi->pre_highlight > 0.0f || qi->pre_hue != 0.0f);
    if (!qi->pre_lut && !has_adjustments) {
        return;
    }

    if (qi->pre_lut) {
        apply_lut(qi->pre_lut, r8, g8, b8);
        if (!has_adjustments) {
            return;
        }
    }

    float h, s, v;
    rgb_to_hsb(r8, g8, b8, h, s, v);

    if (qi->pre_hue != 0.0f) {
        h += qi->pre_hue / 360.0f;
    }

    if (qi->pre_sat > 0.0f) {
        const float sat_scale = 1.0f + (1.25f - 1.0f) * qi->pre_sat;
        s *= sat_scale;
    }

    if (qi->pre_gamma > 0.0f) {
        const float gamma = 1.0f + (1.2f - 1.0f) * qi->pre_gamma;
        v = powf(v, gamma);
    }

    if (qi->pre_highlight > 0.0f) {
        if (v > 0.5f) {
            float t = (v - 0.5f) / 0.5f;
            const float highlight_scale = 1.0f + (1.3f - 1.0f) * qi->pre_highlight;
            t *= highlight_scale;
            t  = clamp01f(t);
            v  = 0.5f + t * 0.5f;
        }
    }

    hsb_to_rgb(h, s, v, r8, g8, b8);
}

void ensure_palette_hsb_initialized()
{
    if (g_palette_hsb_initialized) {
        return;
    }
    for (int i = 0; i < MSX1PQ::kNumQuantColors; i++) {
        float h, s, v;
        rgb_to_hsb(MSX1PQ::kQuantColors[i].r,
                   MSX1PQ::kQuantColors[i].g,
                   MSX1PQ::kQuantColors[i].b,
                   h, s, v);
        g_palette_h[i] = h;
        g_palette_s[i] = s;
        g_palette_b[i] = v;
    }
    g_palette_hsb_initialized = true;
}

int nearest_palette_rgb(std::uint8_t r8, std::uint8_t g8, std::uint8_t b8,
                        int num_colors)
{
    int   best_idx = 0;
    float best_d2  = 1.0e30f;

    for (int i = 0; i < num_colors; ++i) {
        const MSX1PQ::QuantColor &qc = MSX1PQ::kQuantColors[i];
        float dr = static_cast<float>(r8) - static_cast<float>(qc.r);
        float dg = static_cast<float>(g8) - static_cast<float>(qc.g);
        float db = static_cast<float>(b8) - static_cast<float>(qc.b);
        float d2 = dr*dr + dg*dg + db*db;

        if (d2 < best_d2) {
            best_d2  = d2;
            best_idx = i;
        }
    }
    return best_idx;
}

int nearest_palette_hsb(std::uint8_t r8, std::uint8_t g8, std::uint8_t b8,
                        float w_h, float w_s, float w_b,
                        int num_colors)
{
    ensure_palette_hsb_initialized();

    float h, s, v;
    rgb_to_hsb(r8, g8, b8, h, s, v);

    int   best_idx = 0;
    float best_d2  = 1.0e30f;

    for (int i = 0; i < num_colors; ++i) {
        float dh = h - g_palette_h[i];
        float ds = s - g_palette_s[i];
        float dv = v - g_palette_b[i];

        float d2 = (w_h * dh * dh +
                    w_s * ds * ds +
                    w_b * dv * dv);

        if (d2 < best_d2) {
            best_d2  = d2;
            best_idx = i;
        }
    }
    return best_idx;
}

int nearest_basic_hsb(std::uint8_t r8, std::uint8_t g8, std::uint8_t b8,
                      float w_h, float w_s, float w_b)
{
    ensure_palette_hsb_initialized();

    float h, s, v;
    rgb_to_hsb(r8, g8, b8, h, s, v);

    float wh = clamp01f(w_h);
    float ws = clamp01f(w_s);
    float wb = clamp01f(w_b);

    int   best_idx = 0;
    float best_d2  = 1.0e30f;

    for (int i = 0; i < MSX1PQ::kNumBasicColors; i++) {
        float dh = std::fabs(h - g_palette_h[i]);
        if (dh > 0.5f) {
            dh = 1.0f - dh;
        }
        float ds = s - g_palette_s[i];
        float dv = v - g_palette_b[i];

        float d2 =
            (wh * dh) * (wh * dh) +
            (ws * ds) * (ws * ds) +
            (wb * dv) * (wb * dv);

        if (d2 < best_d2) {
            best_d2  = d2;
            best_idx = i;
        }
    }
    return best_idx;
}

const MSX1PQ::QuantColor* get_basic_palette(int color_system)
{
    return (color_system == MSX1PQ_COLOR_SYS_MSX2)
        ? MSX1PQ::kBasicColorsMsx2
        : MSX1PQ::kQuantColors;
}

int find_basic_index_from_rgb(std::uint8_t r, std::uint8_t g, std::uint8_t b,
                              int color_system)
{
    const MSX1PQ::QuantColor* table = get_basic_palette(color_system);

    int  best_idx  = 0;
    long best_dist = 0x7fffffffL;

    for (int i = 0; i < MSX1PQ::kNumBasicColors; ++i) {
        long dr = static_cast<long>(r) - static_cast<long>(table[i].r);
        long dg = static_cast<long>(g) - static_cast<long>(table[i].g);
        long db = static_cast<long>(b) - static_cast<long>(table[i].b);

        long d2 = dr*dr + dg*dg + db*db;
        if (d2 < best_dist) {
            best_dist = d2;
            best_idx  = i;
        }
    }
    return best_idx;
}

int transition_cost_pair(int prevA, int prevB, int a, int b)
{
    const int COST_SAME          = 0;
    const int COST_SAME_BUT_SWAP = 3;
    const int COST_DIFFERENT     = 8;

    if (prevA < 0 || prevB < 0) {
        return COST_SAME;
    }

    if ((a == prevA && b == prevB)) return COST_SAME;
    if ((a == prevB && b == prevA)) return COST_SAME_BUT_SWAP;
    if (a == prevA || b == prevB)   return COST_SAME_BUT_SWAP;
    if (a == prevB || b == prevA)   return COST_SAME_BUT_SWAP;

    return COST_DIFFERENT;
}

bool load_cube_lut(const char* path, PreprocessLut& out_lut, std::string& error_message)
{
    if (!path) {
        error_message = "Invalid LUT path";
        return false;
    }

    std::ifstream ifs(path);
    if (!ifs) {
        error_message = "Failed to open LUT file";
        return false;
    }

    auto trim = [](std::string& str) {
        auto is_space = [](unsigned char c) { return std::isspace(c) != 0; };
        str.erase(str.begin(), std::find_if(str.begin(), str.end(), [&](unsigned char c) { return !is_space(c); }));
        str.erase(std::find_if(str.rbegin(), str.rend(), [&](unsigned char c) { return !is_space(c); }).base(), str.end());
    };

    out_lut = PreprocessLut{};

    std::string line;
    int expected_values = -1;
    while (std::getline(ifs, line)) {
        // Remove comments
        auto comment_pos = line.find('#');
        if (comment_pos != std::string::npos) {
            line = line.substr(0, comment_pos);
        }
        comment_pos = line.find("//");
        if (comment_pos != std::string::npos) {
            line = line.substr(0, comment_pos);
        }

        trim(line);
        if (line.empty()) {
            continue;
        }

        std::istringstream iss(line);
        std::string head;
        iss >> head;
        if (head == "TITLE") {
            continue;
        } else if (head == "LUT_3D_SIZE") {
            iss >> out_lut.size;
            if (out_lut.size <= 1) {
                error_message = "LUT_3D_SIZE must be greater than 1";
                return false;
            }
            expected_values = out_lut.size * out_lut.size * out_lut.size;
            out_lut.values.reserve(static_cast<std::size_t>(expected_values) * 3);
        } else if (head == "DOMAIN_MIN") {
            iss >> out_lut.domain_min[0] >> out_lut.domain_min[1] >> out_lut.domain_min[2];
        } else if (head == "DOMAIN_MAX") {
            iss >> out_lut.domain_max[0] >> out_lut.domain_max[1] >> out_lut.domain_max[2];
        } else {
            // Assume data line
            float r, g, b;
            if (!(std::istringstream(line) >> r >> g >> b)) {
                error_message = "Failed to parse LUT value line";
                return false;
            }
            out_lut.values.push_back(r);
            out_lut.values.push_back(g);
            out_lut.values.push_back(b);
        }
    }

    if (out_lut.size <= 1 || expected_values < 0) {
        error_message = "LUT_3D_SIZE was not specified";
        return false;
    }

    if (static_cast<int>(out_lut.values.size() / 3) != expected_values) {
        error_message = "Unexpected number of LUT entries";
        return false;
    }

    return true;
}

} // namespace MSX1PQCore

