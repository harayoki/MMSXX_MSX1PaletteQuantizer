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

from PIL import Image, ImageEnhance

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
    eightdot_mode: str = "BASIC"  # FAST, BASIC, BEST, NONE
    gamma: float | None = None
    contrast: float | None = None
    hue_shift: float | None = None
    posterize_colors: int | None = None
    enable_dither: bool = True
    skip_dither_application: bool = False


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


def apply_preprocessing(image: Image.Image, options: ConvertOptions) -> Image.Image:
    """Apply optional pre-processing before palette quantization."""

    image = image.convert("RGB")

    if options.hue_shift is not None:
        if options.hue_shift < -180 or options.hue_shift > 180:
            raise ConversionError("Hue shift must be between -180 and 180 degrees")
        shift = int(round(options.hue_shift * 255.0 / 360.0))
        h, s, v = image.convert("HSV").split()
        lut = [((value + shift) % 256) for value in range(256)]
        h = h.point(lut)
        image = Image.merge("HSV", (h, s, v)).convert("RGB")

    if options.gamma is not None:
        if options.gamma <= 0:
            raise ConversionError("Gamma must be greater than 0")
        gamma = options.gamma
        lut = [
            max(0, min(255, int(round((value / 255.0) ** gamma * 255))))
            for value in range(256)
        ]
        image = image.point(lut * len(image.getbands()))

    if options.contrast is not None:
        if options.contrast < 0:
            raise ConversionError("Contrast must be zero or greater")
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(options.contrast)

    if options.posterize_colors is not None:
        if options.posterize_colors < 2:
            raise ConversionError("Posterize colors must be at least 2")
        image = image.quantize(colors=options.posterize_colors, method=Image.MEDIANCUT)
        image = image.convert("RGB")

    return image


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


def _squared_distance(a: Color, b: Color) -> int:
    return sum((x - y) ** 2 for x, y in zip(a, b))


SPARSE_DITHER_PATTERN = (
    (True, False),
    (False, False),
    (False, True),
    (False, False),
)

_PERCEIVED_LUMINANCE_WEIGHTS = (0.299, 0.587, 0.114)
DARK_COLOR_LUMINANCE_THRESHOLD = 140.0


def _perceived_luminance(color: Color) -> float:
    r, g, b = color
    wr, wg, wb = _PERCEIVED_LUMINANCE_WEIGHTS
    return r * wr + g * wg + b * wb


# Palette index reference (1-based for users, 0-based in code):
#  0: Black
#  1: Medium Green
#  2: Light Green
#  3: Dark Blue
#  4: Light Blue
#  5: Dark Red
#  6: Cyan
#  7: Medium Red
#  8: Light Red
#  9: Dark Yellow
# 10: Light Yellow
# 11: Dark Green
# 12: Magenta
# 13: Gray
# 14: White

