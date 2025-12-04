/*
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

#include <cstddef>
#include <algorithm>
#include <cstdarg>
#include <cstdio>


#ifdef AE_OS_WIN
#include <Windows.h>
static inline void MyDebugLog(const char* fmt, ...)
{
    char buf[512];

    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);

    OutputDebugStringA(buf);
    // OutputDebugStringA("\n");
}
#else
// Mac の場合（AE_OS_WIN が未定義）
static inline void MyDebugLog(const char* fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    std::vfprintf(stderr, fmt, args);
    std::fprintf(stderr, "\n");
    va_end(args);
}
#endif

namespace MSX1PQ {
    constexpr char kPluginName[]        = "MSX1 Palette Quantizer";
    constexpr char kPluginDescription[] = "\nMSX1-style palette quantization and dithering.";
    constexpr int  kVersionMajor        = 0;
    constexpr int  kVersionMinor        = 7;
    constexpr int  kVersionBug          = 0;
    constexpr int  kVersionStage        = PF_Stage_BETA;
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

using MSX1PQCore::QuantInfo;
using MSX1PQCore::apply_preprocess;
using MSX1PQCore::find_basic_index_from_rgb;
using MSX1PQCore::get_basic_palette;
using MSX1PQCore::nearest_basic_hsb;
using MSX1PQCore::nearest_palette_hsb;
using MSX1PQCore::nearest_palette_rgb;
using MSX1PQCore::quantize_pixel;
using MSX1PQCore::clamp01f;
using MSX1PQCore::clamp_value;
using MSX1PQCore::MSX1PQ_COLOR_SYS_MSX1;
using MSX1PQCore::MSX1PQ_COLOR_SYS_MSX2;
using MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_ATTR_BEST;
using MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BASIC1;
using MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BEST1;
using MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_FAST1;
using MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_NONE;
using MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_PENALTY_BEST;
using MSX1PQCore::MSX1PQ_DIST_MODE_HSB;
using MSX1PQCore::MSX1PQ_DIST_MODE_RGB;

namespace {

static inline PF_Err CheckoutParam(
    PF_InData     *in_data,
    PF_ParamIndex  param_index,
    PF_ParamDef   &param)
{
    AEFX_CLR_STRUCT(param);

    return PF_CHECKOUT_PARAM(
        in_data,
        param_index,
        in_data->current_time,
        in_data->time_step,
        in_data->time_scale,
        &param);
}

static inline PF_Err CheckinParam(
    PF_InData   *in_data,
    PF_ParamDef &param)
{
    return PF_CHECKIN_PARAM(in_data, &param);
}


} // namespace

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
    // MyDebugLog("my_version = %lu", (unsigned long)out_data->my_version);

        out_data->out_flags  = PF_OutFlag_NONE;
        out_data->out_flags2 = PF_OutFlag2_SUPPORTS_SMART_RENDER |
                               PF_OutFlag2_SUPPORTS_THREADED_RENDERING;
    //PF_OutFlag2_SUPPORTS_SMART_RENDER = 0x0400
    //PF_OutFlag2_SUPPORTS_THREADED_RENDERING = 0x08000000?
    MyDebugLog("GlobalSetup: out_flags=0x%08X, out_flags2=0x%08X",
                    (unsigned int)out_data->out_flags,
                    (unsigned int)out_data->out_flags2); //この値を rファイルに書く 0x08000400

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

    AEFX_CLR_STRUCT(def);
    // 入力レイヤーは暗黙に 0 番として存在するので何もしない
    // Premiere ではデフォルト固定のため変更不可
    if (in_data->appl_id == kAppID_Premiere) {
        def.ui_flags |= PF_PUI_DISABLED;
    }
    def.flags    |= PF_ParamFlag_CANNOT_TIME_VARY;
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
    PF_ADD_FLOAT_SLIDERX(
        "Pre 1: Posterize",
        0,
        255,
        0,
        255,
        16,
        0,
        0,
        0,
        MSX1PQ_PARAM_PRE_POSTERIZE
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "Pre 2: Saturation boost",
        0,
        10,
        0,
        10,
        1,
        2,
        0,
        0,
        MSX1PQ_PARAM_PRE_SAT
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "Pre 3: Gamma (darker)",
        0,
        10,
        0,
        10,
        1,
        2,
        0,
        0,
        MSX1PQ_PARAM_PRE_GAMMA
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "Pre 4: Highlight adjust",
        0,
        10,
        0,
        10,
        1,
        2,
        0,
        0,
        MSX1PQ_PARAM_PRE_HIGHLIGHT
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "Pre 5: Hue rotate",
        -180,
        180,
        -180,
        180,
        0,
        0,
        0,
        0,
        MSX1PQ_PARAM_PRE_HUE
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "Pre 6: Sharpen",
        0,
        1,
        0,
        1,
        0,
        2,
        0,
        0,
        MSX1PQ_PARAM_PRE_SHARPEN
    );

    AEFX_CLR_STRUCT(def);
    def.flags    |= PF_ParamFlag_CANNOT_TIME_VARY;
    PF_ADD_CHECKBOX(
        "92-color",
        "for development use",
        FALSE,
        0,
        MSX1PQ_PARAM_USE_PALETTE_COLOR
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

    const auto pitch = static_cast<std::ptrdiff_t>(row_pitch);
    const auto w     = static_cast<std::int32_t>(width);
    const auto h     = static_cast<std::int32_t>(height);
    const int  cs    = static_cast<int>(color_system);

    switch (mode) {
    case MSX1PQ_EIGHTDOT_MODE_FAST1:
        MSX1PQCore::apply_8dot2col_fast1(data, pitch, w, h, cs);
        break;
    case MSX1PQ_EIGHTDOT_MODE_BASIC1:
        MSX1PQCore::apply_8dot2col_basic1(data, pitch, w, h, cs);
        break;
    case MSX1PQ_EIGHTDOT_MODE_BEST1:
        MSX1PQCore::apply_8dot2col_best1(data, pitch, w, h, cs);
        break;
    case MSX1PQ_EIGHTDOT_MODE_ATTR_BEST:
        MSX1PQCore::apply_8dot2col_attr_best(data, pitch, w, h, cs);
        break;
    case MSX1PQ_EIGHTDOT_MODE_PENALTY_BEST:
        MSX1PQCore::apply_8dot2col_attr_best_penalty(data, pitch, w, h, cs);
        break;
    default:
        break;
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

    const auto pitch = static_cast<std::ptrdiff_t>(row_pitch);
    const auto w     = static_cast<std::int32_t>(width);
    const auto h     = static_cast<std::int32_t>(height);
    const int  cs    = static_cast<int>(color_system);

    switch (mode) {
    case MSX1PQ_EIGHTDOT_MODE_FAST1:
        MSX1PQCore::apply_8dot2col_fast1(data, pitch, w, h, cs);
        break;
    case MSX1PQ_EIGHTDOT_MODE_BASIC1:
        MSX1PQCore::apply_8dot2col_basic1(data, pitch, w, h, cs);
        break;
    case MSX1PQ_EIGHTDOT_MODE_BEST1:
        MSX1PQCore::apply_8dot2col_best1(data, pitch, w, h, cs);
        break;
    case MSX1PQ_EIGHTDOT_MODE_ATTR_BEST:
        MSX1PQCore::apply_8dot2col_attr_best(data, pitch, w, h, cs);
        break;
    case MSX1PQ_EIGHTDOT_MODE_PENALTY_BEST:
        MSX1PQCore::apply_8dot2col_attr_best_penalty(data, pitch, w, h, cs);
        break;
    default:
        break;
    }
}

// ---------------------------------------------------------------------------
// 8bit ARGB (AE用) 量子化
// ---------------------------------------------------------------------------

struct FilterRefcon {
    // QuantInfo は各レンダー呼び出しごとに値コピーを保持し、
    // iterate() の並列実行でも他スレッドと状態を共有しない。
    QuantInfo qi{};
    A_long     global_x0{};
    A_long     global_y0{};
    const void* input_base{nullptr};
    std::ptrdiff_t input_pitch{};
    A_long     width{};
    A_long     height{};
};

template <typename PixelT>
static void SetupInputLayout(const PF_EffectWorld* worldP,
                             const PF_Rect& rect,
                             const PixelT*& base_out,
                             std::ptrdiff_t& pitch_out,
                             A_long& width_out,
                             A_long& height_out)
{
    if (!worldP) {
        base_out   = nullptr;
        pitch_out  = 0;
        width_out  = 0;
        height_out = 0;
        return;
    }

    const A_long row_bytes = worldP->rowbytes;
    pitch_out = (row_bytes >= 0)
        ? (row_bytes / static_cast<A_long>(sizeof(PixelT)))
        : ((-row_bytes) / static_cast<A_long>(sizeof(PixelT)));

    const char* base = reinterpret_cast<const char*>(worldP->data);
    if (row_bytes < 0) {
        base += (worldP->height - 1 - rect.top) * (-row_bytes);
    } else {
        base += rect.top * row_bytes;
    }
    base += rect.left * static_cast<A_long>(sizeof(PixelT));

    base_out   = reinterpret_cast<const PixelT*>(base);
    width_out  = rect.right  - rect.left;
    height_out = rect.bottom - rect.top;
}

template <typename PixelT, typename ExtractFunc>
static void SampleSharpenedRGB(const FilterRefcon* ref,
                               const PixelT* inP,
                               A_long x,
                               A_long y,
                               std::uint8_t& r,
                               std::uint8_t& g,
                               std::uint8_t& b,
                               ExtractFunc extract)
{
    if (!ref || !inP) {
        return;
    }

    extract(inP, r, g, b);

    if (!ref->input_base || ref->qi.pre_sharpen <= 0.0f ||
        ref->width <= 0 || ref->height <= 0) {
        return;
    }

    const float amount = clamp01f(ref->qi.pre_sharpen);
    if (amount <= 0.0f) {
        return;
    }

    const auto* base = reinterpret_cast<const PixelT*>(ref->input_base);
    const std::ptrdiff_t pitch = ref->input_pitch;
    const A_long max_x = ref->width - 1;
    const A_long max_y = ref->height - 1;

    const int weights[3][3] = {
        {1, 2, 1},
        {2, 4, 2},
        {1, 2, 1}
    };

    float blur_r = 0.0f;
    float blur_g = 0.0f;
    float blur_b = 0.0f;

    for (int dy = -1; dy <= 1; ++dy) {
        A_long sy = clamp_value(static_cast<A_long>(y) + dy,
                                static_cast<A_long>(0),
                                max_y);
        const PixelT* row = base + sy * pitch;

        for (int dx = -1; dx <= 1; ++dx) {
            A_long sx = clamp_value(static_cast<A_long>(x) + dx,
                                    static_cast<A_long>(0),
                                    max_x);
            std::uint8_t sr{}, sg{}, sb{};
            extract(row + sx, sr, sg, sb);
            int w = weights[dy + 1][dx + 1];
            blur_r += static_cast<float>(sr) * static_cast<float>(w);
            blur_g += static_cast<float>(sg) * static_cast<float>(w);
            blur_b += static_cast<float>(sb) * static_cast<float>(w);
        }
    }

    const float inv_norm = 1.0f / 16.0f;
    blur_r *= inv_norm;
    blur_g *= inv_norm;
    blur_b *= inv_norm;

    auto apply_channel = [&](float orig, float blur) -> std::uint8_t {
        float detail = orig - blur;
        float value  = orig + amount * detail;
        return static_cast<std::uint8_t>(
            clamp_value(value, 0.0f, 255.0f) + 0.5f);
    };

    r = apply_channel(static_cast<float>(r), blur_r);
    g = apply_channel(static_cast<float>(g), blur_g);
    b = apply_channel(static_cast<float>(b), blur_b);
}

static PF_Err
FilterImage8 (
    void        *refcon,
    A_long      xL,
    A_long      yL,
    PF_Pixel8   *inP,
    PF_Pixel8   *outP)
{
    auto *ref = reinterpret_cast<FilterRefcon*>(refcon);
    const QuantInfo *qi = &ref->qi;

    std::uint8_t r = 0;
    std::uint8_t g = 0;
    std::uint8_t b = 0;
    SampleSharpenedRGB<PF_Pixel8>(
        ref,
        inP,
        xL,
        yL,
        r,
        g,
        b,
        [](const PF_Pixel8* p, std::uint8_t& out_r, std::uint8_t& out_g, std::uint8_t& out_b) {
            out_r = p->red;
            out_g = p->green;
            out_b = p->blue;
        });

    // 前処理
    apply_preprocess(qi, r, g, b);

    const MSX1PQ::QuantColor &qc = quantize_pixel(
        *qi,
        r,
        g,
        b,
        static_cast<std::int32_t>(ref->global_x0 + xL),
        static_cast<std::int32_t>(ref->global_y0 + yL));

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
    auto *ref = reinterpret_cast<FilterRefcon*>(refcon);
    const QuantInfo *qi = &ref->qi;

    MSX1PQ_Pixel_BGRA_8u *inBGRA_8uP  = reinterpret_cast<MSX1PQ_Pixel_BGRA_8u*>(inP);
    MSX1PQ_Pixel_BGRA_8u *outBGRA_8uP = reinterpret_cast<MSX1PQ_Pixel_BGRA_8u*>(outP);

    std::uint8_t r = 0;
    std::uint8_t g = 0;
    std::uint8_t b = 0;
    SampleSharpenedRGB<MSX1PQ_Pixel_BGRA_8u>(
        ref,
        inBGRA_8uP,
        xL,
        yL,
        r,
        g,
        b,
        [](const MSX1PQ_Pixel_BGRA_8u* p,
           std::uint8_t& out_r,
           std::uint8_t& out_g,
           std::uint8_t& out_b) {
            out_r = p->red;
            out_g = p->green;
            out_b = p->blue;
        });

    apply_preprocess(qi, r, g, b);

    const MSX1PQ::QuantColor &qc = quantize_pixel(
        *qi,
        r,
        g,
        b,
        static_cast<std::int32_t>(ref->global_x0 + xL),
        static_cast<std::int32_t>(ref->global_y0 + yL));

    outBGRA_8uP->alpha = inBGRA_8uP->alpha;
    outBGRA_8uP->red   = qc.r;
    outBGRA_8uP->green = qc.g;
    outBGRA_8uP->blue  = qc.b;

    return PF_Err_NONE;
}

// ---------------------------------------------------------------------------
// 共通ヘルパー
// ---------------------------------------------------------------------------

static PF_Err
RunIteratePass(
    PF_InData            *in_dataP,
    PF_OutData           *out_data,
    A_long               linesL,
    PF_EffectWorld       *input_worldP,
    FilterRefcon         *refconP,
    PF_IteratePixel8Func filter_func,
    PF_EffectWorld       *output_worldP)
{
    AEFX_SuiteScoper<PF_Iterate8Suite2> iterate8Suite(
        in_dataP,
        kPFIterate8Suite,
        kPFIterate8SuiteVersion2,
        out_data);

    return iterate8Suite->iterate(
        in_dataP,
        0,
        linesL,
        input_worldP,
        nullptr,
        refconP,
        filter_func,
        output_worldP);
}

static void
Apply8dot2colARGB(
    PF_EffectWorld            *output_worldP,
    const PF_Rect             &rect,
    const QuantInfo           &qi)
{
    const A_long row_bytes = output_worldP->rowbytes;
    const A_long row_pitch = (row_bytes >= 0)
        ? (row_bytes / (A_long)sizeof(PF_Pixel8))
        : ((-row_bytes) / (A_long)sizeof(PF_Pixel8));

    const A_long width  = rect.right  - rect.left;
    const A_long height = rect.bottom - rect.top;

    char *base = reinterpret_cast<char*>(output_worldP->data);

    // ROI の左上を指す開始ポインタを計算（上下反転にも対応）
    if (row_bytes < 0) {
        base += (output_worldP->height - 1 - rect.top) * (-row_bytes);
    } else {
        base += rect.top * row_bytes;
    }

    base += rect.left * static_cast<A_long>(sizeof(PF_Pixel8));

    apply_8dot2col_dispatch_ARGB(
        reinterpret_cast<PF_Pixel8*>(base),
        row_pitch,
        width,
        height,
        qi.color_system,
        qi.use_8dot2col);
}

static void
Apply8dot2colBGRA(
    PF_EffectWorld            *output_worldP,
    A_long                    width,
    A_long                    height,
    const QuantInfo           &qi)
{
    A_long row_pitch = output_worldP->rowbytes
        / sizeof(MSX1PQ_Pixel_BGRA_8u);

    MSX1PQ_Pixel_BGRA_8u* base =
        reinterpret_cast<MSX1PQ_Pixel_BGRA_8u*>(output_worldP->data);

    MSX1PQ_Pixel_BGRA_8u* data =
        base + output_worldP->extent_hint.top * row_pitch
             + output_worldP->extent_hint.left;

    apply_8dot2col_dispatch_BGRA(
        data,
        row_pitch,
        width,
        height,
        qi.color_system,
        qi.use_8dot2col);
}

// ---------------------------------------------------------------------------
// Render (スマートレンダリング設定時は呼ばれない)
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
    qi.use_palette_color = (params[MSX1PQ_PARAM_USE_PALETTE_COLOR]->u.bd.value != 0);
    qi.use_8dot2col    = params[MSX1PQ_PARAM_USE_8DOT2COL]->u.pd.value;
    qi.use_hsb         = (params[MSX1PQ_PARAM_DISTANCE_MODE]->u.pd.value == MSX1PQ_DIST_MODE_HSB);

    qi.w_h = clamp01f(
        static_cast<float>(params[MSX1PQ_PARAM_WEIGHT_H]->u.fs_d.value));
    qi.w_s = clamp01f(
        static_cast<float>(params[MSX1PQ_PARAM_WEIGHT_S]->u.fs_d.value));
    qi.w_b = clamp01f(
        static_cast<float>(params[MSX1PQ_PARAM_WEIGHT_B]->u.fs_d.value));

    qi.pre_posterize = clamp_value(
        static_cast<int>(params[MSX1PQ_PARAM_PRE_POSTERIZE]->u.fs_d.value + 0.5),
        0,
        255);
    qi.pre_sat       = static_cast<float>(params[MSX1PQ_PARAM_PRE_SAT]->u.fs_d.value);
    qi.pre_gamma     = static_cast<float>(params[MSX1PQ_PARAM_PRE_GAMMA]->u.fs_d.value);
    qi.pre_highlight = static_cast<float>(params[MSX1PQ_PARAM_PRE_HIGHLIGHT]->u.fs_d.value);
    qi.pre_hue       = static_cast<float>(params[MSX1PQ_PARAM_PRE_HUE]->u.fs_d.value);
    qi.pre_sharpen   = clamp01f(
        static_cast<float>(params[MSX1PQ_PARAM_PRE_SHARPEN]->u.fs_d.value));

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
            FilterRefcon refcon{};
            refcon.qi = qi;
            refcon.global_x0 = output->extent_hint.left;
            refcon.global_y0 = output->extent_hint.top;

            const PF_EffectWorld* input_world = reinterpret_cast<PF_EffectWorld*>(
                &params[MSX1PQ_PARAM_INPUT]->u.ld);
            const MSX1PQ_Pixel_BGRA_8u* input_base = nullptr;
            std::ptrdiff_t input_pitch  = 0;
            A_long src_w = 0;
            A_long src_h = 0;
            SetupInputLayout(
                input_world,
                input_world ? input_world->extent_hint : output->extent_hint,
                input_base,
                input_pitch,
                src_w,
                src_h);
            refcon.input_base  = input_base;
            refcon.input_pitch = input_pitch;
            refcon.width       = src_w;
            refcon.height      = src_h;

            err = RunIteratePass(
                      in_dataP,
                      out_data,
                      linesL,
                      reinterpret_cast<PF_EffectWorld*>(
                          &params[MSX1PQ_PARAM_INPUT]->u.ld),
                      &refcon,
                      FilterImageBGRA_8u,
                      reinterpret_cast<PF_EffectWorld*>(output));

            // ---- 2パス目：8dot / 2color 後処理（基本1）----
            if (!err && !qi.use_palette_color &&
                qi.use_8dot2col != MSX1PQ_EIGHTDOT_MODE_NONE) {

                Apply8dot2colBGRA(
                    reinterpret_cast<PF_EffectWorld*>(output),
                    width,
                    height,
                    qi);
            }


        } else {
            err = PF_Err_UNRECOGNIZED_PARAM_TYPE;
        }

    } else {
        // AE: ARGB32 8bit

        // (reinterpret_cast<PF_EffectWorld*>(output));

        // ---- 1パス目：通常の量子化 ----
        FilterRefcon refcon{};
        refcon.qi = qi;
        refcon.global_x0 = output->extent_hint.left;
        refcon.global_y0 = output->extent_hint.top;

        const PF_EffectWorld* input_world = reinterpret_cast<PF_EffectWorld*>(
            &params[MSX1PQ_PARAM_INPUT]->u.ld);
        const PF_Pixel8* input_base = nullptr;
        std::ptrdiff_t input_pitch  = 0;
        A_long src_w = 0;
        A_long src_h = 0;
        SetupInputLayout(
            input_world,
            input_world ? input_world->extent_hint : output->extent_hint,
            input_base,
            input_pitch,
            src_w,
            src_h);
        refcon.input_base  = input_base;
        refcon.input_pitch = input_pitch;
        refcon.width       = src_w;
        refcon.height      = src_h;

        err = RunIteratePass(
                  in_dataP,
                  out_data,
                  linesL,
                  reinterpret_cast<PF_EffectWorld*>(
                      &params[MSX1PQ_PARAM_INPUT]->u.ld),
                  &refcon,
                  FilterImage8,
                  reinterpret_cast<PF_EffectWorld*>(output));

        // ---- 2パス目：8dot / 2color 後処理（基本1）----
        if (!err && !qi.use_palette_color &&
            qi.use_8dot2col != MSX1PQ_EIGHTDOT_MODE_NONE) {
            Apply8dot2colARGB(
                reinterpret_cast<PF_EffectWorld*>(output),
                output->extent_hint,
                qi);
        }
    }

    return err;
}


static PF_Err
SmartPreRender(
    PF_InData         *in_dataP,
    PF_OutData        *out_dataP,
    PF_ParamDef       * /*params*/[],
    PF_PreRenderExtra *extraP)
{
    PF_Err err = PF_Err_NONE;

    // ホストから来た元の要求
    PF_RenderRequest host_req = extraP->input->output_request;
    PF_Rect host_rect = host_req.rect;
    /*
    MyDebugLog("SmartPreRender: host request L=%ld, T=%ld, R=%ld, B=%ld",
        host_rect.left,
        host_rect.top,
        host_rect.right,
        host_rect.bottom);
    */

    const A_long comp_w = in_dataP->width;
    const A_long comp_h = in_dataP->height;

    // 出力用: ホストの request をコンポ内にクランプ（→やめる）
    PF_Rect out_rect = host_rect;
    // 変更すると上位のエフェクトによって表示位置がずれてクリッピングされることがある
    //out_rect.left   = (std::max)(out_rect.left,  (A_long)0);
    //out_rect.top    = (std::max)(out_rect.top,   (A_long)0);
    //out_rect.right  = (std::min)(out_rect.right, comp_w);
    //out_rect.bottom = (std::min)(out_rect.bottom,comp_h);
    /*
    MyDebugLog("SmartPreRender: output rect L=%ld, T=%ld, R=%ld, B=%ld",
        out_rect.left,
        out_rect.top,
        out_rect.right,
        out_rect.bottom);
    */

    // 入力用: 横だけ全幅に広げる（→やめる）上下は out_rect に合わせる
    PF_RenderRequest input_req = host_req;
    PF_Rect in_roi = out_rect;
    // ここを広げると前に挟むエフェクトによって位置がずれる不具合が出ることがある
    //in_roi.left  = 0;
    //in_roi.right = comp_w;
    input_req.rect = in_roi;

    /*
    MyDebugLog("SmartPreRender: input rect L=%ld, T=%ld, R=%ld, B=%ld",
        input_req.rect.left,
        input_req.rect.top,
        input_req.rect.right,
        input_req.rect.bottom);
    */

    PF_CheckoutResult in_result{};
    err = extraP->cb->checkout_layer(
              in_dataP->effect_ref,
              MSX1PQ_PARAM_INPUT,
              MSX1PQ_PARAM_INPUT,
              &input_req,
              in_dataP->current_time,
              in_dataP->time_step,
              in_dataP->time_scale,
              &in_result);

    if (!err) {

        /*
        MyDebugLog("SmartPreRender: input result rect L=%ld, T=%ld, R=%ld, B=%ld",
            in_result.result_rect.left,
            in_result.result_rect.top,
            in_result.result_rect.right,
            in_result.result_rect.bottom);

        MyDebugLog("SmartPreRender: input result max_result rect L=%ld, T=%ld, R=%ld, B=%ld",
            in_result.max_result_rect.left,
            in_result.max_result_rect.top,
            in_result.max_result_rect.right,
            in_result.max_result_rect.bottom);
        */

        // in_result.result_rect との共通部分に
        auto intersect = [](const PF_Rect& a, const PF_Rect& b) {
            PF_Rect r;
            r.left   = (std::max)(a.left,   b.left);
            r.top    = (std::max)(a.top,    b.top);
            r.right  = (std::min)(a.right,  b.right);
            r.bottom = (std::min)(a.bottom, b.bottom);
            return r;
        };

        //PF_Rect final_rect = intersect(out_rect, in_result.result_rect);
        PF_Rect final_rect = in_result.result_rect; // out_rectを変更しなくなったのでintersectもやめる

        /*
        MyDebugLog("SmartPreRender: final result rect L=%ld, T=%ld, R=%ld, B=%ld",
            final_rect.left,
            final_rect.top,
            final_rect.right,
            final_rect.bottom);
        */

        extraP->output->result_rect     = final_rect;
        extraP->output->max_result_rect = final_rect;
    }

    return err;
}


