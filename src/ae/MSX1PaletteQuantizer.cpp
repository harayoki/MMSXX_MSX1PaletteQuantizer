/*
    MSX1PaletteQuantizer.cpp

    MSX1 パレット エフェクト
    AE / Premiere 両対応。

*/

#include "AEConfig.h"
#include "entry.h"
#include "AE_Effect.h"
#include "AE_EffectCB.h"
#include "Param_Utils.h"
#include "AEFX_SuiteHelper.h"
#include "AEGP_SuiteHandler.h"
#include "MSX1PaletteQuantizer.h"
#include "MSX1PQPalettes.h"


#ifdef AE_OS_WIN
#include <Windows.h>
#include <cstdarg>
#include <cstdio>
inline void MSX1PQ_DebugLog(const char* fmt, ...)
{
    char buf[512];

    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);

    OutputDebugStringA(buf);
    OutputDebugStringA("\n");
}
#else
// Mac の場合（AE_OS_WIN が未定義）
inline void MSX1PQ_DebugLog(const char* /*fmt*/, ...) {}
#endif

namespace MSX1PQ {
    constexpr char kPluginName[]        = "MSX1 Palette Quantizer";
    constexpr char kPluginDescription[] = "\nMSX1-style palette quantization and dithering.";
    constexpr int  kVersionMajor        = 0;
    constexpr int  kVersionMinor        = 2;
    constexpr int  kVersionBug          = 0;
    constexpr int  kVersionStage        = PF_Stage_ALPHA;
    /*
	PF_Stage_DEVELOP,
	PF_Stage_ALPHA,
	PF_Stage_BETA,
	PF_Stage_RELEASE
	*/
    constexpr int  kVersionBuild        = 1;

    constexpr unsigned long kVersionPacked = PF_VERSION(
        kVersionMajor,
        kVersionMinor,
        kVersionBug,
        kVersionStage,
        kVersionBuild
    );
}

typedef struct {
    A_Boolean use_dither;
    A_long use_8dot2col;
    A_Boolean use_hsb;
    PF_FpLong w_h;
    PF_FpLong w_s;
    PF_FpLong w_b;
    A_Boolean pre_sat;
    A_Boolean pre_gamma;
    A_Boolean pre_highlight;
    A_Boolean pre_skin;
    A_Boolean use_dark_dither;
    A_long color_system;
} QuantInfo;


typedef void (*Apply8DotFn_ARGB)(
    PF_Pixel8* data,
    A_long     row_pitch,
    A_long     width,
    A_long     height,
    A_long     color_system);

typedef void (*Apply8DotFn_BGRA)(
    MSX1PQ_Pixel_BGRA_8u* data,
    A_long            row_pitch,
    A_long            width,
    A_long            height,
    A_long            color_system);


// 先にアルゴリズム関数を宣言しておく
template<typename PixelT>
static void apply_8dot2col_basic1(
    PixelT* data, A_long row_pitch,
    A_long width, A_long height,
    A_long color_system);

template<typename PixelT>
static void apply_8dot2col_fast1(
    PixelT* data, A_long row_pitch,
    A_long width, A_long height,
    A_long color_system);

template<typename PixelT>
static void apply_8dot2col_best1(
    PixelT* data, A_long row_pitch,
    A_long width, A_long height,
    A_long color_system);

    template<typename PixelT>
static void apply_8dot2col_attr_best(
    PixelT* data, A_long row_pitch,
    A_long width, A_long height,
    A_long color_system);

template<typename PixelT>
static void apply_8dot2col_attr_best_penalty(
    PixelT* data, A_long row_pitch,
    A_long width, A_long height,
    A_long color_system);

// モード → 関数 のテーブル（インデックス 0 は未使用）

static Apply8DotFn_ARGB g_apply8dot_ARGB[7] = {
    nullptr,
    nullptr,                                      // 1: NONE
    apply_8dot2col_fast1<PF_Pixel8>,             // 2: FAST1
    apply_8dot2col_basic1<PF_Pixel8>,            // 3: BASIC1
    apply_8dot2col_best1<PF_Pixel8>,             // 4: BEST1
    apply_8dot2col_attr_best<PF_Pixel8>,         // 5: 同じセル内の縦帯全体の色ヒストグラム
    apply_8dot2col_attr_best_penalty<PF_Pixel8>, // 6: BEST + 遷移ペナルティ
};

static Apply8DotFn_BGRA g_apply8dot_BGRA[7] = {
    nullptr,
    nullptr,
    apply_8dot2col_fast1<MSX1PQ_Pixel_BGRA_8u>,
    apply_8dot2col_basic1<MSX1PQ_Pixel_BGRA_8u>,
    apply_8dot2col_best1<MSX1PQ_Pixel_BGRA_8u>,
    apply_8dot2col_attr_best<MSX1PQ_Pixel_BGRA_8u>,
    apply_8dot2col_attr_best_penalty<MSX1PQ_Pixel_BGRA_8u>,
};


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

// 既存: MSX1PQ::kQuantColors[]
extern const MSX1PQ::QuantColor MSX1PQ::kQuantColors[];
extern const int        MSX1PQ::kNumQuantColors;

// パレットのHSBを一度だけ計算してキャッシュ
static A_Boolean g_palette_hsb_initialized = FALSE;
static float     g_palette_h[256];
static float     g_palette_s[256];
static float     g_palette_b[256];

static void
rgb_to_hsb(A_u_char r8, A_u_char g8, A_u_char b8,
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
        h = hue / 360.0f; // 0?1 に正規化
    }
}

// HSB -> RGB 変換（簡易版）
static void
hsb_to_rgb(float h, float s, float v,
           A_u_char &r8, A_u_char &g8, A_u_char &b8)
{
    h = h - floorf(h);      // 念のため 0?1 に丸め
    s = clamp01f(s);
    v = clamp01f(v);

    float r, g, b;

    if (s <= 0.0f) {
        r = g = b = v;
    } else {
        float hh = h * 6.0f;
        int   i  = (int)floorf(hh);
        float ff = hh - (float)i;
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

    r8 = (A_u_char)(clamp01f(r) * 255.0f + 0.5f);
    g8 = (A_u_char)(clamp01f(g) * 255.0f + 0.5f);
    b8 = (A_u_char)(clamp01f(b) * 255.0f + 0.5f);
}

// 1?4 のチェックボックス用の前処理
static void
apply_preprocess(const QuantInfo *qi,
                 A_u_char &r8, A_u_char &g8, A_u_char &b8)
{
    if (!qi) return;

    if (!qi->pre_sat && !qi->pre_gamma &&
        !qi->pre_highlight && !qi->pre_skin) {
        return;
    }

    float h, s, v;
    rgb_to_hsb(r8, g8, b8, h, s, v);

    // 1: 彩度ブースト
    if (qi->pre_sat) {
        s *= 1.25f;
    }

    // 2: ガンマ（黒を少し締める）
    if (qi->pre_gamma) {
        const float gamma = 1.2f;   // >1 で暗くなる
        v = powf(v, gamma);
    }

    // 3: ハイライト寄りの補正
    if (qi->pre_highlight) {
        if (v > 0.5f) {
            float t = (v - 0.5f) / 0.5f; // 0?1
            t *= 1.3f;
            t  = clamp01f(t);
            v  = 0.5f + t * 0.5f;
        }
    }

    // 4: 肌色寄せ（黄?オレンジ付近だけ少し赤寄り）
    if (qi->pre_skin) {
        if (v > 0.2f && v < 0.95f && s > 0.2f) {
            if (h > 0.03f && h < 0.18f) { // だいたい黄?オレンジ
                float target = 0.07f;     // 目標色相（オレンジ寄り）
                float t      = 0.25f;     // どれくらい寄せるか
                h = h * (1.0f - t) + target * t;
            }
        }
    }

    hsb_to_rgb(h, s, v, r8, g8, b8);
}


static void
ensure_palette_hsb_initialized()
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
    g_palette_hsb_initialized = TRUE;
}