DITHER_PAIR_ALLOWLIST_HALF: List[List[bool]] = [
    # 0: Black — always allowed with every partner
    [
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
    ],
    # 1: Medium Green
    [
        True,  # with Light Green
        True,  # with Dark Blue
        True,  # with Light Blue
        False,  # with Dark Red — complementary clash
        True,  # with Cyan
        False,  # with Medium Red — complementary clash
        False,  # with Light Red — complementary clash
        True,  # with Dark Yellow
        True,  # with Light Yellow
        True,  # with Dark Green
        False,  # with Magenta — complementary clash
        True,  # with Gray
        True,  # with White
    ],
    # 2: Light Green
    [
        True,  # with Dark Blue
        True,  # with Light Blue
        False,  # with Dark Red — complementary clash
        True,  # with Cyan
        False,  # with Medium Red — complementary clash
        False,  # with Light Red — complementary clash
        True,  # with Dark Yellow
        True,  # with Light Yellow
        True,  # with Dark Green
        False,  # with Magenta — complementary clash
        True,  # with Gray
        True,  # with White
    ],
    # 3: Dark Blue
    [
        True,  # with Light Blue
        True,  # with Dark Red
        True,  # with Cyan
        True,  # with Medium Red
        False,  # with Light Red — blue/orange contrast
        False,  # with Dark Yellow — complementary contrast
        False,  # with Light Yellow — complementary contrast
        True,  # with Dark Green
        True,  # with Magenta
        True,  # with Gray
        True,  # with White
    ],
    # 4: Light Blue
    [
        True,  # with Dark Red
        True,  # with Cyan
        False,  # with Medium Red — blue/orange contrast
        False,  # with Light Red — blue/orange contrast
        False,  # with Dark Yellow — complementary contrast
        False,  # with Light Yellow — complementary contrast
        True,  # with Dark Green
        True,  # with Magenta
        True,  # with Gray
        True,  # with White
    ],
    # 5: Dark Red
    [
        False,  # with Cyan — complementary clash
        True,  # with Medium Red
        True,  # with Light Red
        True,  # with Dark Yellow
        True,  # with Light Yellow
        True,  # with Dark Green
        True,  # with Magenta
        True,  # with Gray
        True,  # with White
    ],
    # 6: Cyan
    [
        False,  # with Medium Red — complementary clash
        False,  # with Light Red — complementary clash
        True,  # with Dark Yellow
        True,  # with Light Yellow
        True,  # with Dark Green
        True,  # with Magenta
        True,  # with Gray
        True,  # with White
    ],
    # 7: Medium Red
    [
        True,  # with Light Red
        True,  # with Dark Yellow
        True,  # with Light Yellow
        True,  # with Dark Green
        True,  # with Magenta
        True,  # with Gray
        True,  # with White
    ],
    # 8: Light Red
    [
        True,  # with Dark Yellow
        True,  # with Light Yellow
        True,  # with Dark Green
        True,  # with Magenta
        True,  # with Gray
        True,  # with White
    ],
    # 9: Dark Yellow
    [
        True,  # with Light Yellow
        True,  # with Dark Green
        False,  # with Magenta — complementary contrast
        True,  # with Gray
        True,  # with White
    ],
    # 10: Light Yellow
    [
        True,  # with Dark Green
        False,  # with Magenta — complementary contrast
        True,  # with Gray
        True,  # with White
    ],
    # 11: Dark Green
    [
        False,  # with Magenta — complementary clash
        True,  # with Gray
        True,  # with White
    ],
    # 12: Magenta
    [
        True,  # with Gray
        True,  # with White
    ],
    # 13: Gray
    [
        True,  # with White — always okay with neutral white
    ],
]


def _blend(color_a: Color, color_b: Color, weight_a: float) -> Color:
    weight_b = 1.0 - weight_a
    return (
        int(round(color_a[0] * weight_a + color_b[0] * weight_b)),
        int(round(color_a[1] * weight_a + color_b[1] * weight_b)),
        int(round(color_a[2] * weight_a + color_b[2] * weight_b)),
    )


def build_dither_pair_allowlist(palette: Sequence[Color]) -> List[List[bool]]:
    """Mark palette pairs that are suitable for dithering.

    Strong complementary pairs tend to produce distracting artifacts on MSX1
    artwork. The allowlist keeps black and white paired with everything but
    rejects vivid opposites and other combinations that differ wildly in hue.
    """

    size = len(palette)
    allow = [[True for _ in range(size)] for _ in range(size)]

    for i, row in enumerate(DITHER_PAIR_ALLOWLIST_HALF):
        for offset, allowed in enumerate(row, start=i + 1):
            allow[i][offset] = allowed
            allow[offset][i] = allowed
        allow[i][i] = True

    # Any extra palette entries beyond the base 15 are allowed by default to
    # avoid over-restricting extended palettes.
    for i in range(len(DITHER_PAIR_ALLOWLIST_HALF), size):
        allow[i][i] = True
        for j in range(i + 1, size):
            allow[i][j] = True
            allow[j][i] = True

    return allow


