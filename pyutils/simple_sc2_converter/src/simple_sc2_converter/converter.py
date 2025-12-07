"""Core conversion logic for the simple SC2 converter."""

# Reference: SCREEN 2 (MSX1)
# Usage                 | Address Range  | Notes
# ----------------------|---------------|-------------------------------------------------------
# Pattern generator     | 0000h–17FFh   | 8×8 dots × 768 patterns (3 banks)
# Name table            | 1800h–1AFFh   | 32×24 = 768 bytes; pattern numbers placed on screen
# Sprite attributes     | 1B00h–1B7Fh   | 32 entries; terminates at Y = 216 (0xD8)
# Color table           | 2000h–37FFh   | 8×8 × 768 bytes; color data corresponding to patterns
# Sprite patterns       | 3800h–3FFFh   | 8×8 × 256 bytes

# Reference: SCREEN 4 (Graphic 3, MSX2 and later)
# - Resolution and color count match SCREEN 2 (2bpp with pattern colors).
# - Compatible with SCREEN 2, but table start addresses differ and sprites are Type 2
#   (multi-color sprites).
# Usage                 | Address Range   | Notes
# ----------------------|-----------------|-------------------------------------------------------
# Pattern generator     | 00000h–017FFh   | 8×8 dots × 768 patterns (3 banks)
# Name table            | 01800h–01AFFh   | 32×24 = 768 bytes
# Color palette table   | 01B80h–01B9Fh   | 16 colors × 2 bytes (each R/G/B has 3 bits)
# Sprite colors         | 01C00h–01DFFh   | 256 entries (1 byte each)
# Sprite attributes     | 01E00h–01E7Fh   | 32 entries; terminates at Y = 216 (0xD8)
# Pattern colors        | 02000h–037FFh   | 8×8 × 768 bytes; color data corresponding to patterns
# Sprite patterns       | 03800h–03FFFh   | 8×8 × 256 bytes
# Free space            | 04000h–0FFFFh/1FFFFh | Varies depending on 64KB/128KB VRAM

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from PIL import Image

Color = Tuple[int, int, int]
PaletteOverride = Dict[int, Color]

TARGET_WIDTH = 256
TARGET_HEIGHT = 192
VRAM_SIZE = 0x4000
BASIC_COLORS_MSX1: List[Color] = [
    (0, 0, 0),
    (62, 184, 73),
    (116, 208, 125),
    (89, 85, 224),
    (128, 118, 241),
    (185, 94, 81),
    (101, 219, 239),
    (219, 101, 89),
    (255, 137, 125),
    (204, 195, 94),
    (222, 208, 135),
    (58, 162, 65),
    (183, 102, 181),
    (204, 204, 204),
    (255, 255, 255),
]

BASIC_COLORS_MSX2: List[Color] = [
    (0x00, 0x00, 0x00),
    (0x22, 0xDD, 0x22),
    (0x66, 0xFF, 0x66),
    (0x22, 0x22, 0xFF),
    (0x44, 0x66, 0xFF),
    (0xAA, 0x22, 0x22),
    (0x44, 0xDD, 0xFF),
    (0xFF, 0x22, 0x22),
    (0xFF, 0x66, 0x66),
    (0xDD, 0xDD, 0x22),
    (0xDD, 0xDD, 0x88),
    (0x22, 0x88, 0x22),
    (0xDD, 0x44, 0xAA),
    (0xAA, 0xAA, 0xAA),
    (0xFF, 0xFF, 0xFF),
]


@dataclass
class ConvertOptions:
    """Options for resizing and palette selection."""

    oversize_mode: str = "error"  # error, shrink, crop
    undersize_mode: str = "error"  # error, pad
    background_color: Color = (0, 0, 0)
    use_msx2_palette: bool = False
    palette_overrides: PaletteOverride = field(default_factory=dict)
    include_header: bool = True
    eightdot_mode: str = "BASIC"  # FAST, BASIC, BEST


class ConversionError(Exception):
    """Custom exception for conversion errors."""


