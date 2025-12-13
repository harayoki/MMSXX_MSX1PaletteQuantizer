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

![panel.png](panel.png)

## Main Settings
-   **MSX1/MSX2 Color**: Switches between the MSX1 palette (15 colors) and the MSX2 palette (15 colors tuned for the MSX2 look).
-   **Dither**: Toggles dithering ON/OFF.
-   **Dark Area Dither**: Selects whether to use a dedicated dither pattern for dark areas.
-   **Convert Algorithm**: Select one of five algorithms for 2-color conversion within an 8x1 dot area.
    - **None**: Does nothing.
    - **Fast**: Uses the two most frequently occurring colors, operates quickly.
    - **Basic**: Selects two colors based on color distance from the appearing colors.
    - **Best**: Re-selects the two most optimal colors from the 15-palette that represent the colors appearing within 8 pixels. (Recommended)
    - **Best-Atttr**: In addition to "Best", considers the colors of the surrounding upper and lower pixels to select two colors.
    - **Best-Tran**: In addition to "Best Attribute", considers the colors of the left and right frames to select two colors.
-   **Color Distance**: Selects the color distance calculation method from RGB or HSV.
-   **HSV Weight**: Adjusts the weighting (Hue, Saturation, Value) for color distance calculation in the HSV space.

## Pre-processing
-   **Posterization**: Reduces the total number of colors before conversion (0–255, default 16; disabled when `<=1`). Helpful for suppressing noise, flattening areas, or steering dithering patterns.
-   **Saturation Boost**: Adjusts saturation with a slider (0 to 10, default 1).
-   **Gamma (Darker)**: Darkens midtones with a slider (0 to 10, default 1).
-   **Highlight Adjust**: Boosts bright areas with a slider (0 to 10, default 1).
-   **Hue Rotate**: Rotates hue from -180 to 180 degrees (integer values).

## Others

-   **92 Color**: (For development) Outputs using the 92-color palette.