@dataclass
class DitherCandidate:
    tag: str
    primary: int
    secondary: int
    mix_color: Color
    minority_is_primary: bool = False


def _build_dither_candidates(
    palette: Sequence[Color],
    allow_pairs: Sequence[Sequence[bool]],
    enable_dither: bool,
) -> List[DitherCandidate]:
    candidates = [
        DitherCandidate(tag="single", primary=i, secondary=i, mix_color=color)
        for i, color in enumerate(palette)
    ]

    if not enable_dither:
        return candidates

    size = len(palette)
    for a in range(size):
        for b in range(a + 1, size):
            if not allow_pairs[a][b]:
                continue

            color_a = palette[a]
            color_b = palette[b]

            candidates.append(
                DitherCandidate(
                    tag="half_even",
                    primary=a,
                    secondary=b,
                    mix_color=_blend(color_a, color_b, 0.5),
                )
            )
            candidates.append(
                DitherCandidate(
                    tag="half_odd",
                    primary=a,
                    secondary=b,
                    mix_color=_blend(color_a, color_b, 0.5),
                )
            )

            candidates.append(
                DitherCandidate(
                    tag="quarter_primary",
                    primary=a,
                    secondary=b,
                    mix_color=_blend(color_a, color_b, 0.25),
                    minority_is_primary=True,
                )
            )
            candidates.append(
                DitherCandidate(
                    tag="quarter_secondary",
                    primary=a,
                    secondary=b,
                    mix_color=_blend(color_a, color_b, 0.75),
                    minority_is_primary=False,
                )
            )

    # Special 3:1 mixes with black as the minority color against dark palette entries.
    black_index = 0
    if black_index < len(palette):
        black_color = palette[black_index]
        for color_index in range(1, len(palette)):
            if _perceived_luminance(palette[color_index]) > DARK_COLOR_LUMINANCE_THRESHOLD:
                continue
            candidates.append(
                DitherCandidate(
                    tag="black_three_one",
                    primary=color_index,
                    secondary=black_index,
                    mix_color=_blend(palette[color_index], black_color, 0.75),
                    minority_is_primary=False,
                )
            )

    return candidates


def _line_dither_index(
    x: int, y: int, primary: int, secondary: int, secondary_on_even_row: bool
) -> int:
    use_secondary = ((y & 1) == 0) if secondary_on_even_row else ((y & 1) == 1)
    return secondary if use_secondary else primary


def _sparse_dither_index(
    x: int, y: int, primary: int, secondary: int, minority_is_primary: bool
) -> int:
    minority_spot = SPARSE_DITHER_PATTERN[y % len(SPARSE_DITHER_PATTERN)][x % len(SPARSE_DITHER_PATTERN[0])]
    if minority_is_primary:
        return primary if minority_spot else secondary
    return secondary if minority_spot else primary


