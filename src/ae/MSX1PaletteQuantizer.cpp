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
#include "adobesdk/DrawbotSuite.h"
#include "MSX1PaletteQuantizer.h"
#include "MSX1PQPalettes.h"

#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <random>
#include <cstring>
#include <vector>


#ifndef MSX1PQ_IMPL_AEFX_SUITE_HELPER
#define MSX1PQ_IMPL_AEFX_SUITE_HELPER
extern "C" {
PF_Err AEFX_AcquireSuite(
    PF_InData   *in_data,
    PF_OutData  *out_data,
    const char  *name,
    int32_t      version,
    const char  *error_stringPC0,
    void       **suite)
{
    PF_Err         err    = PF_Err_NONE;
    SPBasicSuite  *bsuite = in_data->pica_basicP;

    if (bsuite) {
        (*bsuite->AcquireSuite)((char*)name, version, (const void**)suite);
        if (!*suite) {
            err = PF_Err_BAD_CALLBACK_PARAM;
        }
    } else {
        err = PF_Err_BAD_CALLBACK_PARAM;
    }

    if (err) {
        const char *error_stringPC = error_stringPC0 ? error_stringPC0 : "Not able to acquire AEFX Suite.";
        out_data->out_flags |= PF_OutFlag_DISPLAY_ERROR_MESSAGE;
        PF_SPRINTF(out_data->return_msg, error_stringPC);
    }

    return err;
}

PF_Err AEFX_ReleaseSuite(
    PF_InData   *in_data,
    PF_OutData  *out_data,
    const char  *name,
    int32_t      version,
    const char  *error_stringPC0)
{
    PF_Err         err    = PF_Err_NONE;
    SPBasicSuite  *bsuite = in_data->pica_basicP;

    if (bsuite) {
        (*bsuite->ReleaseSuite)((char*)name, version);
    } else {
        err = PF_Err_BAD_CALLBACK_PARAM;
    }

    if (err) {
        const char *error_stringPC = error_stringPC0 ? error_stringPC0 : "Not able to release AEFX Suite.";
        out_data->out_flags |= PF_OutFlag_DISPLAY_ERROR_MESSAGE;
        PF_SPRINTF(out_data->return_msg, error_stringPC);
    }

    return err;
}

PF_Err AEFX_AcquireDrawbotSuites(
    PF_InData       *in_data,
    PF_OutData      *out_data,
    DRAWBOT_Suites  *suitesP)
{
    PF_Err err = PF_Err_NONE;

    if (!suitesP) {
        out_data->out_flags |= PF_OutFlag_DISPLAY_ERROR_MESSAGE;
        PF_SPRINTF(out_data->return_msg, "NULL suite pointer passed to AEFX_AcquireDrawbotSuites");
        return PF_Err_UNRECOGNIZED_PARAM_TYPE;
    }

    err = AEFX_AcquireSuite(in_data, out_data, kDRAWBOT_DrawSuite, kDRAWBOT_DrawSuite_VersionCurrent, NULL, (void **)&suitesP->drawbot_suiteP);
    if (!err) {
        err = AEFX_AcquireSuite(in_data, out_data, kDRAWBOT_SupplierSuite, kDRAWBOT_SupplierSuite_VersionCurrent, NULL, (void **)&suitesP->supplier_suiteP);
    }
    if (!err) {
        err = AEFX_AcquireSuite(in_data, out_data, kDRAWBOT_SurfaceSuite, kDRAWBOT_SurfaceSuite_VersionCurrent, NULL, (void **)&suitesP->surface_suiteP);
    }
    if (!err) {
        err = AEFX_AcquireSuite(in_data, out_data, kDRAWBOT_PathSuite, kDRAWBOT_PathSuite_VersionCurrent, NULL, (void **)&suitesP->path_suiteP);
    }
    return err;
}

PF_Err AEFX_ReleaseDrawbotSuites(
    PF_InData   *in_data,
    PF_OutData  *out_data)
{
    AEFX_ReleaseSuite(in_data, out_data, kDRAWBOT_DrawSuite, kDRAWBOT_DrawSuite_VersionCurrent, NULL);
    AEFX_ReleaseSuite(in_data, out_data, kDRAWBOT_SupplierSuite, kDRAWBOT_SupplierSuite_VersionCurrent, NULL);
    AEFX_ReleaseSuite(in_data, out_data, kDRAWBOT_SurfaceSuite, kDRAWBOT_SurfaceSuite_VersionCurrent, NULL);
    AEFX_ReleaseSuite(in_data, out_data, kDRAWBOT_PathSuite, kDRAWBOT_PathSuite_VersionCurrent, NULL);
    return PF_Err_NONE;
}
} // extern "C"
#endif // MSX1PQ_IMPL_AEFX_SUITE_HELPER


#ifdef AE_OS_WIN
#ifndef NOMINMAX
#define NOMINMAX 1
#endif
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
    constexpr int  kVersionMinor        = 8;
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
using MSX1PQCore::apply_black_edge_sharpen;
using MSX1PQCore::apply_preprocess;
using MSX1PQCore::find_basic_index_from_rgb;
using MSX1PQCore::get_basic_palette;
using MSX1PQCore::nearest_basic_hsv;
using MSX1PQCore::nearest_palette_hsv;
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
using MSX1PQCore::MSX1PQ_DIST_MODE_HSV;
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