def parse_color(text: str) -> Color:
    text = text.strip()
    if text.startswith("#"):
        text = text[1:]
    if "," in text:
        parts = text.split(",")
    else:
        parts = [text[i : i + 2] for i in range(0, len(text), 2)]
    if len(parts) != 3:
        raise ConversionError("Color must have exactly three components")
    values = []
    for part in parts:
        part = part.strip()
        base = 16 if all(c in "0123456789abcdefABCDEF" for c in part) and len(part) <= 2 else 10
        try:
            values.append(int(part, base))
        except ValueError as exc:
            raise ConversionError(f"Invalid color component: {part}") from exc
    if any(not (0 <= v <= 255) for v in values):
        raise ConversionError("Color components must be between 0 and 255")
    return tuple(values)  # type: ignore[return-value]


def build_palette(options: ConvertOptions) -> List[Color]:
    base = BASIC_COLORS_MSX2 if options.use_msx2_palette else BASIC_COLORS_MSX1
    palette = list(base)
    for index, color in options.palette_overrides.items():
        if 1 <= index <= len(palette):
            palette[index - 1] = color
        else:
            raise ConversionError(f"Palette index {index} is out of range")
    return palette


def format_palette_text(palette: Sequence[Color]) -> str:
    entries = [f"{idx+1}: ({r},{g},{b})" for idx, (r, g, b) in enumerate(palette)]
    return ", ".join(entries)


