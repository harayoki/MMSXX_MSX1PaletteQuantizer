#include "AEConfig.h"
#include "AE_EffectVers.h"

#ifndef AE_OS_WIN
	#include "AE_General.r"
#endif

resource 'PiPL' (16000) {
	{
		Kind {
			AEEffect
		},
		Name {
			"MSX1 Palette Quantizer"
		},
		Category {
			"MMSXX"
		},
#ifdef AE_OS_WIN
    #if defined(AE_PROC_INTELx64)
		CodeWin64X86 {"EffectMain"},
    #elif defined(AE_PROC_ARM64)
		CodeWinARM64 {"EffectMain"},
    #endif
#elif defined(AE_OS_MAC)
		CodeMacIntel64 {"EffectMain"},
		CodeMacARM64 {"EffectMain"},
#endif
		AE_PiPL_Version {
			2,
			0
		},
		AE_Effect_Spec_Version {
			PF_PLUG_IN_VERSION,
			PF_PLUG_IN_SUBVERS
		},
        AE_Effect_Version {
                263169
            /*
            You can also calculate it as follows to match the specified values in the GlobalSetup function.
            Major, Minor, Bug, Stage, Build
            (ST =  0:dev 1:alpha 2:beta 3:release)
            python -c "import sys;M,S,B,ST,BL=map(int,sys.argv[1:]);print(((M>>3)&15)<<26 | (M&7)<<19 | (S&15)<<15 | (B&15)<<11 | (ST&3)<<9 | (BL&0x1FF))" 0 8 0 2 1
            */
		},
		AE_Effect_Info_Flags {
			0
		},
		AE_Effect_Global_OutFlags {
			0x00008000
			/*
			    PF_OutFlag_NONE: 0x00000000
    			PF_OutFlag_SEND_UPDATE_PARAMS_UI: 0x04000000
    			PF_OutFlag_CUSTOM_UI: 0x00008000
			*/
		},
        AE_Effect_Global_OutFlags_2 {
            0x08000400
            /*
                PF_OutFlag2_NONE: 0x00000000
                PF_OutFlag2_SUPPORTS_SMART_RENDER: 0x00000400
                PF_OutFlag2_SUPPORTS_THREADED_RENDERING: 0x08000000?
            */
        },
		AE_Effect_Match_Name {
			"MMSXX_MSX1PaletteQuantizer"
		},
		AE_Reserved_Info {
			0
		},
		AE_Effect_Support_URL {
			"https://github.com/harayoki/MMSXX_MSX1PaletteQuantizer"
		}
	}
};