static PF_Err DrawSwatchRow(
    PF_InData     *in_data,
    PF_OutData    *out_data,
    PF_ParamDef   *params[],
    PF_EventExtra *event_extra)
{
    if (!event_extra || !params || !in_data || !out_data) {
        return PF_Err_NONE;
    }
    if (event_extra->e_type != PF_Event_DRAW ||
        event_extra->effect_win.index != MSX1PQ_PARAM_SWATCH_ROW) {
        return PF_Err_NONE;
    }

    MyDebugLog("DrawSwatchRow: area=%d index=%d event=%d",
               event_extra->effect_win.area,
               event_extra->effect_win.index,
               event_extra->e_type);

    const PF_Rect* frame_ptr = &event_extra->effect_win.current_frame;
    const PF_Rect& title_frame = event_extra->effect_win.param_title_frame;
    if (frame_ptr->bottom <= frame_ptr->top) {
        frame_ptr = &title_frame;
    }
    const PF_Rect& frame = *frame_ptr;
    const float height   = static_cast<float>(frame.bottom - frame.top);
    const float width    = static_cast<float>(frame.right - frame.left);
    const float window_height = std::max(height, 20.0f);
    const float margin   = 4.0f;
    const float max_box_by_height = window_height - 4.0f;
    const float available_width = std::max(width - margin * 2.0f, 0.0f);
    const float box_space = std::max(available_width - (MSX1PQ::kNumBasicColors - 1) * margin, 0.0f);
    const float max_box_by_width = box_space / MSX1PQ::kNumBasicColors;
    const float box_size = std::max(4.0f, std::min(14.0f, std::min(max_box_by_height, max_box_by_width)));
    MyDebugLog("DrawSwatchRow: frame=(%d,%d,%d,%d) size=(%.1f,%.1f) window_h=%.1f box_size=%.1f title_frame=(%d,%d,%d,%d)",
               frame.left, frame.top, frame.right, frame.bottom, width, height, window_height, box_size,
               title_frame.left, title_frame.top, title_frame.right, title_frame.bottom);

    const A_long color_system = params[MSX1PQ_PARAM_COLOR_SYSTEM]->u.pd.value;
    const MSX1PQ::QuantColor* palette = get_basic_palette(static_cast<int>(color_system));
    if (!palette) {
        return PF_Err_NONE;
    }

    DRAWBOT_Suites drawbot_suites{};
    if (AEFX_AcquireDrawbotSuites(in_data, out_data, &drawbot_suites) != PF_Err_NONE) {
        MyDebugLog("DrawSwatchRow: AcquireDrawbotSuites failed");
        return PF_Err_NONE;
    }

    PF_EffectCustomUISuite1 *custom_ui_suite = nullptr;
    DRAWBOT_DrawRef draw_ref = nullptr;
    if (AEFX_AcquireSuite(
            in_data,
            out_data,
            kPFEffectCustomUISuite,
            kPFEffectCustomUISuiteVersion1,
            "EffectCustomUISuite",
            reinterpret_cast<void**>(&custom_ui_suite)) == PF_Err_NONE &&
        custom_ui_suite) {
        (void)custom_ui_suite->PF_GetDrawingReference(event_extra->contextH, &draw_ref);
        (void)AEFX_ReleaseSuite(
            in_data,
            out_data,
            kPFEffectCustomUISuite,
            kPFEffectCustomUISuiteVersion1,
            "EffectCustomUISuite");
    }

    if (!draw_ref) {
        (void)AEFX_ReleaseDrawbotSuites(in_data, out_data);
        return PF_Err_NONE;
    }

    DRAWBOT_SupplierRef supplier_ref = nullptr;
    DRAWBOT_SurfaceRef surface_ref   = nullptr;
    if (drawbot_suites.drawbot_suiteP->GetSupplier(draw_ref, &supplier_ref) != PF_Err_NONE ||
        drawbot_suites.drawbot_suiteP->GetSurface(draw_ref, &surface_ref) != PF_Err_NONE) {
        MyDebugLog("DrawSwatchRow: GetSupplier/GetSurface failed");
        (void)AEFX_ReleaseDrawbotSuites(in_data, out_data);
        return PF_Err_NONE;
    }

    float x = static_cast<float>(frame.left) + margin;
    const float y = (height > box_size + margin)
        ? static_cast<float>(frame.top) + (height - box_size) * 0.5f
        : static_cast<float>(frame.top) + margin;

    DRAWBOT_BrushRef bg_brush_ref = nullptr;
    DRAWBOT_PathRef bg_path_ref = nullptr;
    DRAWBOT_ColorRGBA bg_color{};
    bg_color.red = bg_color.green = bg_color.blue = 0.1f;
    bg_color.alpha = 1.0f;

    DRAWBOT_RectF32 bg_rect{
        static_cast<float>(frame.left) + 0.5f,
        static_cast<float>(frame.top) + 0.5f,
        static_cast<float>(frame.right - frame.left),
        static_cast<float>(window_height < 18.0f ? 18.0f : window_height)
    };

    if (drawbot_suites.supplier_suiteP->NewPath(supplier_ref, &bg_path_ref) == PF_Err_NONE) {
        (void)drawbot_suites.path_suiteP->AddRect(bg_path_ref, &bg_rect);
        if (drawbot_suites.supplier_suiteP->NewBrush(supplier_ref, &bg_color, &bg_brush_ref) == PF_Err_NONE) {
            (void)drawbot_suites.surface_suiteP->FillPath(surface_ref, bg_brush_ref, bg_path_ref, kDRAWBOT_FillType_Default);
        }
    }

    if (bg_brush_ref) {
        (void)drawbot_suites.supplier_suiteP->ReleaseObject(reinterpret_cast<DRAWBOT_ObjectRef>(bg_brush_ref));
    }
    if (bg_path_ref) {
        (void)drawbot_suites.supplier_suiteP->ReleaseObject(reinterpret_cast<DRAWBOT_ObjectRef>(bg_path_ref));
    }

    for (int i = 0; i < MSX1PQ::kNumBasicColors; ++i) {
        DRAWBOT_PathRef path_ref = nullptr;
        DRAWBOT_BrushRef brush_ref = nullptr;
        DRAWBOT_RectF32 rectF{ x + 0.5f, y + 0.5f, box_size, box_size };

        if (drawbot_suites.supplier_suiteP->NewPath(supplier_ref, &path_ref) == PF_Err_NONE) {
            (void)drawbot_suites.path_suiteP->AddRect(path_ref, &rectF);
        }
        else {
            MyDebugLog("DrawSwatchRow: NewPath failed index=%d", i);
        }

        DRAWBOT_ColorRGBA c{};
        c.red   = static_cast<float>(palette[i].r) / 255.0f;
        c.green = static_cast<float>(palette[i].g) / 255.0f;
        c.blue  = static_cast<float>(palette[i].b) / 255.0f;
        c.alpha = 1.0f;

        if (path_ref &&
            drawbot_suites.supplier_suiteP->NewBrush(supplier_ref, &c, &brush_ref) == PF_Err_NONE) {
            (void)drawbot_suites.surface_suiteP->FillPath(surface_ref, brush_ref, path_ref, kDRAWBOT_FillType_Default);
        } else if (path_ref) {
            MyDebugLog("DrawSwatchRow: NewBrush failed index=%d", i);
        }

        if (brush_ref) {
            (void)drawbot_suites.supplier_suiteP->ReleaseObject(reinterpret_cast<DRAWBOT_ObjectRef>(brush_ref));
        }
        if (path_ref) {
            (void)drawbot_suites.supplier_suiteP->ReleaseObject(reinterpret_cast<DRAWBOT_ObjectRef>(path_ref));
        }

        x += box_size + margin;
    }

    event_extra->evt_out_flags |= PF_EO_HANDLED_EVENT;
    (void)AEFX_ReleaseDrawbotSuites(in_data, out_data);
    return PF_Err_NONE;
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

        out_data->out_flags  = PF_OutFlag_NONE | PF_OutFlag_CUSTOM_UI; // | PF_OutFlag_SEND_UPDATE_PARAMS_UI;
        out_data->out_flags2 = PF_OutFlag2_SUPPORTS_SMART_RENDER |
                               PF_OutFlag2_SUPPORTS_THREADED_RENDERING;
    //PF_OutFlag_CUSTOM_UI = 0x00008000
    //PF_OutFlag_SEND_UPDATE_PARAMS_UI = 0x04000000
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
        MSX1PQ_DIST_MODE_RGB, // デフォルト値 (1 = RGB)
        "RGB|HSV",            // 順番に 1:RGB, 2:HSV
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
        "V weight",
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
        "R weight",
        0,
        1,
        0,
        1,
        1,
        2,
        0,
        0,
        MSX1PQ_PARAM_WEIGHT_R
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "G weight",
        0,
        1,
        0,
        1,
        1,
        2,
        0,
        0,
        MSX1PQ_PARAM_WEIGHT_G
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "B weight",
        0,
        1,
        0,
        1,
        1,
        2,
        0,
        0,
        MSX1PQ_PARAM_WEIGHT_B_RGB
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
        2,
        0,
        10,
        0,
        2,
        0,
        0,
        MSX1PQ_PARAM_PRE_SAT
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "Pre 3: Gamma",
        0.2,
        5,
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
        "Pre 4: Contrast adjust",
        0.2,
        5,
        0,
        10,
        1,
        2,
        0,
        0,
        MSX1PQ_PARAM_PRE_CONTRAST
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "Pre 5: Hue rotate",
        -90,
        90,
        -180,
        180,
        0,
        2,
        0,
        0,
        MSX1PQ_PARAM_PRE_HUE
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "Pre 6: Black cutoff",
        0,
        1,
        0,
        1,
        0,
        2,
        0,
        0,
        MSX1PQ_PARAM_PRE_BLACK_CUTOFF
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_FLOAT_SLIDERX(
        "Pre 7: Sharpen near black",
        0,
        10,
        0,
        5,
        0,
        2,
        0,
        0,
        MSX1PQ_PARAM_PRE_SHARPEN_BLACK
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

    // Palette control topic
    AEFX_CLR_STRUCT(def);
    PF_ADD_TOPIC(
        "MSX1 Palette Control",
        MSX1PQ_PARAM_TOPIC_PALETTE_CONTROL
    );

    AEFX_CLR_STRUCT(def);
    def.flags |= PF_ParamFlag_CANNOT_TIME_VARY;
    def.ui_flags |= PF_PUI_CONTROL;
    def.ui_height = 32;
    PF_ADD_NULL("Palette sample", MSX1PQ_PARAM_SWATCH_ROW);

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*1: Black",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_1
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*2: Medium Green",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_2
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*3: Light Green",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_3
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*4: Dark Blue",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_4
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*5: Light Blue",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_5
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*6: Dark Red",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_6
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*7: Cyan",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_7
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*8: Medium Red",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_8
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*9: Light Red",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_9
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*10: Dark Yellow",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_10
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*11: Light Yellow",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_11
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*12: Dark Green",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_12
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*13: Magenta",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_13
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*14: Gray",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_14
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_CHECKBOX(
        "*15: White",
        "Enable",
        TRUE,
        0,
        MSX1PQ_PARAM_COLOR_FLAG_15
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_BUTTON(
        "Randomize",
        "Randomize",
        0,
        PF_ParamFlag_SUPERVISE,
        MSX1PQ_PARAM_RANDOMIZE_PALETTE_FLAGS
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_BUTTON(
        "Rand +1",
        "Rand +1",
        0,
        PF_ParamFlag_SUPERVISE,
        MSX1PQ_PARAM_RANDOMIZE_PLUS_ONE
    );

    AEFX_CLR_STRUCT(def);
    PF_ADD_BUTTON(
        "Rand -1",
        "Rand -1",
        0,
        PF_ParamFlag_SUPERVISE,
        MSX1PQ_PARAM_RANDOMIZE_MINUS_ONE
    );

    AEFX_CLR_STRUCT(def);
    PF_END_TOPIC(MSX1PQ_PARAM_TOPIC_PALETTE_CONTROL_END);

    PF_CustomUIInfo ci{};
    ci.events = PF_CustomEFlag_EFFECT;
    ci.comp_ui_width = ci.comp_ui_height = 0;
    ci.comp_ui_alignment = PF_UIAlignment_NONE;
    ci.layer_ui_width = ci.layer_ui_height = 0;
    ci.layer_ui_alignment = PF_UIAlignment_NONE;
    ci.preview_ui_width = ci.preview_ui_height = 0;
    ci.preview_ui_alignment = PF_UIAlignment_NONE;
    ERR((*(in_data->inter.register_ui))(in_data->effect_ref, &ci));

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
    const PF_Pixel8* pre_sharpen_argb{nullptr};
    const MSX1PQ_Pixel_BGRA_8u* pre_sharpen_bgra{nullptr};
    std::ptrdiff_t pre_sharpen_pitch{0};
};

template<typename PixelT>
static void BuildPreSharpenBuffer(
    const PF_EffectWorld *world,
    float                 strength,
    float                 black_cutoff,
    std::vector<PixelT>  &buffer,
    const PixelT*        &out_ptr,
    std::ptrdiff_t       &out_pitch)
{
    out_ptr = nullptr;
    out_pitch = 0;

    if (!world || (strength <= 0.0f && black_cutoff <= 0.0f)) {
        return;
    }

    const A_long width  = world->width;
    const A_long height = world->height;
    if (width <= 1 || height <= 1) {
        return;
    }

    buffer.resize(static_cast<std::size_t>(width) *
                  static_cast<std::size_t>(height));

    const std::ptrdiff_t row_bytes = static_cast<std::ptrdiff_t>(world->rowbytes);
    for (A_long y = 0; y < height; ++y) {
        const char *row_base = reinterpret_cast<const char*>(world->data);
        if (row_bytes < 0) {
            row_base += (world->height - 1 - y) * (-row_bytes);
        } else {
            row_base += y * row_bytes;
        }

        const PixelT *src_row = reinterpret_cast<const PixelT*>(row_base);
        PixelT *dst_row = buffer.data() + static_cast<std::size_t>(y) * static_cast<std::size_t>(width);
        std::copy(src_row, src_row + width, dst_row);
    }

    apply_black_edge_sharpen(
        buffer.data(),
        static_cast<std::ptrdiff_t>(width),
        static_cast<std::int32_t>(width),
        static_cast<std::int32_t>(height),
        strength,
        black_cutoff);

    out_ptr   = buffer.data();
    out_pitch = static_cast<std::ptrdiff_t>(width);
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

    const PF_Pixel8 *srcP = inP;
    if (ref->pre_sharpen_argb) {
        srcP = ref->pre_sharpen_argb +
            ref->pre_sharpen_pitch * static_cast<std::ptrdiff_t>(yL) +
            static_cast<std::ptrdiff_t>(xL);
    }

    // 入力色をローカルコピー
    A_u_char r = srcP->red;
    A_u_char g = srcP->green;
    A_u_char b = srcP->blue;

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

    const MSX1PQ_Pixel_BGRA_8u *srcP = inBGRA_8uP;
    if (ref->pre_sharpen_bgra) {
        srcP = ref->pre_sharpen_bgra +
            ref->pre_sharpen_pitch * static_cast<std::ptrdiff_t>(yL) +
            static_cast<std::ptrdiff_t>(xL);
    }

    A_u_char r = srcP->red;
    A_u_char g = srcP->green;
    A_u_char b = srcP->blue;

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
    qi.use_hsv         = (params[MSX1PQ_PARAM_DISTANCE_MODE]->u.pd.value == MSX1PQ_DIST_MODE_HSV);

    qi.w_h = clamp01f(
        static_cast<float>(params[MSX1PQ_PARAM_WEIGHT_H]->u.fs_d.value));
    qi.w_s = clamp01f(
        static_cast<float>(params[MSX1PQ_PARAM_WEIGHT_S]->u.fs_d.value));
    qi.w_b = clamp01f(
        static_cast<float>(params[MSX1PQ_PARAM_WEIGHT_B]->u.fs_d.value));
    qi.w_r = clamp01f(
        static_cast<float>(params[MSX1PQ_PARAM_WEIGHT_R]->u.fs_d.value));
    qi.w_g = clamp01f(
        static_cast<float>(params[MSX1PQ_PARAM_WEIGHT_G]->u.fs_d.value));
    qi.w_b_rgb = clamp01f(
        static_cast<float>(params[MSX1PQ_PARAM_WEIGHT_B_RGB]->u.fs_d.value));

    qi.pre_posterize = clamp_value(
        static_cast<int>(params[MSX1PQ_PARAM_PRE_POSTERIZE]->u.fs_d.value + 0.5),
        0,
        255);
    qi.pre_sat       = static_cast<float>(params[MSX1PQ_PARAM_PRE_SAT]->u.fs_d.value);
    qi.pre_gamma     = static_cast<float>(params[MSX1PQ_PARAM_PRE_GAMMA]->u.fs_d.value);
    qi.pre_contrast  = static_cast<float>(params[MSX1PQ_PARAM_PRE_CONTRAST]->u.fs_d.value);
    qi.pre_hue       = static_cast<float>(params[MSX1PQ_PARAM_PRE_HUE]->u.fs_d.value);
    qi.pre_black_cutoff = clamp01f(
        static_cast<float>(params[MSX1PQ_PARAM_PRE_BLACK_CUTOFF]->u.fs_d.value));
    qi.pre_sharpen_black = clamp_value(
        static_cast<float>(params[MSX1PQ_PARAM_PRE_SHARPEN_BLACK]->u.fs_d.value),
        0.0f,
        10.0f);

    qi.use_dark_dither = (params[MSX1PQ_PARAM_USE_DARK_DITHER]->u.bd.value != 0);

    for (int i = 0; i < MSX1PQ::kNumBasicColors; ++i) {
        const PF_ParamIndex flag_index = static_cast<PF_ParamIndex>(MSX1PQ_PARAM_COLOR_FLAG_1 + i);
        if (flag_index < MSX1PQ_PARAM_NUM_PARAMS) {
            qi.palette_enabled[static_cast<std::size_t>(i)] =
                (params[flag_index]->u.bd.value != 0);
        }
    }

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

            std::vector<MSX1PQ_Pixel_BGRA_8u> sharpen_buffer;
            if (qi.pre_sharpen_black > 0.0f || qi.pre_black_cutoff > 0.0f) {
                BuildPreSharpenBuffer(
                    reinterpret_cast<PF_EffectWorld*>(
                        &params[MSX1PQ_PARAM_INPUT]->u.ld),
                    qi.pre_sharpen_black,
                    qi.pre_black_cutoff,
                    sharpen_buffer,
                    refcon.pre_sharpen_bgra,
                    refcon.pre_sharpen_pitch);
            }

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

        std::vector<PF_Pixel8> sharpen_buffer;
        if (qi.pre_sharpen_black > 0.0f || qi.pre_black_cutoff > 0.0f) {
            BuildPreSharpenBuffer(
                reinterpret_cast<PF_EffectWorld*>(
                    &params[MSX1PQ_PARAM_INPUT]->u.ld),
                qi.pre_sharpen_black,
                qi.pre_black_cutoff,
                sharpen_buffer,
                refcon.pre_sharpen_argb,
                refcon.pre_sharpen_pitch);
        }

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
        qi.use_hsv = (param.u.pd.value == MSX1PQ_DIST_MODE_HSV);
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

        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_WEIGHT_R,
                param) );
        qi.w_r = clamp01f(static_cast<float>(param.u.fs_d.value));
        ERR( CheckinParam(in_dataP, param) );

        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_WEIGHT_G,
                param) );
        qi.w_g = clamp01f(static_cast<float>(param.u.fs_d.value));
        ERR( CheckinParam(in_dataP, param) );

        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_WEIGHT_B_RGB,
                param) );
        qi.w_b_rgb = clamp01f(static_cast<float>(param.u.fs_d.value));
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

        // PRE_SAT / GAMMA / CONTRAST / HUE
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
                MSX1PQ_PARAM_PRE_CONTRAST,
                param) );
        qi.pre_contrast = static_cast<float>(param.u.fs_d.value);
        ERR( CheckinParam(in_dataP, param) );

        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_PRE_HUE,
                param) );
        qi.pre_hue = static_cast<float>(param.u.fs_d.value);
        ERR( CheckinParam(in_dataP, param) );

        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_PRE_BLACK_CUTOFF,
                param) );
        qi.pre_black_cutoff = clamp01f(static_cast<float>(param.u.fs_d.value));
        ERR( CheckinParam(in_dataP, param) );

        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_PRE_SHARPEN_BLACK,
                param) );
        qi.pre_sharpen_black = clamp_value(
            static_cast<float>(param.u.fs_d.value),
            0.0f,
            10.0f);
        ERR( CheckinParam(in_dataP, param) );

        // USE_DARK_DITHER
        ERR( CheckoutParam(
                in_dataP,
                MSX1PQ_PARAM_USE_DARK_DITHER,
                param) );
        qi.use_dark_dither = (param.u.bd.value != 0);
        ERR( CheckinParam(in_dataP, param) );

        for (int i = 0; i < MSX1PQ::kNumBasicColors; ++i) {
            const PF_ParamIndex flag_index = static_cast<PF_ParamIndex>(MSX1PQ_PARAM_COLOR_FLAG_1 + i);
            ERR( CheckoutParam(
                    in_dataP,
                    flag_index,
                    param) );
            qi.palette_enabled[static_cast<std::size_t>(i)] = (param.u.bd.value != 0);
            ERR( CheckinParam(in_dataP, param) );
        }

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

            std::vector<PF_Pixel8> sharpen_buffer;
            if (qi.pre_sharpen_black > 0.0f || qi.pre_black_cutoff > 0.0f) {
                BuildPreSharpenBuffer(
                    &input_roi,
                    qi.pre_sharpen_black,
                    qi.pre_black_cutoff,
                    sharpen_buffer,
                    refcon.pre_sharpen_argb,
                    refcon.pre_sharpen_pitch);
            }

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
    A_Boolean enable_hsv = (mode == MSX1PQ_DIST_MODE_HSV);
    A_Boolean enable_rgb = (mode == MSX1PQ_DIST_MODE_RGB);

    // MyDebugLog("=== UpdateParameterUI CALLED ===");
    // MyDebugLog("UpdateParameterUI: mode=%ld enable_hsv=%d",
    //          mode, enable_hsv ? 1 : 0);

    PF_ParamDef tmp;

    // --- H weight ---
    tmp = *params[MSX1PQ_PARAM_WEIGHT_H];
    if (enable_hsv)
        tmp.ui_flags &= ~PF_PUI_DISABLED;
    else
        tmp.ui_flags |= PF_PUI_DISABLED;
    // MyDebugLog("  H ui_flags(new)=0x%08x", tmp.ui_flags);
    paramUtils->PF_UpdateParamUI(in_data->effect_ref,
                                 MSX1PQ_PARAM_WEIGHT_H,
                                 &tmp);

    // --- S weight ---
    tmp = *params[MSX1PQ_PARAM_WEIGHT_S];
    if (enable_hsv)
        tmp.ui_flags &= ~PF_PUI_DISABLED;
    else
        tmp.ui_flags |= PF_PUI_DISABLED;
    // MyDebugLog("  S ui_flags(new)=0x%08x", tmp.ui_flags);
    paramUtils->PF_UpdateParamUI(in_data->effect_ref,
                                 MSX1PQ_PARAM_WEIGHT_S,
                                 &tmp);

    // --- V weight ---
    tmp = *params[MSX1PQ_PARAM_WEIGHT_B];
    if (enable_hsv)
        tmp.ui_flags &= ~PF_PUI_DISABLED;
    else
        tmp.ui_flags |= PF_PUI_DISABLED;
    // MyDebugLog("  B ui_flags(new)=0x%08x", tmp.ui_flags);
    paramUtils->PF_UpdateParamUI(in_data->effect_ref,
                                 MSX1PQ_PARAM_WEIGHT_B,
                                 &tmp);

    // --- R weight ---
    tmp = *params[MSX1PQ_PARAM_WEIGHT_R];
    if (enable_rgb)
        tmp.ui_flags &= ~PF_PUI_DISABLED;
    else
        tmp.ui_flags |= PF_PUI_DISABLED;
    paramUtils->PF_UpdateParamUI(in_data->effect_ref,
                                 MSX1PQ_PARAM_WEIGHT_R,
                                 &tmp);

    // --- G weight ---
    tmp = *params[MSX1PQ_PARAM_WEIGHT_G];
    if (enable_rgb)
        tmp.ui_flags &= ~PF_PUI_DISABLED;
    else
        tmp.ui_flags |= PF_PUI_DISABLED;
    paramUtils->PF_UpdateParamUI(in_data->effect_ref,
                                 MSX1PQ_PARAM_WEIGHT_G,
                                 &tmp);

    // --- B weight ---
    tmp = *params[MSX1PQ_PARAM_WEIGHT_B_RGB];
    if (enable_rgb)
        tmp.ui_flags &= ~PF_PUI_DISABLED;
    else
        tmp.ui_flags |= PF_PUI_DISABLED;
    paramUtils->PF_UpdateParamUI(in_data->effect_ref,
                                 MSX1PQ_PARAM_WEIGHT_B_RGB,
                                 &tmp);

    return err;
}