def map_palette_with_dither(
    rgb_values: List[Color],
    palette: Sequence[Color],
    allow_pairs: Sequence[Sequence[bool]],
    enable_dither: bool,
    skip_dither_application: bool,
) -> List[int]:
    candidates = _build_dither_candidates(palette, allow_pairs, enable_dither)

    candidate_indices: List[int] = []
    for rgb in rgb_values:
        best_idx = 0
        best_error = _squared_distance(rgb, candidates[0].mix_color)
        for idx, candidate in enumerate(candidates[1:], start=1):
            error = _squared_distance(rgb, candidate.mix_color)
            if error < best_error:
                best_error = error
                best_idx = idx
        candidate_indices.append(best_idx)

    result: List[int] = []
    for y in range(TARGET_HEIGHT):
        row_offset = y * TARGET_WIDTH
        for x in range(TARGET_WIDTH):
            candidate = candidates[candidate_indices[row_offset + x]]

            if candidate.tag == "single" or not enable_dither or skip_dither_application:
                if candidate.tag == "single":
                    chosen = candidate.primary
                else:
                    chosen = nearest_palette_index(candidate.mix_color, palette)
            elif candidate.tag == "half_even":
                chosen = _line_dither_index(
                    x, y, candidate.primary, candidate.secondary, True
                )
            elif candidate.tag == "half_odd":
                chosen = _line_dither_index(
                    x, y, candidate.primary, candidate.secondary, False
                )
            elif candidate.tag in {"quarter_primary", "quarter_secondary", "black_three_one"}:
                chosen = _sparse_dither_index(
                    x,
                    y,
                    candidate.primary,
                    candidate.secondary,
                    minority_is_primary=candidate.minority_is_primary,
                )
            else:
                raise ConversionError(f"Unknown dither candidate tag: {candidate.tag}")

            result.append(chosen)

    return result


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
    record_indices: List[int] | None = None,
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

                if record_indices is not None:
                    record_indices.extend(block_indices)

                pattern_addr = pattern_base + char_index * 8 + ry
                color_addr = color_base + char_index * 8 + ry
                vram[pattern_addr] = pattern_byte & 0xFF
                vram[color_addr] = ((fg_color_code & 0x0F) << 4) | (bg_color_code & 0x0F)

    return bytes(vram)


def _prepare_quantized_image(
    image: Image.Image, options: ConvertOptions | None
) -> tuple[ConvertOptions, List[Color], List[int], List[Color]]:
    options = options or ConvertOptions()
    image = apply_preprocessing(image, options)
    palette = build_palette(options)
    image = resize_image(image, options)

    rgb_values = list(image.getdata())
    allow_pairs = build_dither_pair_allowlist(palette)
    palette_indices = map_palette_with_dither(
        rgb_values,
        palette,
        allow_pairs,
        options.enable_dither,
        options.skip_dither_application,
    )

    return options, palette, palette_indices, rgb_values


def convert_image_to_sc2(image: Image.Image, options: ConvertOptions | None = None) -> bytes:
    options, palette, palette_indices, rgb_values = _prepare_quantized_image(
        image, options
    )

    if options.eightdot_mode.upper() == "NONE":
        raise ConversionError(
            "--eightdot NONE disables the 8-pixel two-color limit and cannot produce SC2/SC4 data"
        )

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


def _encode_msx1_palette() -> bytes:
    """Encode the fixed MSX1 palette into MSX2 palette table format.

    The V9938 palette expects two bytes per color entry:

    * Byte 0: ``0BBB0RRR`` (lower 3 bits = red, upper 3 bits = blue)
    * Byte 1: ``0GGG0000`` (lower 3 bits = green)

    MSX1 colors are expressed in 0–255 RGB values. They are quantized to the
    3-bit-per-channel format by scaling into the 0–7 range.
    """

    def to_3bit(component: int) -> int:
        return max(0, min(7, round(component * 7 / 255)))

    palette_bytes = bytearray()
    for r, g, b in BASIC_COLORS_MSX1:
        r3, g3, b3 = to_3bit(r), to_3bit(g), to_3bit(b)
        palette_bytes.append((b3 << 4) | r3)
        palette_bytes.append(g3)
    return bytes(palette_bytes)


