#pragma once
#ifndef MSX1_PALETTE_QUANTIZER_H
#define MSX1_PALETTE_QUANTIZER_H

#include "AEConfig.h"
#include "entry.h"
#include "AEFX_SuiteHelper.h"
#include "PrSDKAESupport.h"
#include "AE_Effect.h"
#include "AE_EffectCB.h"
#include "AE_EffectCBSuites.h"
#include "AE_Macros.h"
#include "AEGP_SuiteHandler.h"
#include "String_Utils.h"
#include "Param_Utils.h"
#include "Smart_Utils.h"

#include <cstdint>

#include "../core/MSX1PQCore.h"

// ParamsSetup() の追加順と必ず一致させること
enum MSX1PQ_ParamId {
    MSX1PQ_PARAM_INPUT = 0,       // Input layer

    MSX1PQ_PARAM_COLOR_SYSTEM,    // MSX1 / MSX2
    MSX1PQ_PARAM_USE_DITHER,      // Dither ON/OFF
    MSX1PQ_PARAM_USE_DARK_DITHER, // Whether to use a dark dither palette
    MSX1PQ_PARAM_USE_8DOT2COL,    // 8dot / 2col restriction mode
    MSX1PQ_PARAM_DISTANCE_MODE,   // Distance calculation method (RGB/HSB)
    MSX1PQ_PARAM_WEIGHT_H,        // H intensity
    MSX1PQ_PARAM_WEIGHT_S,        // S intensity
    MSX1PQ_PARAM_WEIGHT_B,        // B intensity

    MSX1PQ_PARAM_PRE_POSTERIZE,   // Posterize before preprocessing
    MSX1PQ_PARAM_PRE_SAT,         // Saturation boost
    MSX1PQ_PARAM_PRE_GAMMA,       // Gamma to enhance shadows
    MSX1PQ_PARAM_PRE_HIGHLIGHT,   // Highlight correction
    MSX1PQ_PARAM_PRE_HUE,         // Hue rotation
    MSX1PQ_PARAM_PRE_SHARPNESS,   // Sharpen amount
    MSX1PQ_PARAM_PRE_SHARP_THRESHOLD, // Black-level threshold for sharpening

    MSX1PQ_PARAM_USE_PALETTE_COLOR, // Use 92-color palette directly

    MSX1PQ_PARAM_NUM_PARAMS
};

extern "C" {

        DllExport
        PF_Err
        EffectMain (
                PF_Cmd                  cmd,
                PF_InData               *in_data,
                PF_OutData              *out_data,
                PF_ParamDef             *params[],
                PF_LayerDef             *output,
                void                    *extra);

}

typedef struct {
        std::uint8_t blue, green, red, alpha;
} MSX1PQ_Pixel_BGRA_8u;

#endif // MSX1_PALETTE_QUANTIZER_H
