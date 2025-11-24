# How to use in After Effects

## 1. Recommended Initial Settings

-   **Composition Settings**: Place your footage in a composition with a size of `256x192`.
-   **Layer Settings**: Change the layer's quality setting from "Bilinear" to "Nearest Neighbor" to disable anti-aliasing.

## 2. Applying the Effect

Apply "MSX1 Palette Quantizer" from the effects menu.

## 3. Basic Color Adjustment

It is recommended to apply the following adjustments before the MSX1 effect.
-   **Tone Curve**: Adjusts the overall brightness.
-   **Sharpness**: Sharpens the image.
-   **Saturation**: Adjusts the saturation.
-   **LOOK (LUT)**: Apply a LUT to approximate a specific color tone.

## 4. MSX1 Effect Parameters

## Main Settings
-   **MSX1/MSX2 Color**: Switches between MSX1 (15 colors) and MSX2 (512 colors) palettes.
-   **Dither**: Toggles dithering ON/OFF.
-   **Dark Area Dither**: Selects whether to use a dedicated dither pattern for dark areas.
-   **Convert Algorithm**: Select one of five algorithms for 2-color conversion within an 8x1 dot area.
-   **Color Distance**: Selects the color distance calculation method from RGB or HSB.
-   **HSB Weight**: Adjusts the weighting (Hue, Saturation, Brightness) for color distance calculation in the HSB space.

## Pre-processing
-   **Saturation Boost**: Boosts saturation.
-   **Dark Boost**: Boosts dark areas.
-   **Bright Boost**: Boosts bright areas.
-   **Skin Color Boost**: Adjusts the skin color range.

# Exporting Video

-   **Frame Rate**: Use the "Posterize Time" effect to adjust the frame rate to something like 12 FPS.
-   **Resolution**: Scale up to an integer multiple of `256x192` (3x or 4x is recommended).
-   **Aspect Ratio**: Adjust to fit a 16:9 aspect ratio.
-   **Rendering Settings**: Rendering at "Quality: Draft" and "Resolution: Full" is recommended.
