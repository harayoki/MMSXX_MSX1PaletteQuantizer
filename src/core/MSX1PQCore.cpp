#include "MSX1PQCore.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

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

std::string to_lower_copy(const std::string& s)
{   
    std::string result = s;
    std::transform(result.begin(), result.end(), result.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return result;
}

std::string get_lower_extension(const std::string& path)
{
    const std::string::size_type dot = path.find_last_of('.');
    if (dot == std::string::npos) {
        return std::string();
    }
    return to_lower_copy(path.substr(dot));
}

bool parse_cube_lut(std::istream& file, std::vector<float>& out3d, int& lut_size)
{
    lut_size = 0;
    out3d.clear();

    std::vector<std::array<float, 3>> rows;
    std::string line;

    auto normalize_value = [](float v, float max_value) {
        if (max_value <= 1.0f) {
            return clamp_value(v, 0.0f, 1.0f);
        }
        return clamp_value(v / max_value, 0.0f, 1.0f);
    };

    while (std::getline(file, line)) {
        const auto hash_pos = line.find('#');
        if (hash_pos != std::string::npos) {
            line = line.substr(0, hash_pos);
        }

        std::istringstream iss(line);
        std::string token;
        if (!(iss >> token)) {
            continue;
        }

        if (token == "LUT_3D_SIZE") {
            iss >> lut_size;
            continue;
        }

        float r, g, b;
        try {
            r = std::stof(token);
        } catch (...) {
            continue;
        }
        if (!(iss >> g >> b)) {
            continue;
        }
        rows.push_back({r, g, b});
    }

    if (rows.empty()) {
        return false;
    }

    if (lut_size == 0) {
        lut_size = static_cast<int>(std::round(std::cbrt(static_cast<double>(rows.size()))));
    }

    const std::size_t expected_entries = static_cast<std::size_t>(lut_size) * lut_size * lut_size;
    if (expected_entries != rows.size()) {
        return false;
    }

    float max_value = 1.0f;
    for (const auto& row : rows) {
        max_value = std::max({max_value, row[0], row[1], row[2]});
    }

    out3d.reserve(rows.size() * 3);
    for (const auto& row : rows) {
        out3d.push_back(normalize_value(row[0], max_value));
        out3d.push_back(normalize_value(row[1], max_value));
        out3d.push_back(normalize_value(row[2], max_value));
    }

    return true;
}

// パレットのHSBを一度だけ計算してキャッシュ
bool  g_palette_hsb_initialized = false;
float g_palette_h[256];
float g_palette_s[256];
float g_palette_b[256];

} // namespace

float clamp01f(float v)
{
    if (v < 0.0f) return 0.0f;
    if (v > 1.0f) return 1.0f;
    return v;
}

void apply_sharpness_rgb(float amount,
                         std::uint8_t blurred_r,
                         std::uint8_t blurred_g,
                         std::uint8_t blurred_b,
                         std::uint8_t &r8,
                         std::uint8_t &g8,
                         std::uint8_t &b8)
{
    amount = clamp01f(amount);
    if (amount <= 0.0f) {
        return;
    }

    auto sharpen = [amount](std::uint8_t src, std::uint8_t blurred) {
        float delta = static_cast<float>(src) - static_cast<float>(blurred);
        float value = static_cast<float>(src) + delta * (1.5f * amount);
        return clamp_value<int>(static_cast<int>(std::round(value)), 0, 255);
    };

    r8 = static_cast<std::uint8_t>(sharpen(r8, blurred_r));
    g8 = static_cast<std::uint8_t>(sharpen(g8, blurred_g));
    b8 = static_cast<std::uint8_t>(sharpen(b8, blurred_b));
}