def resize_image(image: Image.Image, options: ConvertOptions) -> Image.Image:
    width, height = image.size
    target = (TARGET_WIDTH, TARGET_HEIGHT)

    if width == TARGET_WIDTH and height == TARGET_HEIGHT:
        return image

    if width > TARGET_WIDTH or height > TARGET_HEIGHT:
        if options.oversize_mode == "error":
            raise ConversionError("Input exceeds 256x192. Use --oversize to allow resizing or cropping.")
        if options.oversize_mode == "shrink":
            ratio = min(TARGET_WIDTH / width, TARGET_HEIGHT / height)
            new_size = (max(1, int(width * ratio)), max(1, int(height * ratio)))
            image = image.resize(new_size, Image.LANCZOS)
            width, height = image.size
        elif options.oversize_mode == "crop":
            left = max(0, (width - TARGET_WIDTH) // 2)
            top = max(0, (height - TARGET_HEIGHT) // 2)
            image = image.crop((left, top, left + TARGET_WIDTH, top + TARGET_HEIGHT))
            width, height = image.size
        else:
            raise ConversionError(f"Unknown oversize mode: {options.oversize_mode}")

    if width < TARGET_WIDTH or height < TARGET_HEIGHT:
        if options.undersize_mode == "error":
            raise ConversionError("Input is smaller than 256x192. Use --undersize pad and set --background.")
        if options.undersize_mode == "pad":
            canvas = Image.new("RGB", target, options.background_color)
            offset = ((TARGET_WIDTH - width) // 2, (TARGET_HEIGHT - height) // 2)
            canvas.paste(image, offset)
            image = canvas
        else:
            raise ConversionError(f"Unknown undersize mode: {options.undersize_mode}")

    if image.size != target:
        raise ConversionError("Image could not be resized to exactly 256x192.")

    return image


def nearest_palette_index(rgb: Color, palette: Sequence[Color]) -> int:
    """
    Return the palette entry closest to ``rgb`` using squared distance.
    Iterates every palette entry and tracks the index with the smallest
    Euclidean distance in RGB space. Squared distances are used to avoid an
    unnecessary square root while preserving ordering.
    """
    r, g, b = rgb
    best_idx = 0
    best_dist = float("inf")
    for i, (pr, pg, pb) in enumerate(palette):
        dist = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if dist < best_dist:
            best_idx = i
            best_dist = dist
    return best_idx


def enforce_two_colors_per_block(
    indices: List[int],
    rgb_values: List[Color],
    palette: Sequence[Color],
    mode: str = "FAST",
) -> List[int]:
    """Limit each 8-pixel block to two palette indices.

    The ``mode`` argument controls how the two palette entries are chosen:
    - ``FAST``  : pick the two most frequent palette indices in the block and
      snap other pixels to whichever of those two colors is closer in RGB
      distance.
    - ``BASIC`` : evaluate all color pairs that already appear in the block and
      choose the pair with the smallest summed RGB distance to the original
      pixels, then remap every pixel to the nearer color from that pair.
    - ``BEST``  : brute-force every pair from the full 15-color palette and use
      the pair that minimizes summed RGB distance for the block, remapping
      pixels to the nearer candidate.
    """

    mode_upper = mode.upper()
    if mode_upper not in {"FAST", "BASIC", "BEST"}:
        raise ConversionError(f"Unknown eightdot mode: {mode}")

    result = indices[:]

    def block_error(pair: Tuple[int, int], start: int) -> float:
        color_a, color_b = pair
        err = 0.0
        for offset, (r, g, b) in enumerate(rgb_values[start : start + 8]):
            idx = indices[start + offset]
            if idx == color_a or idx == color_b:
                continue
            ra, ga, ba = palette[color_a]
            rb, gb, bb = palette[color_b]
            da = (r - ra) ** 2 + (g - ga) ** 2 + (b - ba) ** 2
            db = (r - rb) ** 2 + (g - gb) ** 2 + (b - bb) ** 2
            err += da if da <= db else db
        return err

    for block_start in range(0, TARGET_WIDTH, 8):
        block_indices = indices[block_start : block_start + 8]
        unique_colors = sorted(set(block_indices))
        if len(unique_colors) <= 2:
            continue

        chosen: Tuple[int, int]

        if mode_upper == "FAST":
            counts: Dict[int, int] = {}
            for idx in block_indices:
                counts[idx] = counts.get(idx, 0) + 1
            top_two = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:2]
            chosen = (top_two[0][0], top_two[1][0])
        elif mode_upper == "BASIC":
            best_pair: Tuple[int, int] | None = None
            best_error = float("inf")
            for i, color_a in enumerate(unique_colors):
                for color_b in unique_colors[i + 1 :]:
                    err = block_error((color_a, color_b), block_start)
                    if err < best_error:
                        best_error = err
                        best_pair = (color_a, color_b)
            if best_pair is None:
                continue
            chosen = best_pair
        else:  # BEST
            best_pair: Tuple[int, int] | None = None
            best_error = float("inf")
            for color_a in range(len(palette)):
                for color_b in range(color_a + 1, len(palette)):
                    err = block_error((color_a, color_b), block_start)
                    if err < best_error:
                        best_error = err
                        best_pair = (color_a, color_b)
            if best_pair is None:
                continue
            chosen = best_pair

        allowed = chosen
        ra, ga, ba = palette[allowed[0]]
        rb, gb, bb = palette[allowed[1]]

        for i in range(block_start, block_start + 8):
            r, g, b = rgb_values[i]
            da = (r - ra) ** 2 + (g - ga) ** 2 + (b - ba) ** 2
            db = (r - rb) ** 2 + (g - gb) ** 2 + (b - bb) ** 2
            result[i] = allowed[0] if da <= db else allowed[1]

    return result


def to_vram(
    palette_indices: List[int],
    rgb_values: List[Color],
    palette: Sequence[Color],
    mode: str,
) -> bytes:
    vram = bytearray(VRAM_SIZE)
    pixels_per_line = TARGET_WIDTH

    for ty in range((TARGET_HEIGHT + 7) // 8):
        for tx in range(32):
            ty_mod = ty & 7
            char_index = ty_mod * 32 + tx
            pattern_base = 0x0000 if ty < 8 else (0x0800 if ty < 16 else 0x1000)
            color_base = 0x2000 if ty < 8 else (0x2800 if ty < 16 else 0x3000)
            name_addr = 0x1800 + ty * 32 + tx
            vram[name_addr] = char_index & 0xFF

            for ry in range(8):
                y_base = ty * 8 + ry
                if y_base >= TARGET_HEIGHT:
                    bg_color_code = 1
                    fg_color_code = 1
                    pattern_byte = 0
                else:
                    offset = y_base * pixels_per_line + tx * 8
                    block_indices = palette_indices[offset : offset + 8]
                    block_rgb = rgb_values[offset : offset + 8]
                    block_indices = enforce_two_colors_per_block(
                        block_indices, block_rgb, palette, mode
                    )
                    color_min = min(block_indices)
                    color_max = max(block_indices)
                    bg_color_code = color_min + 1
                    fg_color_code = color_max + 1
                    pattern_byte = 0
                    for idx, color_idx in enumerate(block_indices):
                        pattern_byte <<= 1
                        if color_idx == color_max:
                            pattern_byte |= 0x01

                pattern_addr = pattern_base + char_index * 8 + ry
                color_addr = color_base + char_index * 8 + ry
                vram[pattern_addr] = pattern_byte & 0xFF
                vram[color_addr] = ((fg_color_code & 0x0F) << 4) | (bg_color_code & 0x0F)

    return bytes(vram)


def convert_image_to_sc2(image: Image.Image, options: ConvertOptions | None = None) -> bytes:
    options = options or ConvertOptions()
    palette = build_palette(options)
    image = image.convert("RGB")
    image = resize_image(image, options)

    rgb_values = list(image.getdata())
    palette_indices = [nearest_palette_index(rgb, palette) for rgb in rgb_values]

    vram = to_vram(palette_indices, rgb_values, palette, options.eightdot_mode)

    if not options.include_header:
        return vram

    header = bytes([0xFE, 0x00, 0x00, 0xFF, 0x3F, 0x00, 0x00])
    return header + vram


def _strip_header(sc2_bytes: bytes) -> bytes:
    header = bytes([0xFE, 0x00, 0x00, 0xFF, 0x3F, 0x00, 0x00])
    if len(sc2_bytes) == VRAM_SIZE:
        return sc2_bytes
    if len(sc2_bytes) == VRAM_SIZE + len(header) and sc2_bytes.startswith(header):
        return sc2_bytes[len(header) :]
    raise ConversionError(
        "SC2 data must be 16 KiB or a 7-byte header plus 16 KiB of VRAM data."
    )


def sc2_to_sc4(sc2_bytes: bytes, include_header: bool = True) -> bytes:
    """Convert SC2 VRAM bytes into SC4 VRAM bytes.

    The current converter generates Screen 2 VRAM. Screen 4 uses a compatible
    16 KiB layout for pattern, name, and color tables, so this function mainly
    normalizes the input to raw VRAM and rewrites the optional header for an
    ``.sc4`` payload.

    Warning: SC4 binary layout differs from SC2; this placeholder implementation
    will be corrected in a future update.
    """

    vram = _strip_header(sc2_bytes)

    if len(vram) != VRAM_SIZE:
        raise ConversionError("SC2 VRAM payload must be exactly 16 KiB.")

    if not include_header:
        return bytes(vram)

    header = bytes([0xFE, 0x00, 0x00, 0xFF, 0x3F, 0x00, 0x00])
    return header + bytes(vram)


def convert_image_to_sc4(image: Image.Image, options: ConvertOptions | None = None) -> bytes:
    """Convert an in-memory image to SC4 bytes via SC2 VRAM generation."""

    options = options or ConvertOptions()

    sc2_options = ConvertOptions(
        oversize_mode=options.oversize_mode,
        undersize_mode=options.undersize_mode,
        background_color=options.background_color,
        use_msx2_palette=options.use_msx2_palette,
        palette_overrides=dict(options.palette_overrides),
        include_header=False,
    )

    sc2_vram = convert_image_to_sc2(image, sc2_options)
    return sc2_to_sc4(sc2_vram, include_header=options.include_header)


def convert_png_to_sc2(path: str | Path, options: ConvertOptions | None = None) -> bytes:
    path = Path(path)
    try:
        with Image.open(path) as img:
            return convert_image_to_sc2(img, options)
    except FileNotFoundError as exc:
        raise ConversionError(f"Input file not found: {path}") from exc
    except OSError as exc:
        raise ConversionError(f"Failed to read PNG: {path}") from exc


def convert_png_to_sc4(path: str | Path, options: ConvertOptions | None = None) -> bytes:
    path = Path(path)
    try:
        with Image.open(path) as img:
            return convert_image_to_sc4(img, options)
    except FileNotFoundError as exc:
        raise ConversionError(f"Input file not found: {path}") from exc
    except OSError as exc:
        raise ConversionError(f"Failed to read PNG: {path}") from exc
