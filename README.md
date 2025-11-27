# MMSXX_MSX1PaletteQuantizer (for AfterFX / Premiere PRO / CLI)

MSX1-style effect plugin for Adobe After Effects (AE) / Premiere PRO / CLI

日本語版のドキュメント：[README_ja](README_ja.md)

| source movie | result |
|---------|--------|
|![source_movie_capture](docs%2Fsource_movie_capture.png)|![result_capture](docs%2Fresult_capture.png)|

## sample movies

* [Wing It in 8-bit MSX (TMS9918) Colors](https://www.youtube.com/watch?v=HZ43BCsNMus) - YouTube - (C) Blender Foundation | studio.blender.org

|                                            |                                            |
|------------------------------------------------|------------------------------------------------|
| ![capture_00008.png](docs%2Fcapture_00010.png) | ![capture_00009.png](docs%2Fcapture_00011.png) |

* [MSX Girl at Kichijoji station (in Tokyo) Pixel Art Video](https://www.youtube.com/watch?v=-X0sMmEDrdY) - YouTube
* [Comparison Video of Original and Effect Applied](https://www.youtube.com/shorts/yKph3DFmB7M) - YouTube Shorts

## Overview

"MSX1PaletteQuantizer" is an effect plugin that recreates the MSX1 (TMS9918) look in compositions.
It imitates the graphics style specific to MSX1, based on rules (15 colors, 2 colors within an 8-dot horizontal area).

## Disclaimer

The author assumes no responsibility for any damages caused by the use of this plugin. Use it at your own risk.

## Supported Platforms

- Windows
- Adobe After Effects CC 2018? or later
- Adobe Premiere Pro CC 2018? or later

It should also work on Mac if built with Xcode.

## Installation

1.  Obtain the plugin file (.aex or .plugin).
2.  Copy the plugin file to the common plugin folder of After Effects / Premiere PRO.
    - Windows: `C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore\`

## How to Use

1.  Launch After Effects.
2.  Add your footage to a composition.
3.  Select "MMSXX" > "MSX1PaletteQuantizer" from the effects menu and apply it to the footage.
4.  Adjust settings in the Effect Controls panel.

The same steps can be used for Premiere Pro.

For detailed usage and settings of MSX1PaletteQuantizer, please refer to:
* [How to use in After Effects](docs/AE_guide_en.md)
* https://note.com/harayoki/n/nef7d2f9b5380 note article

For command line usage, see:
* [CLI usage guide](docs/CLI_guide_en.md)

## Build Instructions for Visual Studio 2022 (Windows)

Build the project using Visual Studio (Windows) or Xcode (Mac).
Upon successful build, a plugin file (.aex or .plugin) will be generated.

*   In "x64 Native Tools Command Prompt for VS2022", set `AESDK_ROOT` to the After Effects SDK path.
    *   `setx AESDK_ROOT F:\ae25.6_61.64bit.AfterEffectsSDK\Examples\`
*   Restart Command Prompt.
*   Navigate to the root directory of this repository.
    *   `cd {your_pc_path}\MMSXX_MSX1PaletteQuantizer`
*   Build with `msbuild` command.
    *   `msbuild platform\Win\MSX1PaletteQuantizer.sln /p:Configuration=Release /p:Platform=x64`

`MMSXX_MSX1PaletteQuantizer.aex` will be generated in the `platform\Win\x64` folder.

## Build Instructions for Xcode (Mac)

*   Set the `AESDK_ROOT` environment variable to the root of your After Effects SDK installation (e.g., `/Applications/Adobe After Effects 2023/Support Files/After Effects SDK`).
*   Open `platform/Mac/MSX1PaletteQuantizer.xcodeproj` in Xcode.
*   Build the `MSX1PaletteQuantizer` target to produce `MSX1PaletteQuantizer.plugin`.

## Implementation Details

The plugin is written in legacy C++. It does not support GPU utilization, parallel processing, or smart rendering. Additionally, it only supports 8-bit mode.  
Code modifications to address these limitations are highly welcome. Porting to free or low-cost video editing software (e.g., OpenFX format) is also encouraged.

## License

* Released under the MIT License.
  * [LICENSE](LICENSE)
* The CLI version uses the PNG encoder/decoder library "lodepng".
  * https://github.com/lvandeve/lodepng/
  * [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt)
