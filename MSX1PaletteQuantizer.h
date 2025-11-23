
#pragma once
#ifndef MYPLUG1_H
#define MYPLUG1_H

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

#ifdef AE_OS_WIN
#include <Windows.h>
#include <cstdarg>
#include <cstdio>
inline void DebugLog(const char* fmt, ...)
{
    char buf[512];

    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);

    OutputDebugStringA(buf);
    OutputDebugStringA("\n");
}

#else  // Mac ÇÃèÍçáÅiAE_OS_WIN Ç™ñ¢íËã`Åj
inline void DebugLog(const char* /*fmt*/, ...) {}
#endif


#define DESCRIPTION	"\nMSX1-style palette quantization and dithering."

#define NAME			"MSX1 Palette Quantizer"
#define	MAJOR_VERSION	5
#define	MINOR_VERSION	6
#define	BUG_VERSION		0
#define	STAGE_VERSION	PF_Stage_DEVELOP
#define	BUILD_VERSION	1

enum {
    PARAM_INPUT = 0,       // Input layer

    PARAM_COLOR_SYSTEM,    // MSX1 / MSX2
    PARAM_USE_DITHER,      // Dither ON/OFF
    PARAM_USE_8DOT2COL,    // 8dot / 2col restriction mode
    PARAM_DISTANCE_MODE,   // Distance calculation method (RGB/HSB)
    PARAM_WEIGHT_H,        // H intensity
    PARAM_WEIGHT_S,        // S intensity
    PARAM_WEIGHT_B,        // B intensity

    PARAM_PRE_SAT,         // Saturation boost
    PARAM_PRE_GAMMA,       // Gamma to enhance shadows
    PARAM_PRE_HIGHLIGHT,   // Highlight correction
    PARAM_PRE_SKIN,        // Skin tone adjustment

    PARAM_USE_DARK_DITHER, // Whether to use a dark dither palette
    PARAM_NUM_PARAMS
};

typedef enum {
    DIST_MODE_RGB = 1,
    DIST_MODE_HSB = 2
} DistanceMode;

typedef enum {
    EIGHTDOT_MODE_NONE   = 1, // None
    EIGHTDOT_MODE_FAST1  = 2, // Lightweight version
    EIGHTDOT_MODE_BASIC1 = 3, // Standard version
    EIGHTDOT_MODE_BEST1  = 4,  // Best version
    EIGHTDOT_MODE_ATTR_BEST = 5, // Attribute cell BEST (8Å~N)
    EIGHTDOT_MODE_PENALTY_BEST = 6  // Transition penalty BEST
} EightDotMode;

typedef enum {
    COLOR_SYS_MSX1 = 1,
    COLOR_SYS_MSX2 = 2
} ColorSystem;


#define SLIDER_MIN			0
#define	SLIDER_MAX			100

#define RESTRICT_BOUNDS			0
#define SLIDER_PRECISION		1
#define DISPLAY_FLAGS			PF_ValueDisplayFlag_PERCENT


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

typedef struct {
	A_u_char	Pr, Pb, luma, alpha;
} PF_Pixel_VUYA_8u;

typedef struct {
	PF_FpShort	blue, green, red, alpha;
} PF_Pixel_BGRA_32f;

typedef struct {
	PF_FpShort	Pr, Pb, luma, alpha;
} PF_Pixel_VUYA_32f;

#endif