bool load_pre_lut(const std::string& path,
                  std::vector<std::uint8_t>& out1d,
                  std::vector<float>& out3d,
                  int& lut3d_size)
{
    out1d.clear();
    out3d.clear();
    lut3d_size = 0;

    std::ifstream file(path.c_str());
    if (!file.is_open()) {
        std::cerr << "Failed to open LUT file: " << path << "\n";
        return false;
    }

    const std::string ext = get_lower_extension(path);
    if (ext == ".cube") {
        if (parse_cube_lut(file, out3d, lut3d_size)) {
            return true;
        }

        file.clear();
        file.seekg(0);
    }

    std::vector<int> values;
    values.reserve(256 * 3);

    std::string line;
    while (std::getline(file, line)) {
        const auto comment_pos = line.find('#');
        if (comment_pos != std::string::npos) {
            line = line.substr(0, comment_pos);
        }
        for (char& c : line) {
            if (c == ',' || c == ';') {
                c = ' ';
            }
        }

        std::istringstream iss(line);
        int v;
        while (iss >> v) {
            if (v < 0 || v > 255) {
                std::cerr << "LUT value out of range (0-255): " << v << "\n";
                return false;
            }
            values.push_back(v);
        }
    }

    if (values.size() != 256 * 3) {
        std::cerr << "LUT must contain 256 RGB triplets (found " << values.size() << " values)\n";
        return false;
    }

    out1d.resize(values.size());
    for (std::size_t i = 0; i < values.size(); ++i) {
        out1d[i] = static_cast<std::uint8_t>(values[i]);
    }

    return true;
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

    if (qi->pre_lut3d && qi->pre_lut3d_size > 1) {
        const int lut_size = qi->pre_lut3d_size;
        const float scale  = static_cast<float>(lut_size - 1);

        struct LutSample {
            int idx0;
            int idx1;
            float t;
        };

        auto sample = [&](float v) -> LutSample {
            float pos  = v * scale;
            int idx0   = static_cast<int>(floorf(pos));
            int idx1   = idx0 + 1;
            float t    = pos - static_cast<float>(idx0);
            if (idx1 >= lut_size) {
                idx1 = lut_size - 1;
            }
            return {idx0, idx1, t};
        };

        auto lerp = [](float a, float b, float t) {
            return a + (b - a) * t;
        };

        const auto rx = sample(static_cast<float>(r8) / 255.0f);
        const auto ry = sample(static_cast<float>(g8) / 255.0f);
        const auto rz = sample(static_cast<float>(b8) / 255.0f);

        auto lut_index = [lut_size](int x, int y, int z) {
            return ((z * lut_size + y) * lut_size + x) * 3;
        };

        auto fetch = [&](int x, int y, int z, int offset) {
            return qi->pre_lut3d[lut_index(x, y, z) + offset];
        };

        float c000_r = fetch(rx.idx0, ry.idx0, rz.idx0, 0);
        float c000_g = fetch(rx.idx0, ry.idx0, rz.idx0, 1);
        float c000_b = fetch(rx.idx0, ry.idx0, rz.idx0, 2);

        float c100_r = fetch(rx.idx1, ry.idx0, rz.idx0, 0);
        float c100_g = fetch(rx.idx1, ry.idx0, rz.idx0, 1);
        float c100_b = fetch(rx.idx1, ry.idx0, rz.idx0, 2);

        float c010_r = fetch(rx.idx0, ry.idx1, rz.idx0, 0);
        float c010_g = fetch(rx.idx0, ry.idx1, rz.idx0, 1);
        float c010_b = fetch(rx.idx0, ry.idx1, rz.idx0, 2);

        float c110_r = fetch(rx.idx1, ry.idx1, rz.idx0, 0);
        float c110_g = fetch(rx.idx1, ry.idx1, rz.idx0, 1);
        float c110_b = fetch(rx.idx1, ry.idx1, rz.idx0, 2);

        float c001_r = fetch(rx.idx0, ry.idx0, rz.idx1, 0);
        float c001_g = fetch(rx.idx0, ry.idx0, rz.idx1, 1);
        float c001_b = fetch(rx.idx0, ry.idx0, rz.idx1, 2);

        float c101_r = fetch(rx.idx1, ry.idx0, rz.idx1, 0);
        float c101_g = fetch(rx.idx1, ry.idx0, rz.idx1, 1);
        float c101_b = fetch(rx.idx1, ry.idx0, rz.idx1, 2);

        float c011_r = fetch(rx.idx0, ry.idx1, rz.idx1, 0);
        float c011_g = fetch(rx.idx0, ry.idx1, rz.idx1, 1);
        float c011_b = fetch(rx.idx0, ry.idx1, rz.idx1, 2);

        float c111_r = fetch(rx.idx1, ry.idx1, rz.idx1, 0);
        float c111_g = fetch(rx.idx1, ry.idx1, rz.idx1, 1);
        float c111_b = fetch(rx.idx1, ry.idx1, rz.idx1, 2);

        auto interp_channel = [&](float c000, float c100, float c010, float c110,
                                  float c001, float c101, float c011, float c111) {
            float c00 = lerp(c000, c100, rx.t);
            float c01 = lerp(c001, c101, rx.t);
            float c10 = lerp(c010, c110, rx.t);
            float c11 = lerp(c011, c111, rx.t);

            float c0 = lerp(c00, c10, ry.t);
            float c1 = lerp(c01, c11, ry.t);
            return lerp(c0, c1, rz.t);
        };

        float rf = interp_channel(c000_r, c100_r, c010_r, c110_r, c001_r, c101_r, c011_r, c111_r);
        float gf = interp_channel(c000_g, c100_g, c010_g, c110_g, c001_g, c101_g, c011_g, c111_g);
        float bf = interp_channel(c000_b, c100_b, c010_b, c110_b, c001_b, c101_b, c011_b, c111_b);

        r8 = static_cast<std::uint8_t>(clamp_value(rf * 255.0f + 0.5f, 0.0f, 255.0f));
        g8 = static_cast<std::uint8_t>(clamp_value(gf * 255.0f + 0.5f, 0.0f, 255.0f));
        b8 = static_cast<std::uint8_t>(clamp_value(bf * 255.0f + 0.5f, 0.0f, 255.0f));
    } else if (qi->pre_lut) {
        auto apply_lut = [lut = qi->pre_lut](std::uint8_t v, int offset) {
            return lut[static_cast<std::size_t>(v) * 3 + offset];
        };
        r8 = apply_lut(r8, 0);
        g8 = apply_lut(g8, 1);
        b8 = apply_lut(b8, 2);
    }

    const int posterize_levels = clamp_value(qi->pre_posterize, 0, 255);
    const bool do_posterize = (posterize_levels > 1);
    const bool do_hsv_adjust =
        (qi->pre_sat > 0.0f) || (qi->pre_gamma > 0.0f) ||
        (qi->pre_highlight > 0.0f) || (qi->pre_hue != 0.0f);

    if (!do_posterize && !do_hsv_adjust) {
        return;
    }

    if (do_posterize) {
        const float scale = static_cast<float>(posterize_levels - 1);
        auto posterize_channel = [scale](std::uint8_t v) -> std::uint8_t {
            float normalized = static_cast<float>(v) / 255.0f;
            float quantized = roundf(normalized * scale) / scale;
            int quantized8 = static_cast<int>(quantized * 255.0f + 0.5f);
            if (quantized8 < 0) quantized8 = 0;
            if (quantized8 > 255) quantized8 = 255;
            return static_cast<std::uint8_t>(quantized8);
        };

        r8 = posterize_channel(r8);
        g8 = posterize_channel(g8);
        b8 = posterize_channel(b8);
    }

    if (!do_hsv_adjust) {
        return;
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

MSX1PQ::QuantColor quantize_pixel(const QuantInfo& qi,
                                  std::uint8_t r,
                                  std::uint8_t g,
                                  std::uint8_t b,
                                  std::int32_t x,
                                  std::int32_t y)
{
    if (qi.use_palette_color) {
        const int palette_idx = qi.use_hsb
            ? nearest_palette_hsb(r, g, b, qi.w_h, qi.w_s, qi.w_b, MSX1PQ::kNumQuantColors)
            : nearest_palette_rgb(r, g, b, MSX1PQ::kNumQuantColors);

        return MSX1PQ::kQuantColors[palette_idx];
    }

    int basic_idx = 0;

    if (qi.use_dither) {
        int num_colors = MSX1PQ::kNumQuantColors;
        if (!qi.use_dark_dither) {
            num_colors = MSX1PQ::kFirstDarkDitherIndex;
        }

        const int palette_idx = qi.use_hsb
            ? nearest_palette_hsb(r, g, b, qi.w_h, qi.w_s, qi.w_b, num_colors)
            : nearest_palette_rgb(r, g, b, num_colors);

        basic_idx = MSX1PQ::palette_index_to_basic_index(palette_idx, x, y);
    } else if (qi.use_hsb) {
        basic_idx = nearest_basic_hsb(r, g, b, qi.w_h, qi.w_s, qi.w_b);
    } else {
        basic_idx = MSX1PQ::nearest_basic_rgb(r, g, b);
    }

    const MSX1PQ::QuantColor* palette =
        (qi.color_system == MSX1PQ_COLOR_SYS_MSX2)
            ? MSX1PQ::kBasicColorsMsx2
            : MSX1PQ::kQuantColors;

    return palette[basic_idx];
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

} // namespace MSX1PQCore