static PF_Err
RefreshPaletteFlagsUI(
    PF_InData   *in_data,
    PF_OutData  *out_data)
{
    PF_Err err = PF_Err_NONE;

    AEFX_SuiteScoper<PF_ParamUtilsSuite3> paramUtils(
        in_data,
        kPFParamUtilsSuite,
        kPFParamUtilsSuiteVersion3,
        out_data);

    PF_ParamDef tmp;
    for (A_long i = MSX1PQ_PARAM_COLOR_FLAG_1;
         i <= MSX1PQ_PARAM_COLOR_FLAG_15 && !err;
         ++i) {
        ERR( CheckoutParam(
                in_data,
                static_cast<PF_ParamIndex>(i),
                tmp) );
        if (!err) {
            paramUtils->PF_UpdateParamUI(
                in_data->effect_ref,
                static_cast<PF_ParamIndex>(i),
                &tmp);
            ERR( CheckinParam(in_data, tmp) );
        }
    }

    return err;
}

static PF_Err
SetPaletteFlagValue(
    PF_InData    *in_data,
    PF_ParamDef  *params[],
    PF_ParamIndex index,
    A_Boolean     value)
{
    PF_Err err = PF_Err_NONE;
    PF_ParamDef temp_param;

    ERR( CheckoutParam(in_data, index, temp_param) );
    if (!err) {
        if (temp_param.param_type == PF_Param_CHECKBOX) {
            temp_param.u.bd.value = value;
            temp_param.uu.change_flags = PF_ChangeFlag_CHANGED_VALUE;
            params[index]->u.bd.value = value;
            params[index]->uu.change_flags = PF_ChangeFlag_CHANGED_VALUE;
        }
        ERR( CheckinParam(in_data, temp_param) );
    }

    return err;
}