static PF_Err
SmartRender(
    PF_InData           *in_dataP,
    PF_OutData          *out_data,
    PF_ParamDef         * /*params*/[],
    PF_SmartRenderExtra *extraP)
{

    PF_Err err  = PF_Err_NONE;
    PF_Err err2 = PF_Err_NONE;

    PF_EffectWorld *input_worldP  = nullptr;
    PF_EffectWorld *output_worldP = nullptr;

    // 入力 / 出力 checkout
    ERR( extraP->cb->checkout_layer_pixels(
             in_dataP->effect_ref,
             MSX1PQ_PARAM_INPUT,
             &input_worldP) );

    if (!err) {
        ERR( extraP->cb->checkout_output(
                 in_dataP->effect_ref,
                 &output_worldP) );
    }

    if (!err && input_worldP && output_worldP) {

        PF_Rect current_rect = output_worldP->extent_hint;
        if (current_rect.left == current_rect.right ||
            current_rect.top  == current_rect.bottom) {
            current_rect.left   = 0;
            current_rect.top    = 0;
            current_rect.right  = output_worldP->width;
            current_rect.bottom = output_worldP->height;
        }

        // --------------------------------------------------------------------
        // QuantInfo を PF_CHECKOUT_PARAM で構築
        // --------------------------------------------------------------------
        QuantInfo  qi{};
        PF_ParamDef param;

        // COLOR_SYSTEM (popup)
        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_COLOR_SYSTEM,
                param) );
        qi.color_system = param.u.pd.value;
        ERR( CheckinParam(in_dataP, param) );

        // USE_DITHER (checkbox)
        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_USE_DITHER,
                param) );
        qi.use_dither = (param.u.bd.value != 0);
        ERR( CheckinParam(in_dataP, param) );

        // USE_PALETTE_COLOR (checkbox)
        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_USE_PALETTE_COLOR,
                param) );
        qi.use_palette_color = (param.u.bd.value != 0);
        ERR( CheckinParam(in_dataP, param) );

        // USE_8DOT2COL (popup)
        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_USE_8DOT2COL,
                param) );
        qi.use_8dot2col = param.u.pd.value;
        ERR( CheckinParam(in_dataP, param) );

        // DISTANCE_MODE (popup)
        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_DISTANCE_MODE,
                param) );
        qi.use_hsb = (param.u.pd.value == MSX1PQ_DIST_MODE_HSB);
        ERR( CheckinParam(in_dataP, param) );

        // WEIGHT_H/S/B (float)
        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_WEIGHT_H,
                param) );
        qi.w_h = clamp01f(static_cast<float>(param.u.fs_d.value));
        ERR( CheckinParam(in_dataP, param) );

        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_WEIGHT_S,
                param) );
        qi.w_s = clamp01f(static_cast<float>(param.u.fs_d.value));
        ERR( CheckinParam(in_dataP, param) );

        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_WEIGHT_B,
                param) );
        qi.w_b = clamp01f(static_cast<float>(param.u.fs_d.value));
        ERR( CheckinParam(in_dataP, param) );

        // PRE_POSTERIZE
        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_PRE_POSTERIZE,
                param) );
        qi.pre_posterize = clamp_value(
            static_cast<int>(param.u.fs_d.value + 0.5f),
            0,
            255);
        ERR( CheckinParam(in_dataP, param) );

        // PRE_SAT / GAMMA / HIGHLIGHT / HUE
        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_PRE_SAT,
                param) );
        qi.pre_sat = static_cast<float>(param.u.fs_d.value);
        ERR( CheckinParam(in_dataP, param) );

        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_PRE_GAMMA,
                param) );
        qi.pre_gamma = static_cast<float>(param.u.fs_d.value);
        ERR( CheckinParam(in_dataP, param) );

        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_PRE_HIGHLIGHT,
                param) );
        qi.pre_highlight = static_cast<float>(param.u.fs_d.value);
        ERR( CheckinParam(in_dataP, param) );

        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_PRE_HUE,
                param) );
        qi.pre_hue = static_cast<float>(param.u.fs_d.value);
        ERR( CheckinParam(in_dataP, param) );

        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_PRE_SHARPEN,
                param) );
        qi.pre_sharpen = clamp01f(static_cast<float>(param.u.fs_d.value));
        ERR( CheckinParam(in_dataP, param) );

        // USE_DARK_DITHER
        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_USE_DARK_DITHER,
                param) );
        qi.use_dark_dither = (param.u.bd.value != 0);
        ERR( CheckinParam(in_dataP, param) );

        // --------------------------------------------------------------------
        // スマートレンダー用 ROI 揃え（ディザ使用時のみ 8ドット境界にスナップ）
        // --------------------------------------------------------------------
        const auto align_down8 = [](A_long v) {
            if (v >= 0) {
                return (v / 8) * 8;
            }
            return -(((-v + 7) / 8) * 8);
        };
        const auto align_up8 = [](A_long v) {
            if (v >= 0) {
                return ((v + 7) / 8) * 8;
            }
            return -(((-v) / 8) * 8);
        };

        PF_Rect aligned_rect = current_rect;
        if (qi.use_dither) {
            aligned_rect.left   = align_down8(current_rect.left);
            aligned_rect.right  = align_up8(current_rect.right);
        }
        aligned_rect.top    = current_rect.top;
        aligned_rect.bottom = current_rect.bottom;

        aligned_rect.left = clamp_value(aligned_rect.left, static_cast<A_long>(0), output_worldP->width);
        aligned_rect.right = clamp_value(aligned_rect.right, aligned_rect.left, output_worldP->width);
        aligned_rect.top = clamp_value(aligned_rect.top, static_cast<A_long>(0), output_worldP->height);
        aligned_rect.bottom = clamp_value(aligned_rect.bottom, aligned_rect.top, output_worldP->height);

        const A_long width  = aligned_rect.right  - aligned_rect.left;
        const A_long height = aligned_rect.bottom - aligned_rect.top;

        // 矩形が空の場合は何もしない
        if (width > 0 && height > 0) {
            auto calc_start = [](const PF_EffectWorld *worldP,
                                 const PF_Rect &rect) -> PF_Pixel8* {
                const A_long row_bytes = worldP->rowbytes;
                char *base = reinterpret_cast<char*>(worldP->data);

                if (row_bytes < 0) {
                    base += (worldP->height - 1 - rect.top) * (-row_bytes);
                } else {
                    base += rect.top * row_bytes;
                }

                base += rect.left * static_cast<A_long>(sizeof(PF_Pixel8));

                return reinterpret_cast<PF_Pixel8*>(base);
            };

            PF_EffectWorld input_roi  = *input_worldP;
            PF_EffectWorld output_roi = *output_worldP;

            input_roi.data  = calc_start(input_worldP, aligned_rect);
            output_roi.data = calc_start(output_worldP, aligned_rect);

            input_roi.width  = width;
            input_roi.height = height;
            output_roi.width  = width;
            output_roi.height = height;

            input_roi.extent_hint.left = 0;
            input_roi.extent_hint.top  = 0;
            input_roi.extent_hint.right  = width;
            input_roi.extent_hint.bottom = height;
            output_roi.extent_hint.left = 0;
            output_roi.extent_hint.top  = 0;
            output_roi.extent_hint.right  = width;
            output_roi.extent_hint.bottom = height;

            MyDebugLog("### SR: rect by hint L=%ld, T=%ld, R=%ld, B=%ld, aligned rect L=%ld, T=%ld, R=%ld, B=%ld",
                current_rect.left,
                current_rect.top,
                current_rect.right,
                current_rect.bottom,
                aligned_rect.left,
                aligned_rect.top,
                aligned_rect.right,
                aligned_rect.bottom);

            FilterRefcon refcon{};
            refcon.qi = qi;
            refcon.global_x0 = aligned_rect.left;
            refcon.global_y0 = aligned_rect.top;

            const PF_Pixel8* input_base = nullptr;
            std::ptrdiff_t input_pitch  = 0;
            A_long src_w = 0;
            A_long src_h = 0;
            SetupInputLayout(
                &input_roi,
                input_roi.extent_hint,
                input_base,
                input_pitch,
                src_w,
                src_h);
            refcon.input_base  = input_base;
            refcon.input_pitch = input_pitch;
            refcon.width       = src_w;
            refcon.height      = src_h;

            // ----------------------------------------------------------------
            // 1パス目：通常量子化
            // ----------------------------------------------------------------
            if (!err) {
                err = RunIteratePass(
                          in_dataP,
                          out_data,
                          height,
                          &input_roi,
                          &refcon,
                          FilterImage8,   // 既存 8bit フィルタ
                          &output_roi);
            }

            // ----------------------------------------------------------------
            // 2パス目：8dot / 2color 後処理
            // ----------------------------------------------------------------
            if (!err &&
                !qi.use_palette_color &&
                qi.use_8dot2col != MSX1PQ_EIGHTDOT_MODE_NONE) {
                Apply8dot2colARGB(output_worldP, aligned_rect, qi);
            }
        }
    }

    // input の checkin
    err2 = extraP->cb->checkin_layer_pixels(
               in_dataP->effect_ref,
               MSX1PQ_PARAM_INPUT);
    if (!err && err2) {
        err = err2;
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

    // MyDebugLog("=== UpdateParameterUI CALLED ===");
    // MyDebugLog("UpdateParameterUI: mode=%ld enable_hsb=%d",
    //          mode, enable_hsb ? 1 : 0);

    PF_ParamDef tmp;

    // --- H weight ---
    tmp = *params[MSX1PQ_PARAM_WEIGHT_H];
    if (enable_hsb)
        tmp.ui_flags &= ~PF_PUI_DISABLED;
    else
        tmp.ui_flags |= PF_PUI_DISABLED;
    // MyDebugLog("  H ui_flags(new)=0x%08x", tmp.ui_flags);
    paramUtils->PF_UpdateParamUI(in_data->effect_ref,
                                 MSX1PQ_PARAM_WEIGHT_H,
                                 &tmp);

    // --- S weight ---
    tmp = *params[MSX1PQ_PARAM_WEIGHT_S];
    if (enable_hsb)
        tmp.ui_flags &= ~PF_PUI_DISABLED;
    else
        tmp.ui_flags |= PF_PUI_DISABLED;
    // MyDebugLog("  S ui_flags(new)=0x%08x", tmp.ui_flags);
    paramUtils->PF_UpdateParamUI(in_data->effect_ref,
                                 MSX1PQ_PARAM_WEIGHT_S,
                                 &tmp);

    // --- B weight ---
    tmp = *params[MSX1PQ_PARAM_WEIGHT_B];
    if (enable_hsb)
        tmp.ui_flags &= ~PF_PUI_DISABLED;
    else
        tmp.ui_flags |= PF_PUI_DISABLED;
    // MyDebugLog("  B ui_flags(new)=0x%08x", tmp.ui_flags);
    paramUtils->PF_UpdateParamUI(in_data->effect_ref,
                                 MSX1PQ_PARAM_WEIGHT_B,
                                 &tmp);

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

            case PF_Cmd_SMART_PRE_RENDER:
                // AE SmartFX 用 / ROI 最適化なし
                err = SmartPreRender(
                          in_dataP,
                          out_data,
                          params,
                          reinterpret_cast<PF_PreRenderExtra*>(extra));
                break;

            case PF_Cmd_SMART_RENDER:
                // AE SmartFX 用 / ROI 最適化なし
                err = SmartRender(
                          in_dataP,
                          out_data,
                          params,
                          reinterpret_cast<PF_SmartRenderExtra*>(extra));
                break;
        }
    } catch(PF_Err &thrown_err) {
        // AE に例外を飛ばさない
        err = thrown_err;
    }
    return err;
}
