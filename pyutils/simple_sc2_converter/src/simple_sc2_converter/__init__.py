"""Simple PNG to SC2 converter.

This module provides a minimal converter that maps PNG images to MSX Screen 2
binary data. It can be invoked through the CLI (``python -m
simple_sc2_converter``) or imported to convert a single PNG file into bytes.
"""

from .converter import (
    BASIC_COLORS_MSX1,
    BASIC_COLORS_MSX2,
    ConvertOptions,
    PaletteOverride,
    convert_image_to_sc2,
    convert_image_to_sc4,
    convert_png_to_sc2,
    convert_png_to_sc4,
    format_palette_text,
)

__all__ = [
    "BASIC_COLORS_MSX1",
    "BASIC_COLORS_MSX2",
    "ConvertOptions",
    "PaletteOverride",
    "convert_image_to_sc2",
    "convert_image_to_sc4",
    "convert_png_to_sc2",
    "convert_png_to_sc4",
    "format_palette_text",
]
