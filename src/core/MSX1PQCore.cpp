// src/core/MSX1PQCore.cpp

#include "MSX1PQCore.h"
#include "MSX1PQPalettes.h"

#include <cmath>
#include <cstdint>
#include <algorithm>

namespace MSX1PQ {
namespace Core {

// パレットHSBキャッシュ
static bool   g_palette_hsb_initialized = false;
static float  g_palette_h[256];
static float  g_palette_s[256];
static float  g_palette_b[256];

static inline float clamp01f(float v)
{
    if (v < 0.0f) return 0.0f;
    if (v > 1.0f) return 1.0f;
    return v;
}

static inline float max3f(float a, float b, float c)
{
    float m = (a > b) ? a : b;
    return (m > c) ? m : c;
}

static inline float min3f(float a, float b, float c)
{
    float m = (a < b) ? a : b;
    return (m < c) ? m : c;
}

// RGB(0-255) → H(0-360), S(0-1), V(0-1)
static void RgbToHsv(
    std::uint8_t r8, std::uint8_t g8, std::uint8_t b8,
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

    if (delta <= 0.0f) {
        s = 0.0f;
        h = 0.0f;
        return;
    }

    s = delta / maxc;

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
    h = hue;
}

// H(0-360), S(0-1), V(0-1) → RGB(0-255)
static void HsvToRgb(
    float h, float s, float v,
    std::uint8_t &r8, std::uint8_t &g8, std::uint8_t &b8)
{
    h = std::fmod(h, 360.0f);
    if (h < 0.0f) h += 360.0f;

    s = clamp01f(s);
    v = clamp01f(v);

    if (s <= 0.0f) {
        std::uint8_t g = static_cast<std::uint8_t>(std::round(v * 255.0f));
        r8 = g8 = b8 = g;
        return;
    }

    float hf = h / 60.0f;
    int   i  = static_cast<int>(std::floor(hf));
    float f  = hf - static_cast<float>(i);

    float p = v * (1.0f - s);
    float q = v * (1.0f - s * f);
    float t = v * (1.0f - s * (1.0f - f));

    float rf, gf, bf;
    switch (i) {
    default:
    case 0: rf = v; gf = t; bf = p; break;
    case 1: rf = q; gf = v; bf = p; break;
    case 2: rf = p; gf = v; bf = t; break;
    case 3: rf = p; gf = q; bf = v; break;
    case 4: rf = t; gf = p; bf = v; break;
    case 5: rf = v; gf = p; bf = q; break;
    }

    r8 = static_cast<std::uint8_t>(std::round(clamp01f(rf) * 255.0f));
    g8 = static_cast<std::uint8_t>(std::round(clamp01f(gf) * 255.0f));
    b8 = static_cast<std::uint8_t>(std::round(clamp01f(bf) * 255.0f));
}

static void EnsurePaletteHsvInitialized()
{
    if (g_palette_hsb_initialized) {
        return;
    }

    const int num = std::min(kNumQuantColors, 256);
    for (int i = 0; i < num; ++i) {
        float h, s, v;
        RgbToHsv(kQuantColors[i].r, kQuantColors[i].g, kQuantColors[i].b, h, s, v);
        g_palette_h[i] = h;
        g_palette_s[i] = s;
        g_palette_b[i] = v;
    }
    for (int i = num; i < 256; ++i) {
        g_palette_h[i] = 0.0f;
        g_palette_s[i] = 0.0f;
        g_palette_b[i] = 0.0f;
    }
    g_palette_hsb_initialized = true;
}

// HSB ベースの距離
static float HsvDistanceSq(
    float h1, float s1, float v1,
    float h2, float s2, float v2,
    const HsbWeight& w)
{
    float dh = h1 - h2;
    // 周期性を考慮して 0..180 に収める
    while (dh > 180.0f) dh -= 360.0f;
    while (dh < -180.0f) dh += 360.0f;
    dh /= 180.0f; // -1..1 → 他とスケール合わせ

    float ds = s1 - s2;
    float dv = v1 - v2;

    return w.h * dh * dh +
           w.s * ds * ds +
           w.b * dv * dv;
}

// RGB ベースの距離
static inline float RgbDistanceSq(
    std::uint8_t r1, std::uint8_t g1, std::uint8_t b1,
    std::uint8_t r2, std::uint8_t g2, std::uint8_t b2)
{
    const float dr = static_cast<float>(r1) - static_cast<float>(r2);
    const float dg = static_cast<float>(g1) - static_cast<float>(g2);
    const float db = static_cast<float>(b1) - static_cast<float>(b2);
    return dr * dr + dg * dg + db * db;
}

// 事前処理（今は何もしない。既存プリプロを移植するならここ）
static void ApplyPreprocess(
    const QuantizeConfig& /*config*/,
    std::uint8_t& /*r*/,
    std::uint8_t& /*g*/,
    std::uint8_t& /*b*/)
{
    // TODO: preSaturation / preGamma / preHighlight / preSkin を反映するなら実装
}

// パレット内で最近傍インデックスを探す（RGB or HSB）
static int FindNearestPaletteIndex(
    const QuantizeConfig& config,
    std::uint8_t r,
    std::uint8_t g,
    std::uint8_t b)
{
    int beginIndex = 0;
    int endIndex   = kNumQuantColors; // [begin, end)

    if (!config.useDither) {
        // ディザなし → 基本15色のみ
        endIndex = kNumBasicColors;
    } else {
        if (!config.useDarkDither) {
            // 暗部ディザは除外
            endIndex = kFirstDarkDitherIndex;
        }
        // useDarkDither == true → 全範囲
    }

    endIndex = std::max(beginIndex + 1, std::min(endIndex, kNumQuantColors));

    if (config.distanceMode == DistanceMode::RGB) {
        int   bestIdx = beginIndex;
        float bestD2  = 1.0e30f;

        for (int i = beginIndex; i < endIndex; ++i) {
            float d2 = RgbDistanceSq(
                r, g, b,
                kQuantColors[i].r,
                kQuantColors[i].g,
                kQuantColors[i].b);
            if (d2 < bestD2) {
                bestD2  = d2;
                bestIdx = i;
            }
        }
        return bestIdx;
    } else {
        // HSB 距離
        EnsurePaletteHsvInitialized();

        float h, s, v;
        RgbToHsv(r, g, b, h, s, v);

        int   bestIdx = beginIndex;
        float bestD2  = 1.0e30f;

        for (int i = beginIndex; i < endIndex; ++i) {
            float d2 = HsvDistanceSq(
                h, s, v,
                g_palette_h[i],
                g_palette_s[i],
                g_palette_b[i],
                config.hsbWeight);
            if (d2 < bestD2) {
                bestD2  = d2;
                bestIdx = i;
            }
        }
        return bestIdx;
    }
}

void QuantizePixel(
    const QuantizeConfig& config,
    int x,
    int y,
    std::uint8_t in_r,
    std::uint8_t in_g,
    std::uint8_t in_b,
    std::uint8_t& out_r,
    std::uint8_t& out_g,
    std::uint8_t& out_b)
{
    (void)x;
    (void)y;

    std::uint8_t r = in_r;
    std::uint8_t g = in_g;
    std::uint8_t b = in_b;

    // プリプロセス
    ApplyPreprocess(config, r, g, b);

    // 今は MSX1 / MSX2 の分岐は未実装扱い（MSX1 相当で処理）
    // TODO: ColorSystem::MSX2 対応するならここに分岐を追加

    const int idx = FindNearestPaletteIndex(config, r, g, b);

    // ディザ有効時は、座標依存のディザパターンを通して基本15色に変換
    const int basic_idx = config.useDither
        ? palette_index_to_basic_index(idx, x, y)
        : idx;

    out_r = kQuantColors[basic_idx].r;
    out_g = kQuantColors[basic_idx].g;
    out_b = kQuantColors[basic_idx].b;
}

void ProcessImageRGBA8(
    const QuantizeConfig& config,
    std::uint8_t* data,
    int width,
    int height,
    int strideBytes,
    bool keepAlpha)
{
    if (!data || width <= 0 || height <= 0 || strideBytes < width * 4) {
        return;
    }

    for (int y = 0; y < height; ++y) {
        std::uint8_t* p = data + y * strideBytes;
        for (int x = 0; x < width; ++x) {
            std::uint8_t* px = p + x * 4;

            std::uint8_t r = px[0];
            std::uint8_t g = px[1];
            std::uint8_t b = px[2];
            std::uint8_t a = px[3];

            std::uint8_t qr, qg, qb;
            QuantizePixel(config, x, y, r, g, b, qr, qg, qb);

            px[0] = qr;
            px[1] = qg;
            px[2] = qb;
            if (!keepAlpha) {
                px[3] = 255;
            } else {
                px[3] = a;
            }
        }
    }

    // TODO:
    //   config.eightDotMode を見て、
    //   8dot / 2色制限アルゴリズムをここで後処理として実装。
    //   いまはプレーンなパレット量子化のみ。
}

} // namespace Core
} // namespace MSX1PQ