static int
nearest_palette_rgb(A_u_char r8, A_u_char g8, A_u_char b8,
                    int num_colors)
{
    int   best_idx = 0;
    float best_d2  = 1.0e30f;

    for (int i = 0; i < num_colors; ++i) {
        const MSX1PQ::QuantColor &qc = MSX1PQ::kQuantColors[i];
        float dr = (float)r8 - (float)qc.r;
        float dg = (float)g8 - (float)qc.g;
        float db = (float)b8 - (float)qc.b;
        float d2 = dr*dr + dg*dg + db*db;

        if (d2 < best_d2) {
            best_d2  = d2;
            best_idx = i;
        }
    }
    return best_idx;
}

static int
nearest_palette_hsb(A_u_char r8, A_u_char g8, A_u_char b8,
                    PF_FpLong w_h, PF_FpLong w_s, PF_FpLong w_b,
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

        float d2 = (float)(w_h * dh * dh +
                           w_s * ds * ds +
                           w_b * dv * dv);

        if (d2 < best_d2) {
            best_d2  = d2;
            best_idx = i;
        }
    }
    return best_idx;
}

static inline int
nearest_basic_hsb(A_u_char r8, A_u_char g8, A_u_char b8,
                  PF_FpLong w_h, PF_FpLong w_s, PF_FpLong w_b)
{
    ensure_palette_hsb_initialized();

    float h, s, v;
    rgb_to_hsb(r8, g8, b8, h, s, v);

    float wh = clamp01f((float)w_h);
    float ws = clamp01f((float)w_s);
    float wb = clamp01f((float)w_b);

    int   best_idx = 0;
    float best_d2  = 1.0e30f;

    // ★基本15色だけを見る（0..14）
    for (int i = 0; i < MSX1PQ::kNumBasicColors; i++) {
        float dh = fabsf(h - g_palette_h[i]);
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
    return best_idx; // 0..14
}

// MSX1/MSX2 共通で「基本15色のパレット配列」を返す
static inline const MSX1PQ::QuantColor*
get_basic_palette(A_long color_system)
{
    return (color_system == MSX1PQ_COLOR_SYS_MSX2)
        ? MSX1PQ::kBasicColorsMsx2   // MSX2 用15色
        : MSX1PQ::kQuantColors;      // MSX1 用15色 (kQuantColors[0..14])
}

// RGB -> 基本15色インデックス (0..14)
static int
find_basic_index_from_rgb(A_u_char r, A_u_char g, A_u_char b, A_long color_system)
{
    const MSX1PQ::QuantColor* table = get_basic_palette(color_system);

    int  best_idx  = 0;
    long best_dist = 0x7fffffffL;

    for (int i = 0; i < MSX1PQ::kNumBasicColors; ++i) {
        long dr = (long)r - (long)table[i].r;
        long dg = (long)g - (long)table[i].g;
        long db = (long)b - (long)table[i].b;

        long d2 = dr*dr + dg*dg + db*db;
        if (d2 < best_dist) {
            best_dist = d2;
            best_idx  = i;
        }
    }
    return best_idx; // 0..14
}

// ---------------------------------------------------------------------------
// About
// ---------------------------------------------------------------------------

static PF_Err
About (
    PF_InData        *in_data,
    PF_OutData       *out_data,
    PF_ParamDef      *params[],
    PF_LayerDef      *output )
{
    PF_SPRINTF(out_data->return_msg,
               "%s, v%d.%d (%lu)\n%s",
               MSX1PQ::kPluginName,
               MSX1PQ::kVersionMajor,
               MSX1PQ::kVersionMinor,
               MSX1PQ::kVersionPacked,
               MSX1PQ::kPluginDescription);
    return PF_Err_NONE;
}

// ---------------------------------------------------------------------------
// GlobalSetup
// ---------------------------------------------------------------------------

static PF_Err
GlobalSetup (
    PF_InData        *in_dataP,
    PF_OutData       *out_data,
    PF_ParamDef      *params[],
    PF_LayerDef      *output )
{
    PF_Err    err = PF_Err_NONE;
    out_data->my_version = MSX1PQ::kVersionPacked;
    // MSX1PQ_DebugLog("my_version = %lu", (unsigned long)out_data->my_version);
    // 8bit専用: DEEP_COLOR_AWARE / FLOAT_COLOR_AWARE / SMART_RENDER は立てない
    // out_data->out_flags  =  PF_OutFlag_PIX_INDEPENDENT |
    //                         PF_OutFlag_NON_PARAM_VARY;

    // out_data->out_flags2 =  PF_OutFlag2_SUPPORTS_THREADED_RENDERING;

	out_data->out_flags  = PF_OutFlag_NONE;
	out_data->out_flags2 = PF_OutFlag2_NONE;
    // Premiere 用ピクセルフォーマット宣言
    if (in_dataP->appl_id == kAppID_Premiere){

        AEFX_SuiteScoper<PF_PixelFormatSuite1> pixelFormatSuite =
            AEFX_SuiteScoper<PF_PixelFormatSuite1>( in_dataP,
                                                    kPFPixelFormatSuite,
                                                    kPFPixelFormatSuiteVersion1,
                                                    out_data);

        // サポートするフォーマットだけ登録
        (*pixelFormatSuite->ClearSupportedPixelFormats)(in_dataP->effect_ref);
        (*pixelFormatSuite->AddSupportedPixelFormat)(
                                                        in_dataP->effect_ref,
                                                        PrPixelFormat_BGRA_4444_8u);
        // VUYA や 32f は今回はサポートしない
    }

    return err;
}

// ---------------------------------------------------------------------------
// ParamsSetup
// ---------------------------------------------------------------------------

static PF_Err
ParamsSetup (
    PF_InData        *in_data,
    PF_OutData       *out_data,
    PF_ParamDef      *params[],
    PF_LayerDef      *output)
{
    PF_Err err = PF_Err_NONE;
    PF_ParamDef def;

    // 入力レイヤーは暗黙に 0 番として存在するので何もしない
    AEFX_CLR_STRUCT(def);
    PF_ADD_POPUP(
        "Color system",
        2,                    // 項目数
        MSX1PQ_COLOR_SYS_MSX1,       // デフォルト 1: MSX1
        "MSX1|MSX2",
        MSX1PQ_PARAM_COLOR_SYSTEM);

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "Dither",            // 表示名
        "Use dithering",     // チェックON時のラベル
        TRUE,                // デフォルトON (TRUE: ディザ有効)
        0,
        MSX1PQ_PARAM_USE_DITHER
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "Use dark dither palettes",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_USE_DARK_DITHER
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_POPUP(
        "8-dot / 2-color",
        6,
        MSX1PQ_EIGHTDOT_MODE_BASIC1,
        "None|Fast|Basic|Best|Best-Attr|Best-Trans",
        MSX1PQ_PARAM_USE_8DOT2COL
    );

    AEFX_CLR_STRUCT(def);
    def.flags = PF_ParamFlag_SUPERVISE;
    PF_ADD_POPUP(
        "Distance mode",      // ラベル
        2,                    // 項目数
        MSX1PQ_DIST_MODE_HSB, // デフォルト値 (2 = HSB)
        "RGB|HSB",            // 順番に 1:RGB, 2:HSB
        MSX1PQ_PARAM_DISTANCE_MODE
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "H weight",           // 表示名
        0,                    //
        1,                    //
        0,                    // SLIDER_MIN
        1,                    // SLIDER_MAX
        1,                    // デフォルト値 1.0
        2,                    // 小数点以下2桁くらい
        0,                    // DISPLAY_FLAGS
        0,                    // 予約
        MSX1PQ_PARAM_WEIGHT_H
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "S weight",
        0,
        1,
        0,
        1,
        0.5,
        2,
        0,
        0,
        MSX1PQ_PARAM_WEIGHT_S
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "B weight",
        0,
        1,
        0,
        1,
        0.75,
        2,
        0,
        0,
        MSX1PQ_PARAM_WEIGHT_B
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "Pre 1: Saturation boost",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_PRE_SAT
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "Pre 2: Gamma (darker)",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_PRE_GAMMA
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "Pre 3: Highlight adjust",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_PRE_HIGHLIGHT
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "Pre 4: Skin tone bias",
        "Enable",
        FALSE,
        0,
        MSX1PQ_PARAM_PRE_SKIN
    );

    out_data->num_params = MSX1PQ_PARAM_NUM_PARAMS;

    return err;
}


// ------------------------------------------------------------
// 横8ドット内2色制限
// ------------------------------------------------------------


static void
apply_8dot2col_dispatch_ARGB(
    PF_Pixel8* data,
    A_long     row_pitch,
    A_long     width,
    A_long     height,
    A_long     color_system,
    A_long     mode)
{
    if (mode <= MSX1PQ_EIGHTDOT_MODE_NONE || mode >= 7) {
        return;
    }
    Apply8DotFn_ARGB fn = g_apply8dot_ARGB[mode];
    if (fn) {
        fn(data, row_pitch, width, height, color_system);
    }
}

static void
apply_8dot2col_dispatch_BGRA(
    MSX1PQ_Pixel_BGRA_8u* data,
    A_long            row_pitch,
    A_long            width,
    A_long            height,
    A_long            color_system,
    A_long            mode)
{
    if (mode <= MSX1PQ_EIGHTDOT_MODE_NONE || mode >= 7) {
        return;
    }
    Apply8DotFn_BGRA fn = g_apply8dot_BGRA[mode];
    if (fn) {
        fn(data, row_pitch, width, height, color_system);
    }
}

template<typename PixelT>
static void
apply_8dot2col_basic1(
    PixelT* data,
    A_long  row_pitch,
    A_long  width,
    A_long  height,
    A_long  color_system)
{
    if (!data || width <= 0 || height <= 0) {
        return;
    }

    const MSX1PQ::QuantColor* table = get_basic_palette(color_system);

    for (A_long y = 0; y < height; ++y) {

        PixelT* row = data + y * row_pitch;

        for (A_long bx = 0; bx * 8 < width; ++bx) {
            A_long x_start = bx * 8;
            A_long x_end   = x_start + 8;
            if (x_end > width) {
                x_end = width;
            }
            int block_w = (int)(x_end - x_start);
            if (block_w <= 0) continue;

            int counts[15] = {0};
            int idx_list[8];

            // 1) ブロック内の basic15 インデックスを取得＆カウント
            for (int i = 0; i < block_w; ++i) {
                PixelT& p = row[x_start + i];

                int idx = find_basic_index_from_rgb(
                    p.red, p.green, p.blue, color_system);

                if (idx < 0) idx = 0;
                if (idx >= MSX1PQ::kNumBasicColors) idx = MSX1PQ::kNumBasicColors - 1;

                idx_list[i] = idx;
                counts[idx]++;
            }

            // 2) 出現数 Top2
            int top1 = -1;
            int top2 = -1;
            for (int c = 0; c < MSX1PQ::kNumBasicColors; ++c) {
                int cnt = counts[c];
                if (cnt <= 0) continue;

                if (top1 < 0 || cnt > counts[top1]) {
                    top2 = top1;
                    top1 = c;
                } else if (top2 < 0 || cnt > counts[top2]) {
                    top2 = c;
                }
            }
            if (top1 < 0) continue;
            if (top2 < 0) top2 = top1;

            // 3) Top2 以外は “どちらに近いか” で寄せる
            for (int i = 0; i < block_w; ++i) {
                int idx = idx_list[i];
                int new_idx = idx;

                if (idx != top1 && idx != top2) {
                    const MSX1PQ::QuantColor& src = table[idx];
                    const MSX1PQ::QuantColor& c1  = table[top1];
                    const MSX1PQ::QuantColor& c2  = table[top2];

                    long dr1 = (long)src.r - (long)c1.r;
                    long dg1 = (long)src.g - (long)c1.g;
                    long db1 = (long)src.b - (long)c1.b;
                    long d1  = dr1*dr1 + dg1*dg1 + db1*db1;

                    long dr2 = (long)src.r - (long)c2.r;
                    long dg2 = (long)src.g - (long)c2.g;
                    long db2 = (long)src.b - (long)c2.b;
                    long d2  = dr2*dr2 + dg2*dg2 + db2*db2;

                    new_idx = (d1 <= d2) ? top1 : top2;
                }

                const MSX1PQ::QuantColor& qc = table[new_idx];
                PixelT& p = row[x_start + i];
                p.red   = qc.r;
                p.green = qc.g;
                p.blue  = qc.b;
            }
        }
    }
}

template<typename PixelT>
static void
apply_8dot2col_fast1(
    PixelT* data,
    A_long  row_pitch,
    A_long  width,
    A_long  height,
    A_long  /*color_system*/)
{
    if (!data || width <= 0 || height <= 0) {
        return;
    }

    for (A_long y = 0; y < height; ++y) {

        PixelT* row = data + y * row_pitch;

        for (A_long bx = 0; bx * 8 < width; ++bx) {
            A_long x_start = bx * 8;
            A_long x_end   = x_start + 8;
            if (x_end > width) {
                x_end = width;
            }
            int block_w = (int)(x_end - x_start);
            if (block_w <= 0) continue;

            struct ColorCount {
                A_u_char r, g, b;
                int      count;
            };

            ColorCount uniques[8];
            int        num_unique = 0;

            // 1) ブロック内のユニーク色を集計（最大 8 種類）
            for (int i = 0; i < block_w; ++i) {
                PixelT& p = row[x_start + i];

                int j;
                for (j = 0; j < num_unique; ++j) {
                    if (uniques[j].r == p.red &&
                        uniques[j].g == p.green &&
                        uniques[j].b == p.blue) {
                        uniques[j].count++;
                        break;
                    }
                }
                if (j == num_unique && num_unique < 8) {
                    uniques[num_unique].r = p.red;
                    uniques[num_unique].g = p.green;
                    uniques[num_unique].b = p.blue;
                    uniques[num_unique].count = 1;
                    ++num_unique;
                }
            }

            if (num_unique <= 1) {
                // もともと 0～1 色なら 2色制限の必要なし
                continue;
            }

            // 2) 出現数 Top2 を探す
            int top1 = 0;
            int top2 = 1;
            if (uniques[top2].count > uniques[top1].count) {
                int tmp = top1; top1 = top2; top2 = tmp;
            }
            for (int i = 2; i < num_unique; ++i) {
                int c = uniques[i].count;
                if (c > uniques[top1].count) {
                    top2 = top1;
                    top1 = i;
                } else if (c > uniques[top2].count) {
                    top2 = i;
                }
            }

            const ColorCount& c1 = uniques[top1];
            const ColorCount& c2 = uniques[top2];

            // 3) Top2 以外の色は “どちらに近いか” で寄せる
            for (int i = 0; i < block_w; ++i) {
                PixelT& p = row[x_start + i];

                // すでに top1 / top2 ならそのまま
                if ((p.red == c1.r && p.green == c1.g && p.blue == c1.b) ||
                    (p.red == c2.r && p.green == c2.g && p.blue == c2.b)) {
                    continue;
                }

                long dr1 = (long)p.red   - (long)c1.r;
                long dg1 = (long)p.green - (long)c1.g;
                long db1 = (long)p.blue  - (long)c1.b;
                long d1  = dr1*dr1 + dg1*dg1 + db1*db1;

                long dr2 = (long)p.red   - (long)c2.r;
                long dg2 = (long)p.green - (long)c2.g;
                long db2 = (long)p.blue  - (long)c2.b;
                long d2  = dr2*dr2 + dg2*dg2 + db2*db2;

                const ColorCount& c = (d1 <= d2) ? c1 : c2;
                p.red   = c.r;
                p.green = c.g;
                p.blue  = c.b;
            }
        }
    }
}

static const int BASIC_COLORS = 15;

template<typename PixelT>
static void apply_8dot2col_best1(
    PixelT* data,
    A_long  row_pitch,
    A_long  width,
    A_long  height,
    A_long  color_system)
{
    if (!data || width <= 0 || height <= 0) {
        return;
    }

    const MSX1PQ::QuantColor* table = get_basic_palette(color_system);

    for (A_long y = 0; y < height; ++y) {

        PixelT* row = data + y * row_pitch;

        for (A_long bx = 0; bx * 8 < width; ++bx) {

            A_long x_start = bx * 8;
            A_long x_end   = x_start + 8;
            if (x_end > width) {
                x_end = width;
            }
            int block_w = (int)(x_end - x_start);
            if (block_w <= 0) continue;

            // --- 1) ブロック内の basic15 インデックス集計 ---
            int counts[BASIC_COLORS] = {0};
            int idx_list[8] = {0};

            int unique_indices[8];
            int num_unique = 0;

            for (int i = 0; i < block_w; ++i) {
                PixelT& p = row[x_start + i];

                int idx = find_basic_index_from_rgb(
                    p.red, p.green, p.blue, color_system);

                if (idx < 0) idx = 0;
                if (idx >= BASIC_COLORS) idx = BASIC_COLORS - 1;

                idx_list[i] = idx;

                if (counts[idx] == 0 && num_unique < 8) {
                    unique_indices[num_unique++] = idx;
                }
                counts[idx]++;
            }

            if (num_unique <= 2) continue;

            // --- 2) 距離テーブル（15×15 固定） ---
            long dist2[BASIC_COLORS][BASIC_COLORS];

            for (int i = 0; i < BASIC_COLORS; ++i) {
                const MSX1PQ::QuantColor& ci = table[i];
                for (int j = 0; j < BASIC_COLORS; ++j) {
                    const MSX1PQ::QuantColor& cj = table[j];
                    long dr = (long)ci.r - (long)cj.r;
                    long dg = (long)ci.g - (long)cj.g;
                    long db = (long)ci.b - (long)cj.b;
                    dist2[i][j] = dr*dr + dg*dg + db*db;
                }
            }

            // --- 3) unique 2色ペア最適化 ---
            long best_error = LONG_MAX;
            int  best_a = unique_indices[0];
            int  best_b = unique_indices[1];

            for (int ua = 0; ua < num_unique; ++ua) {
                for (int ub = ua + 1; ub < num_unique; ++ub) {
                    int a = unique_indices[ua];
                    int b = unique_indices[ub];

                    long err = 0;

                    for (int uk = 0; uk < num_unique; ++uk) {
                        int k = unique_indices[uk];
                        int cnt = counts[k];
                        if (!cnt) continue;

                        long dA = dist2[k][a];
                        long dB = dist2[k][b];
                        long d  = (dA < dB) ? dA : dB;

                        err += (long)cnt * d;
                    }

                    if (err < best_error) {
                        best_error = err;
                        best_a = a;
                        best_b = b;
                    }
                }
            }

            // --- 4) best_a/best_b に寄せる ---
            for (int i = 0; i < block_w; ++i) {
                int src_idx = idx_list[i];

                long dA = dist2[src_idx][best_a];
                long dB = dist2[src_idx][best_b];
                int  new_idx = (dA <= dB) ? best_a : best_b;

                const MSX1PQ::QuantColor& qc = table[new_idx];
                PixelT& p = row[x_start + i];
                p.red   = qc.r;
                p.green = qc.g;
                p.blue  = qc.b;
            }
        }
    }
}


static const int ATTRCELL_HEIGHT   = 8;
// 4 or 8 で調整
// 4：滑らかさ控えめ、解像感優先
// 8：属性セル感強め

static const double ATTR_LAMBDA    = 0.3;
// 0.1?0.2：行の見た目優先（属性セル効果はほんのり）
// 0.3↑：セル全体の傾向がかなり効いてくる

template<typename PixelT>
static void apply_8dot2col_attr_best(
    PixelT* data,
    A_long  row_pitch,
    A_long  width,
    A_long  height,
    A_long  color_system)
{
    if (!data || width <= 0 || height <= 0) {
        return;
    }

    const MSX1PQ::QuantColor* table = get_basic_palette(color_system);

    // 15×15 距離テーブル（セル内共通）
    long dist2[BASIC_COLORS][BASIC_COLORS];
    for (int i = 0; i < BASIC_COLORS; ++i) {
        const MSX1PQ::QuantColor& ci = table[i];
        for (int j = 0; j < BASIC_COLORS; ++j) {
            const MSX1PQ::QuantColor& cj = table[j];
            long dr = (long)ci.r - (long)cj.r;
            long dg = (long)ci.g - (long)cj.g;
            long db = (long)ci.b - (long)cj.b;
            dist2[i][j] = dr*dr + dg*dg + db*db;
        }
    }

    const A_long num_blocks_x = (width + 7) / 8;

    // 縦方向を ATTRCELL_HEIGHT ごとに「属性セル」に分ける
    for (A_long y0 = 0; y0 < height; y0 += ATTRCELL_HEIGHT) {

        A_long cell_h = ATTRCELL_HEIGHT;
        if (y0 + cell_h > height) {
            cell_h = height - y0;
        }
        if (cell_h <= 0) break;

        // 各セル内で、x 方向の 8dot ブロックごとに処理
        for (A_long bx = 0; bx < num_blocks_x; ++bx) {

            A_long x_start = bx * 8;
            if (x_start >= width) break;
            A_long x_end   = x_start + 8;
            if (x_end > width) {
                x_end = width;
            }
            int block_w = (int)(x_end - x_start);
            if (block_w <= 0) continue;

            // --- (1) このセル＆この 8dot 縦帯の basic15 ヒストグラム ---
            int cell_counts[BASIC_COLORS] = {0};

            for (A_long yy = 0; yy < cell_h; ++yy) {
                PixelT* row = data + (y0 + yy) * row_pitch;
                for (int i = 0; i < block_w; ++i) {
                    PixelT& p = row[x_start + i];

                    int idx = find_basic_index_from_rgb(
                        p.red, p.green, p.blue, color_system);
                    if (idx < 0) idx = 0;
                    if (idx >= BASIC_COLORS) idx = BASIC_COLORS - 1;

                    cell_counts[idx]++;
                }
            }

            // --- (2) セル内の各行 8×1 ブロックごとに 2色ペアを選ぶ ---
            for (A_long yy = 0; yy < cell_h; ++yy) {
                A_long y = y0 + yy;
                PixelT* row = data + y * row_pitch;

                int block_counts[BASIC_COLORS] = {0};
                int idx_list[8];

                // この行の 8×1 ブロック内 basic15 集計
                for (int i = 0; i < block_w; ++i) {
                    PixelT& p = row[x_start + i];

                    int idx = find_basic_index_from_rgb(
                        p.red, p.green, p.blue, color_system);
                    if (idx < 0) idx = 0;
                    if (idx >= BASIC_COLORS) idx = BASIC_COLORS - 1;

                    idx_list[i] = idx;
                    block_counts[idx]++;
                }

                // unique な色インデックスを列挙（最大 8 種類）
                int unique_indices[8];
                int num_unique = 0;
                for (int k = 0; k < BASIC_COLORS && num_unique < 8; ++k) {
                    if (block_counts[k] > 0) {
                        unique_indices[num_unique++] = k;
                    }
                }
                if (num_unique <= 1) {
                    // もともと 1色なら 2色制限する必要なし
                    continue;
                }

                double best_score = 0.0;
                bool   first      = true;
                int    best_a     = unique_indices[0];
                int    best_b     = unique_indices[1];

                for (int ua = 0; ua < num_unique; ++ua) {
                    for (int ub = ua + 1; ub < num_unique; ++ub) {

                        int a = unique_indices[ua];
                        int b = unique_indices[ub];

                        // --- err_block: この行(8×1)の誤差 ---
                        long err_block = 0;
                        for (int k = 0; k < BASIC_COLORS; ++k) {
                            int cnt = block_counts[k];
                            if (!cnt) continue;

                            long dA = dist2[k][a];
                            long dB = dist2[k][b];
                            long d  = (dA < dB) ? dA : dB;

                            err_block += (long)cnt * d;
                        }

                        // --- err_cell: このセル全体(8×N)の誤差 ---
                        long err_cell = 0;
                        for (int k = 0; k < BASIC_COLORS; ++k) {
                            int cnt = cell_counts[k];
                            if (!cnt) continue;

                            long dA = dist2[k][a];
                            long dB = dist2[k][b];
                            long d  = (dA < dB) ? dA : dB;

                            err_cell += (long)cnt * d;
                        }

                        double score =
                            (double)err_block +
                            ATTR_LAMBDA * (double)err_cell;  // ← 属性セル寄せ

                        if (first || score < best_score) {
                            first      = false;
                            best_score = score;
                            best_a     = a;
                            best_b     = b;
                        }
                    }
                }

                // --- 選ばれた best_a/best_b で、この行の 8×1 ブロックだけを丸める ---
                for (int i = 0; i < block_w; ++i) {
                    int src_idx = idx_list[i];

                    long dA = dist2[src_idx][best_a];
                    long dB = dist2[src_idx][best_b];
                    int  new_idx = (dA <= dB) ? best_a : best_b;

                    const MSX1PQ::QuantColor& qc = table[new_idx];
                    PixelT& p = row[x_start + i];
                    p.red   = qc.r;
                    p.green = qc.g;
                    p.blue  = qc.b;
                }
            }
        }
    }
}


static const double TRANSITION_LAMBDA = 0.5;
// 0.3?1.0 の間で調整用
// 0.3?0.5：静止画と動画のバランス良い感じ
// 0.8?1.0：動画向け・横方向のガチャつきかなり抑制

static inline int transition_cost_pair(int prevA, int prevB, int a, int b)
{
    if (prevA < 0 || prevB < 0) {
        return 0; // 1列目はペナルティ無し
    }

    // 同じ順序
    if (a == prevA && b == prevB) {
        return 0;
    }
    // 入れ替えだけ
    if (a == prevB && b == prevA) {
        return 1;
    }

    bool share =
        (a == prevA) || (a == prevB) ||
        (b == prevA) || (b == prevB);

    if (share) {
        return 3;   // 片方だけ同じ
    }
    return 5;       // 両方違う
}

template<typename PixelT>
static void apply_8dot2col_attr_best_penalty(
    PixelT* data,
    A_long  row_pitch,
    A_long  width,
    A_long  height,
    A_long  color_system)
{
    if (!data || width <= 0 || height <= 0) {
        return;
    }

    const MSX1PQ::QuantColor* table = get_basic_palette(color_system);

    long dist2[BASIC_COLORS][BASIC_COLORS];
    for (int i = 0; i < BASIC_COLORS; ++i) {
        const MSX1PQ::QuantColor& ci = table[i];
        for (int j = 0; j < BASIC_COLORS; ++j) {
            const MSX1PQ::QuantColor& cj = table[j];
            long dr = (long)ci.r - (long)cj.r;
            long dg = (long)ci.g - (long)cj.g;
            long db = (long)ci.b - (long)cj.b;
            dist2[i][j] = dr*dr + dg*dg + db*db;
        }
    }

    const A_long num_blocks_x = (width + 7) / 8;

    // 縦方向は ATTRCELL_HEIGHT ごとに属性セルで区切る
    for (A_long y0 = 0; y0 < height; y0 += ATTRCELL_HEIGHT) {

        A_long cell_h = ATTRCELL_HEIGHT;
        if (y0 + cell_h > height) {
            cell_h = height - y0;
        }
        if (cell_h <= 0) break;

        // セル内の各行
        for (A_long yy = 0; yy < cell_h; ++yy) {

            A_long y = y0 + yy;
            PixelT* row = data + y * row_pitch;

            int prevA = -1;
            int prevB = -1;  // 左ブロックの 2色ペア

            // 横方向に 8dot ブロックを走査
            for (A_long bx = 0; bx < num_blocks_x; ++bx) {

                A_long x_start = bx * 8;
                if (x_start >= width) break;
                A_long x_end   = x_start + 8;
                if (x_end > width) {
                    x_end = width;
                }
                int block_w = (int)(x_end - x_start);
                if (block_w <= 0) continue;

                // --- (1) この行 8×1 ブロックの basic15 集計 ---
                int block_counts[BASIC_COLORS] = {0};
                int idx_list[8];

                for (int i = 0; i < block_w; ++i) {
                    PixelT& p = row[x_start + i];

                    int idx = find_basic_index_from_rgb(
                        p.red, p.green, p.blue, color_system);
                    if (idx < 0) idx = 0;
                    if (idx >= BASIC_COLORS) idx = BASIC_COLORS - 1;

                    idx_list[i] = idx;
                    block_counts[idx]++;
                }

                int unique_indices[8];
                int num_unique = 0;
                for (int k = 0; k < BASIC_COLORS && num_unique < 8; ++k) {
                    if (block_counts[k] > 0) {
                        unique_indices[num_unique++] = k;
                    }
                }
                if (num_unique <= 1) {
                    // 1色ならそのまま
                    continue;
                }

                // --- (2) このセル＆このブロックの「縦帯」ヒストグラム ---
                int cell_counts[BASIC_COLORS] = {0};
                for (A_long yyc = 0; yyc < cell_h; ++yyc) {
                    PixelT* rowc = data + (y0 + yyc) * row_pitch;
                    for (int i = 0; i < block_w; ++i) {
                        PixelT& p = rowc[x_start + i];

                        int idx = find_basic_index_from_rgb(
                            p.red, p.green, p.blue, color_system);
                        if (idx < 0) idx = 0;
                        if (idx >= BASIC_COLORS) idx = BASIC_COLORS - 1;

                        cell_counts[idx]++;
                    }
                }

                // --- (3) 2色ペア候補を総当たり：block + cell + 横ペナルティ ---
                double best_score = 0.0;
                bool   first      = true;
                int    best_a     = unique_indices[0];
                int    best_b     = unique_indices[1];

                for (int ua = 0; ua < num_unique; ++ua) {
                    for (int ub = ua + 1; ub < num_unique; ++ub) {

                        int a = unique_indices[ua];
                        int b = unique_indices[ub];

                        // err_block
                        long err_block = 0;
                        for (int k = 0; k < BASIC_COLORS; ++k) {
                            int cnt = block_counts[k];
                            if (!cnt) continue;

                            long dA = dist2[k][a];
                            long dB = dist2[k][b];
                            long d  = (dA < dB) ? dA : dB;

                            err_block += (long)cnt * d;
                        }

                        // err_cell
                        long err_cell = 0;
                        for (int k = 0; k < BASIC_COLORS; ++k) {
                            int cnt = cell_counts[k];
                            if (!cnt) continue;

                            long dA = dist2[k][a];
                            long dB = dist2[k][b];
                            long d  = (dA < dB) ? dA : dB;

                            err_cell += (long)cnt * d;
                        }

                        int tc_h = transition_cost_pair(prevA, prevB, a, b);

                        double score =
                            (double)err_block +
                            ATTR_LAMBDA       * (double)err_cell +
                            TRANSITION_LAMBDA * (double)tc_h;

                        if (first || score < best_score) {
                            first      = false;
                            best_score = score;
                            best_a     = a;
                            best_b     = b;
                        }
                    }
                }

                // --- (4) 選ばれたペアでこの行 8×1 ブロックだけを丸める ---
                for (int i = 0; i < block_w; ++i) {
                    int src_idx = idx_list[i];

                    long dA = dist2[src_idx][best_a];
                    long dB = dist2[src_idx][best_b];
                    int  new_idx = (dA <= dB) ? best_a : best_b;

                    const MSX1PQ::QuantColor& qc = table[new_idx];
                    PixelT& p = row[x_start + i];
                    p.red   = qc.r;
                    p.green = qc.g;
                    p.blue  = qc.b;
                }

                // 左ブロックのペアとして保存（横方向ペナルティ用）
                prevA = best_a;
                prevB = best_b;
            }
        }
    }
}

// ---------------------------------------------------------------------------
// 8bit ARGB (AE用) 量子化
// ---------------------------------------------------------------------------

static PF_Err
FilterImage8 (
    void        *refcon,
    A_long      xL,
    A_long      yL,
    PF_Pixel8   *inP,
    PF_Pixel8   *outP)
{
    QuantInfo *qi = reinterpret_cast<QuantInfo*>(refcon);

    // 入力色をローカルコピー
    A_u_char r = inP->red;
    A_u_char g = inP->green;
    A_u_char b = inP->blue;

    // 1?4 の前処理
    apply_preprocess(qi, r, g, b);

    int basic_idx = 0;

    if (qi && qi->use_dither) {
        // どこまでのパレットを使うか
        int num_colors = MSX1PQ::kNumQuantColors;
        if (!qi->use_dark_dither) {
            num_colors = MSX1PQ::kFirstDarkDitherIndex; // 低輝度パレットを除外
        }

        int palette_idx;
        if (qi->use_hsb) {
            palette_idx = nearest_palette_hsb(
                r, g, b,
                qi->w_h, qi->w_s, qi->w_b,
                num_colors);
        } else {
            palette_idx = nearest_palette_rgb(
                r, g, b,
                num_colors);
        }

        basic_idx = MSX1PQ::palette_index_to_basic_index(
            palette_idx,
            static_cast<std::int32_t>(xL),
            static_cast<std::int32_t>(yL));
    } else {
        // ディザOFF: 直接15色へ
        if (qi && qi->use_hsb) {
            basic_idx = nearest_basic_hsb(
                r, g, b,
                qi->w_h, qi->w_s, qi->w_b);
        } else {
            basic_idx = MSX1PQ::nearest_basic_rgb(
                r, g, b);
        }
    }

    const MSX1PQ::QuantColor &qc =
        (qi->color_system == MSX1PQ_COLOR_SYS_MSX2)
        ? MSX1PQ::kBasicColorsMsx2[basic_idx]
        : MSX1PQ::kQuantColors[basic_idx];

    outP->alpha = inP->alpha;
    outP->red   = qc.r;
    outP->green = qc.g;
    outP->blue  = qc.b;

    return PF_Err_NONE;
}

// ---------------------------------------------------------------------------
// 8bit BGRA (Premiere用) 量子化
// ---------------------------------------------------------------------------
static PF_Err
FilterImageBGRA_8u (
    void        *refcon,
    A_long      xL,
    A_long      yL,
    PF_Pixel8   *inP,
    PF_Pixel8   *outP)
{
    QuantInfo *qi = reinterpret_cast<QuantInfo*>(refcon);

    MSX1PQ_Pixel_BGRA_8u *inBGRA_8uP  = reinterpret_cast<MSX1PQ_Pixel_BGRA_8u*>(inP);
    MSX1PQ_Pixel_BGRA_8u *outBGRA_8uP = reinterpret_cast<MSX1PQ_Pixel_BGRA_8u*>(outP);

    A_u_char r = inBGRA_8uP->red;
    A_u_char g = inBGRA_8uP->green;
    A_u_char b = inBGRA_8uP->blue;

    apply_preprocess(qi, r, g, b);

    int basic_idx = 0;

    if (qi && qi->use_dither) {
        int num_colors = MSX1PQ::kNumQuantColors;
        if (!qi->use_dark_dither) {
            num_colors = MSX1PQ::kFirstDarkDitherIndex;
        }

        int palette_idx;
        if (qi->use_hsb) {
            palette_idx = nearest_palette_hsb(
                r, g, b,
                qi->w_h, qi->w_s, qi->w_b,
                num_colors);
        } else {
            palette_idx = nearest_palette_rgb(
                r, g, b,
                num_colors);
        }

        basic_idx = MSX1PQ::palette_index_to_basic_index(
            palette_idx,
            static_cast<std::int32_t>(xL),
            static_cast<std::int32_t>(yL));
    } else {
        if (qi && qi->use_hsb) {
            basic_idx = nearest_basic_hsb(
                r, g, b,
                qi->w_h, qi->w_s, qi->w_b);
        } else {
            basic_idx = MSX1PQ::nearest_basic_rgb(
                r, g, b);
        }
    }

    const MSX1PQ::QuantColor &qc =
        (qi->color_system == MSX1PQ_COLOR_SYS_MSX2)
            ? MSX1PQ::kBasicColorsMsx2[basic_idx]  // ★ MSX2 の 15色
            : MSX1PQ::kQuantColors[basic_idx];     // ★ MSX1 の 15色

    outBGRA_8uP->alpha = inBGRA_8uP->alpha;
    outBGRA_8uP->red   = qc.r;
    outBGRA_8uP->green = qc.g;
    outBGRA_8uP->blue  = qc.b;

    return PF_Err_NONE;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------
static PF_Err
Render (
    PF_InData        *in_dataP,
    PF_OutData       *out_data,
    PF_ParamDef      *params[],
    PF_LayerDef      *output )
{
    PF_Err  err    = PF_Err_NONE;
    A_long  linesL = output->extent_hint.bottom - output->extent_hint.top;

    // ---- パラメータ読み取り ----
    QuantInfo qi;
    qi.color_system    = params[MSX1PQ_PARAM_COLOR_SYSTEM]->u.pd.value;
    qi.use_dither      = (params[MSX1PQ_PARAM_USE_DITHER]->u.bd.value != 0);
    qi.use_8dot2col    = params[MSX1PQ_PARAM_USE_8DOT2COL]->u.pd.value;
    qi.use_hsb         = (params[MSX1PQ_PARAM_DISTANCE_MODE]->u.pd.value == MSX1PQ_DIST_MODE_HSB);

    qi.w_h = params[MSX1PQ_PARAM_WEIGHT_H]->u.fs_d.value;
    qi.w_s = params[MSX1PQ_PARAM_WEIGHT_S]->u.fs_d.value;
    qi.w_b = params[MSX1PQ_PARAM_WEIGHT_B]->u.fs_d.value;

    qi.w_h = clamp01f((float)qi.w_h);
    qi.w_s = clamp01f((float)qi.w_s);
    qi.w_b = clamp01f((float)qi.w_b);

    qi.pre_sat       = (params[MSX1PQ_PARAM_PRE_SAT]->u.bd.value       != 0);
    qi.pre_gamma     = (params[MSX1PQ_PARAM_PRE_GAMMA]->u.bd.value     != 0);
    qi.pre_highlight = (params[MSX1PQ_PARAM_PRE_HIGHLIGHT]->u.bd.value != 0);
    qi.pre_skin      = (params[MSX1PQ_PARAM_PRE_SKIN]->u.bd.value      != 0);

    qi.use_dark_dither = (params[MSX1PQ_PARAM_USE_DARK_DITHER]->u.bd.value != 0);

    // 画像サイズ（extent_hint ベース）
    const A_long width  = output->extent_hint.right  - output->extent_hint.left;
    const A_long height = output->extent_hint.bottom - output->extent_hint.top;

    if (in_dataP->appl_id == kAppID_Premiere) {

        AEFX_SuiteScoper<PF_PixelFormatSuite1> pixelFormatSuite(
            in_dataP,
            kPFPixelFormatSuite,
            kPFPixelFormatSuiteVersion1,
            out_data);

        PrPixelFormat destinationPixelFormat = PrPixelFormat_BGRA_4444_8u;
        pixelFormatSuite->GetPixelFormat(output, &destinationPixelFormat);

        if (destinationPixelFormat == PrPixelFormat_BGRA_4444_8u) {

            // ---- 1パス目：通常の量子化（ディザなど）----
            AEFX_SuiteScoper<PF_Iterate8Suite2> iterate8Suite(
                in_dataP,
                kPFIterate8Suite,
                kPFIterate8SuiteVersion2,
                out_data);

            iterate8Suite->iterate(
                in_dataP,
                0,
                linesL,
                &params[MSX1PQ_PARAM_INPUT]->u.ld,
                NULL,
                &qi,
                FilterImageBGRA_8u,
                output);

            // ---- 2パス目：8dot / 2color 後処理（基本1）----
            if (!err && qi.use_8dot2col != MSX1PQ_EIGHTDOT_MODE_NONE) {

                // すでに width / height は上で計算済みでもOKですが、
                // 明示しておくならこのままでも大丈夫です。
                A_long width  = output->extent_hint.right  - output->extent_hint.left;
                A_long height = output->extent_hint.bottom - output->extent_hint.top;

                // BGRA_4444_8u 用のピッチ
                A_long row_pitch = output->rowbytes / sizeof(MSX1PQ_Pixel_BGRA_8u);

                MSX1PQ_Pixel_BGRA_8u* base =
                    reinterpret_cast<MSX1PQ_Pixel_BGRA_8u*>(output->data);

                MSX1PQ_Pixel_BGRA_8u* data =
                    base + output->extent_hint.top * row_pitch
                         + output->extent_hint.left;

                apply_8dot2col_dispatch_BGRA(
                    data,
                    row_pitch,
                    width,
                    height,
                    qi.color_system,
                    qi.use_8dot2col);
            }


        } else {
            err = PF_Err_UNRECOGNIZED_PARAM_TYPE;
        }

    } else {
        // AE: ARGB32 8bit

        // ---- 1パス目：通常の量子化 ----
        AEFX_SuiteScoper<PF_Iterate8Suite2> iterate8Suite(
            in_dataP,
            kPFIterate8Suite,
            kPFIterate8SuiteVersion2,
            out_data);

        iterate8Suite->iterate(
            in_dataP,
            0,
            linesL,
            &params[MSX1PQ_PARAM_INPUT]->u.ld,
            NULL,
            &qi,
            FilterImage8,
            output);

        // ---- 2パス目：8dot / 2color 後処理（基本1）----
        if (!err && qi.use_8dot2col != MSX1PQ_EIGHTDOT_MODE_NONE) {

            A_long row_bytes = output->rowbytes;
            A_long row_pitch = (row_bytes >= 0)
                ? (row_bytes / (A_long)sizeof(PF_Pixel8))
                : ((-row_bytes) / (A_long)sizeof(PF_Pixel8));

            PF_Pixel8* start =
                reinterpret_cast<PF_Pixel8*>(output->data);

            // rowbytes < 0（上から下ではなく下から上）に備えた補正
            if (row_bytes < 0) {
                start = reinterpret_cast<PF_Pixel8*>(
                    reinterpret_cast<char*>(output->data)
                    + (height - 1) * (-row_bytes));
            }

            apply_8dot2col_dispatch_ARGB(
                start,
                row_pitch,
                width,
                height,
                qi.color_system,
                qi.use_8dot2col);
        }
    }

    return err;
}

// ---------------------------------------------------------------------------
// エントリ登録
// ---------------------------------------------------------------------------

extern "C" DllExport
PF_Err PluginDataEntryFunction2(
    PF_PluginDataPtr inPtr,
    PF_PluginDataCB2 inPluginDataCallBackPtr,
    SPBasicSuite* inSPBasicSuitePtr,
    const char* inHostName,
    const char* inHostVersion)
{
    PF_Err result = PF_Err_INVALID_CALLBACK;

    result = PF_REGISTER_EFFECT_EXT2(
        inPtr,
        inPluginDataCallBackPtr,
        "MSX1PaletteQuantizer", // Name
        "MMSXX_MSX1PaletteQuantizer", // Match Name
        "MMSXX",     // Category
        AE_RESERVED_INFO, // Reserved Info
        "EffectMain", // Entry point
        "https://www.example.com"); // support URL

    return result;
}


static PF_Err
UpdateParameterUI(
    PF_InData   *in_data,
    PF_OutData  *out_data,
    PF_ParamDef *params[])
{
    PF_Err err = PF_Err_NONE;

    // ParamUtilsSuite3 を取る
    AEFX_SuiteScoper<PF_ParamUtilsSuite3> paramUtils(
        in_data,
        kPFParamUtilsSuite,
        kPFParamUtilsSuiteVersion3,
        out_data);

    A_long mode = params[MSX1PQ_PARAM_DISTANCE_MODE]->u.pd.value;
    A_Boolean enable_hsb = (mode == MSX1PQ_DIST_MODE_HSB);

    // MSX1PQ_DebugLog("=== UpdateParameterUI CALLED ===");
    // MSX1PQ_DebugLog("UpdateParameterUI: mode=%ld enable_hsb=%d",
    //          mode, enable_hsb ? 1 : 0);

    PF_ParamDef tmp;

    // --- H weight ---
    tmp = *params[MSX1PQ_PARAM_WEIGHT_H];
    if (enable_hsb)
        tmp.ui_flags &= ~PF_PUI_DISABLED;
    else
        tmp.ui_flags |= PF_PUI_DISABLED;
    // MSX1PQ_DebugLog("  H ui_flags(new)=0x%08x", tmp.ui_flags);
    paramUtils->PF_UpdateParamUI(in_data->effect_ref,
                                 MSX1PQ_PARAM_WEIGHT_H,
                                 &tmp);

    // --- S weight ---
    tmp = *params[MSX1PQ_PARAM_WEIGHT_S];
    if (enable_hsb)
        tmp.ui_flags &= ~PF_PUI_DISABLED;
    else
        tmp.ui_flags |= PF_PUI_DISABLED;
    // MSX1PQ_DebugLog("  S ui_flags(new)=0x%08x", tmp.ui_flags);
    paramUtils->PF_UpdateParamUI(in_data->effect_ref,
                                 MSX1PQ_PARAM_WEIGHT_S,
                                 &tmp);

    // --- B weight ---
    tmp = *params[MSX1PQ_PARAM_WEIGHT_B];
    if (enable_hsb)
        tmp.ui_flags &= ~PF_PUI_DISABLED;
    else
        tmp.ui_flags |= PF_PUI_DISABLED;
    // MSX1PQ_DebugLog("  B ui_flags(new)=0x%08x", tmp.ui_flags);
    paramUtils->PF_UpdateParamUI(in_data->effect_ref,
                                 MSX1PQ_PARAM_WEIGHT_B,
                                 &tmp);

    // MSX1PQ_DebugLog("-> UpdateParameterUI done");

    return err;
}


PF_Err
EffectMain(
    PF_Cmd         cmd,
    PF_InData      *in_dataP,
    PF_OutData     *out_data,
    PF_ParamDef    *params[],
    PF_LayerDef    *output,
    void           *extra)
{
    PF_Err  err = PF_Err_NONE;

    try {
        switch (cmd)
        {
            case PF_Cmd_ABOUT:
                err = About(in_dataP, out_data, params, output);
                break;
            case PF_Cmd_GLOBAL_SETUP:
                err = GlobalSetup(in_dataP, out_data, params, output);
                break;
            // case PF_Cmd_UPDATE_PARAMS_UI:
            //     return UpdateParameterUI(in_dataP, out_data, params);
            case PF_Cmd_PARAMS_SETUP:
                err = ParamsSetup(in_dataP, out_data, params, output);
                break;
            case PF_Cmd_USER_CHANGED_PARAM:
            {
                PF_UserChangedParamExtra *extraP =
                    reinterpret_cast<PF_UserChangedParamExtra*>(extra);

                if (extraP->param_index == MSX1PQ_PARAM_DISTANCE_MODE) {
                    UpdateParameterUI(in_dataP, out_data, params);
                }

                break;
            }
            case PF_Cmd_RENDER:
                err = Render(in_dataP, out_data, params, output);
                break;
            // SMART_RENDER / SMART_PRE_RENDER は 8bit専用につき未対応
        }
    } catch(PF_Err &thrown_err) {
        // AE に例外を飛ばさない
        err = thrown_err;
    }
    return err;
}
