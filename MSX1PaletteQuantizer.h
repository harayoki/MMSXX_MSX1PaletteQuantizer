
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



// ParamsSetup() ÇÃí«â¡èáÇ∆ïKÇ∏àÍívÇ≥ÇπÇÈÇ±Ç∆
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

    MSX1PQ_PARAM_PRE_SAT,         // Saturation boost
    MSX1PQ_PARAM_PRE_GAMMA,       // Gamma to enhance shadows
    MSX1PQ_PARAM_PRE_HIGHLIGHT,   // Highlight correction
    MSX1PQ_PARAM_PRE_SKIN,        // Skin tone adjustment

    MSX1PQ_PARAM_NUM_PARAMS
};


enum MSX1PQ_DistanceMode {
     MSX1PQ_DIST_MODE_RGB = 1,
     MSX1PQ_DIST_MODE_HSB = 2
 };

enum MSX1PQ_EightDotMode {
    MSX1PQ_EIGHTDOT_MODE_NONE   = 1, // None
    MSX1PQ_EIGHTDOT_MODE_FAST1  = 2, // Lightweight version
    MSX1PQ_EIGHTDOT_MODE_BASIC1 = 3, // Standard version
    MSX1PQ_EIGHTDOT_MODE_BEST1  = 4,  // Best version
    MSX1PQ_EIGHTDOT_MODE_ATTR_BEST = 5, // Attribute cell BEST (8Å~N)
    MSX1PQ_EIGHTDOT_MODE_PENALTY_BEST = 6  // Transition penalty BEST
 };

enum MSX1PQ_ColorSystem {
    MSX1PQ_COLOR_SYS_MSX1 = 1,
    MSX1PQ_COLOR_SYS_MSX2 = 2
};

extern "C" {

	DllExport 
	PF_Err
	EffectMain (	
		PF_Cmd			cmd,
		PF_InData		*in_data,
		PF_OutData		*out_data,
		PF_ParamDef		*params[],
		PF_LayerDef		*output,
		void			*extra);

}

typedef struct {
	A_u_char	blue, green, red, alpha;
} PF_Pixel_BGRA_8u;

//typedef struct {
//	A_u_char	Pr, Pb, luma, alpha;
//} PF_Pixel_VUYA_8u;
//
//typedef struct {
//	PF_FpShort	blue, green, red, alpha;
//} PF_Pixel_BGRA_32f;
//
//typedef struct {
//	PF_FpShort	Pr, Pb, luma, alpha;
//} PF_Pixel_VUYA_32f;

#endif