def sc2_to_sc4(sc2_bytes: bytes, include_header: bool = True) -> bytes:
    """Convert SC2 VRAM bytes into SC4 VRAM bytes.

    Screen 2 and Screen 4 share the same pattern generator, pattern color, and
    sprite pattern locations, but Screen 4 relocates sprite attributes and
    inserts a dedicated color palette table plus a sprite color table. This
    converter remaps each region according to the layout at the top of this
    module, injects the fixed MSX1 palette into the color palette table, and
    clears unused gaps to keep the VRAM image deterministic.
    """

    vram = _strip_header(sc2_bytes)

    if len(vram) != VRAM_SIZE:
        raise ConversionError("SC2 VRAM payload must be exactly 16 KiB.")

    sc4 = bytearray(VRAM_SIZE)

    # Pattern generator and name table align between SC2 and SC4.
    sc4[0x0000:0x1800] = vram[0x0000:0x1800]
    sc4[0x1800:0x1B00] = vram[0x1800:0x1B00]

    # Insert MSX1 palette in the SC4 color palette table slot.
    sc4[0x1B80:0x1BA0] = _encode_msx1_palette()

    # Sprite attributes shift from 0x1B00 in SC2 to 0x1E00 in SC4. The gap
    # between 0x1B00–0x1B7F and 0x1C00–0x1DFF is left zeroed (sprite colors are
    # not part of SC2 and default to color 0 here).
    sc4[0x1E00:0x1E80] = vram[0x1B00:0x1B80]

    # Pattern colors and sprite patterns are aligned across both modes.
    sc4[0x2000:0x3800] = vram[0x2000:0x3800]
    sc4[0x3800:0x4000] = vram[0x3800:0x4000]

    if not include_header:
        return bytes(sc4)

    header = bytes([0xFE, 0x00, 0x00, 0xFF, 0x3F, 0x00, 0x00])
    return header + bytes(sc4)


def convert_image_to_sc4(image: Image.Image, options: ConvertOptions | None = None) -> bytes:
    """Convert an in-memory image to SC4 bytes via SC2 VRAM generation."""

    options = options or ConvertOptions()

    if options.skip_dither_application:
        raise ConversionError("Debug dither skipping cannot be combined with SC2->SC4 conversion")

    sc2_options = ConvertOptions(
        oversize_mode=options.oversize_mode,
        undersize_mode=options.undersize_mode,
        background_color=options.background_color,
        use_msx2_palette=options.use_msx2_palette,
        palette_overrides=dict(options.palette_overrides),
        include_header=False,
        gamma=options.gamma,
        contrast=options.contrast,
        hue_shift=options.hue_shift,
        posterize_colors=options.posterize_colors,
        enable_dither=options.enable_dither,
        skip_dither_application=False,
    )

    sc2_vram = convert_image_to_sc2(image, sc2_options)
    return sc2_to_sc4(sc2_vram, include_header=options.include_header)


def convert_image_to_msx_png(
    image: Image.Image, options: ConvertOptions | None = None
) -> Image.Image:
    """Convert an in-memory image into a Screen 2-constrained PNG preview."""

    options, palette, palette_indices, rgb_values = _prepare_quantized_image(
        image, options
    )
    def tile_to_raster(record_indices):
        out = [0] * (256 * 192)
        it = iter(record_indices)

        for ty in range(24):
            for tx in range(32):
                for ry in range(8):
                    for rx in range(8):
                        color = next(it)
                        x = tx * 8 + rx
                        y = ty * 8 + ry
                        out[y * 256 + x] = color
        return out

    if options.eightdot_mode.upper() == "NONE":
        final_indices_raster = palette_indices
    else:
        final_indices = []
        to_vram(
            palette_indices,
            rgb_values,
            palette,
            options.eightdot_mode,
            record_indices=final_indices,
        )

        expected_pixels = TARGET_WIDTH * TARGET_HEIGHT
        if len(final_indices) != expected_pixels:
            raise ConversionError(
                "Failed to render the quantized image to Screen 2 dimensions."
            )

        final_indices_raster = tile_to_raster(final_indices)

    preview = Image.new("RGB", (TARGET_WIDTH, TARGET_HEIGHT))
    preview.putdata([palette[idx] for idx in final_indices_raster])
    return preview


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


def convert_png_to_msx_png(
    path: str | Path, options: ConvertOptions | None = None
) -> Image.Image:
    path = Path(path)
    try:
        with Image.open(path) as img:
            return convert_image_to_msx_png(img, options)
    except FileNotFoundError as exc:
        raise ConversionError(f"Input file not found: {path}") from exc
    except OSError as exc:
        raise ConversionError(f"Failed to read PNG: {path}") from exc