static PF_Err
HandleEvent(
    PF_InData     *in_data,
    PF_OutData    *out_data,
    PF_ParamDef   *params[],
    PF_LayerDef   *output,
    PF_EventExtra *extra)
{
    PF_Err err = PF_Err_NONE;

    (void)output;

    if (!extra) {
        return err;
    }

    if (extra->e_type == PF_Event_DRAW &&
        extra->effect_win.index == MSX1PQ_PARAM_SWATCH_ROW) {
        MyDebugLog("HandleEvent: draw index=%d area=%d", extra->effect_win.index, extra->effect_win.area);
        err = DrawSwatchRow(in_data, out_data, params, extra);
    }

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

    // Log command at entry
    switch (cmd) {
    case PF_Cmd_ABOUT:
        MyDebugLog("CMD: ABOUT");
        break;
    case PF_Cmd_GLOBAL_SETUP:
        MyDebugLog("CMD: GLOBAL_SETUP");
        break;
    case PF_Cmd_PARAMS_SETUP:
        MyDebugLog("CMD: PARAMS_SETUP");
        break;
    case PF_Cmd_RENDER:
        MyDebugLog("CMD: RENDER");
        break;
    case PF_Cmd_SMART_PRE_RENDER:
        MyDebugLog("CMD: SMART_PRE_RENDER");
        break;
    case PF_Cmd_SMART_RENDER:
        MyDebugLog("CMD: SMART_RENDER");
        break;
    case PF_Cmd_USER_CHANGED_PARAM:
        MyDebugLog("CMD: USER_CHANGED_PARAM");
        break;
    case PF_Cmd_EVENT:
        MyDebugLog("CMD: EVENT");
        break;
    default:
        MyDebugLog("CMD: %d (other)", (int)cmd);
        break;
    }

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
                //MyDebugLog("PARAMS_SETUP start");
                err = ParamsSetup(in_dataP, out_data, params, output);
                break;
            case PF_Cmd_USER_CHANGED_PARAM:
            {

                std::random_device rd;
                std::mt19937 gen(rd());
                std::bernoulli_distribution dist(0.5);

                PF_UserChangedParamExtra *extraP =
                    reinterpret_cast<PF_UserChangedParamExtra*>(extra);

                //MyDebugLog("USER_CHANGED_PARAM: index=%d", static_cast<int>(extraP->param_index));
                //MyDebugLog("Check RANDOM index=%d target=%d", extraP->param_index, MSX1PQ_PARAM_RANDOMIZE_PALETTE_FLAGS);
                if (extraP->param_index == MSX1PQ_PARAM_DISTANCE_MODE) {
                    UpdateParameterUI(in_dataP, out_data, params);
                } else if (extraP && extraP->param_index == MSX1PQ_PARAM_RANDOMIZE_PALETTE_FLAGS)
                {
                    A_long changed_count = 0;
                    PF_ParamDef temp_param;

                    for (A_long i = MSX1PQ_PARAM_COLOR_FLAG_1;
                         i <= MSX1PQ_PARAM_COLOR_FLAG_15;
                         ++i)
                    {
                        ERR( CheckoutParam(in_dataP, (PF_ParamIndex)i, temp_param) );

                        if (temp_param.param_type != PF_Param_CHECKBOX) {
                            ERR( CheckinParam(in_dataP, temp_param) );
                            continue;
                        }

                        const A_Boolean old_v = temp_param.u.bd.value;
                        const A_Boolean new_v = dist(gen) ? TRUE : FALSE;

                        if (old_v != new_v)
                        {
                            temp_param.u.bd.value = new_v;
                            temp_param.uu.change_flags = PF_ChangeFlag_CHANGED_VALUE;
                            params[i]->u.bd.value = new_v;
                            params[i]->uu.change_flags = PF_ChangeFlag_CHANGED_VALUE;

                            ERR( CheckinParam(in_dataP, temp_param) );

                            changed_count++;
                        } else {
                            ERR( CheckinParam(in_dataP, temp_param) );
                        }
                    }

                    if (changed_count > 0) {
                        ERR( RefreshPaletteFlagsUI(in_dataP, out_data) );
                        if (!err) {
                            out_data->out_flags |= PF_OutFlag_FORCE_RERENDER;
                            out_data->out_flags |= PF_OutFlag_REFRESH_UI;
                            out_data->out_flags |= PF_OutFlag_SEND_UPDATE_PARAMS_UI;
                        }
                    }

                    //MyDebugLog("RANDOMIZE done changed_count=%d", (int)changed_count);
                } else if (extraP && extraP->param_index == MSX1PQ_PARAM_RANDOMIZE_PLUS_ONE) {
                    PF_ParamDef temp_param;
                    PF_ParamIndex candidates[MSX1PQ::kNumBasicColors]{};
                    A_long candidate_count = 0;

                    for (A_long i = MSX1PQ_PARAM_COLOR_FLAG_1;
                         i <= MSX1PQ_PARAM_COLOR_FLAG_15;
                         ++i)
                    {
                        ERR( CheckoutParam(in_dataP, (PF_ParamIndex)i, temp_param) );

                        if (temp_param.param_type != PF_Param_CHECKBOX) {
                            ERR( CheckinParam(in_dataP, temp_param) );
                            continue;
                        }

                        const bool enabled = (temp_param.u.bd.value != 0);
                        ERR( CheckinParam(in_dataP, temp_param) );

                        if (!enabled && candidate_count < static_cast<A_long>(MSX1PQ::kNumBasicColors)) {
                            candidates[candidate_count++] = static_cast<PF_ParamIndex>(i);
                        }
                    }

                    if (candidate_count > 0) {
                        std::uniform_int_distribution<A_long> pick(0, candidate_count - 1);
                        const PF_ParamIndex target = candidates[pick(gen)];

                        ERR( SetPaletteFlagValue(in_dataP, params, target, TRUE) );
                        if (!err) {
                            ERR( RefreshPaletteFlagsUI(in_dataP, out_data) );
                            out_data->out_flags |= PF_OutFlag_FORCE_RERENDER;
                            out_data->out_flags |= PF_OutFlag_REFRESH_UI;
                            out_data->out_flags |= PF_OutFlag_SEND_UPDATE_PARAMS_UI;
                            // MyDebugLog("RND+1: enabled index=%d", static_cast<int>(target));
                        }
                    } else {
                        // MyDebugLog("RND+1: no disabled color to enable");
                    }
                } else if (extraP && extraP->param_index == MSX1PQ_PARAM_RANDOMIZE_MINUS_ONE) {
                    PF_ParamDef temp_param; // ????PF_ParamDef
                    PF_ParamIndex candidates[MSX1PQ::kNumBasicColors]{};
                    A_long candidate_count = 0;

                    for (A_long i = MSX1PQ_PARAM_COLOR_FLAG_1;
                         i <= MSX1PQ_PARAM_COLOR_FLAG_15;
                         ++i)
                    {
                        ERR( CheckoutParam(in_dataP, (PF_ParamIndex)i, temp_param) );

                        if (temp_param.param_type != PF_Param_CHECKBOX) {
                            ERR( CheckinParam(in_dataP, temp_param) );
                            continue;
                        }

                        const bool enabled = (temp_param.u.bd.value != 0);
                        ERR( CheckinParam(in_dataP, temp_param) );

                        if (enabled && candidate_count < static_cast<A_long>(MSX1PQ::kNumBasicColors)) {
                            candidates[candidate_count++] = static_cast<PF_ParamIndex>(i);
                        }
                    }

                    if (candidate_count > 0) {
                        std::uniform_int_distribution<A_long> pick(0, candidate_count - 1);
                        const PF_ParamIndex target = candidates[pick(gen)];

                        ERR( SetPaletteFlagValue(in_dataP, params, target, FALSE) );
                        if (!err) {
                            ERR( RefreshPaletteFlagsUI(in_dataP, out_data) );
                            out_data->out_flags |= PF_OutFlag_FORCE_RERENDER;
                            out_data->out_flags |= PF_OutFlag_REFRESH_UI;
                            out_data->out_flags |= PF_OutFlag_SEND_UPDATE_PARAMS_UI;
                            //MyDebugLog("RND-1: disabled index=%d", static_cast<int>(target));
                        }
                    } else {
                        //MyDebugLog("RND-1: no enabled color to disable");
                    }
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
            case PF_Cmd_EVENT:
            {
                PF_EventExtra* ev = reinterpret_cast<PF_EventExtra*>(extra);
                //MyDebugLog("PF_Cmd_EVENT command received");
                if (!ev) {
                    break;
                }

                MyDebugLog("EVENT: e_type=%d", (int)ev->e_type);

                err = HandleEvent(
                    in_dataP,
                    out_data,
                    params,
                    output,
                    ev);

                break;
            }
        }
    } catch(PF_Err &thrown_err) {
        // AE に例外を飛ばさない
        err = thrown_err;
    }
    return err;
}
