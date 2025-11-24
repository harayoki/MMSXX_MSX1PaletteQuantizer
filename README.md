# MMSXX_MSX1PaletteQuantizer

日本語版のドキュメント：[README_ja](README_ja.md)

MSX1-style effect plugin for Adobe After Effects (AE) / Premiere PRO

## Overview

"MSX1PaletteQuantizer" is an effect plugin that recreates the MSX1 (TMS9918) look in compositions.
It imitates the graphics style specific to MSX1, based on rules (15 colors, 2 colors within an 8-dot horizontal area).

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
* [How to use in After Effects](docs/MSX1_effect_guide_en.md)
* https://note.com/harayoki/n/nef7d2f9b5380?from=notice note article

## Build Instructions for Visual Studio 2022 (Windows)

Build the project using Visual Studio (Windows) or Xcode (Mac).
Upon successful build, a plugin file (.aex or .plugin) will be generated.

*   In "x64 Native Tools Command Prompt for VS2022", set `AESDK_ROOT` to the After Effects SDK path.
    *   `setx AESDK_ROOT F:\ae25.6_61.64bit.AfterEffectsSDK\Examples\`
*   Restart Command Prompt.
*   Navigate to the root directory of this repository.
    *   `cd {your_pc_path}\MMSXX_MSX1PaletteQuantizer`
*   Build with `msbuild` command.
    *   `msbuild Win\MSX1PaletteQuantizer.sln /p:Configuration=Release /p:Platform=x64`

`MMSXX_MSX1PaletteQuantizer.aex` will be generated in the `Win\x64` folder.

## Build Instructions for Xcode (Mac)

Untested. The Xcode project included in the repository may contain incorrect information.

## License

Released under the MIT License. [LICENSE](LICENSE)