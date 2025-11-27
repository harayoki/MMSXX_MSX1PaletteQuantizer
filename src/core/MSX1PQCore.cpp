#include "MSX1PQCore.h"

#include <algorithm>
#include <cmath>

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

    const int posterize_levels = std::clamp(qi->pre_posterize, 1, 255);
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

