#include "MSX1PQPalettes.h"
#include <limits.h>

const MSX1PQ::QuantColor MSX1PQ::kQuantColors[] = {

    // ---- basic_colors_msx1 ----
    {   0,   0,   0 },   //  1: 黒
    {  62, 184,  73 },   //  2: 緑
    { 116, 208, 125 },   //  3: 薄緑
    {  89,  85, 224 },   //  4: 紫
    { 128, 118, 241 },   //  5: 薄紫
    { 185,  94,  81 },   //  6: 赤
    { 101, 219, 239 },   //  7: 水色
    { 219, 101,  89 },   //  8: 赤紫
    { 255, 137, 125 },   //  9: ピンク
    { 204, 195,  94 },   // 10: 黄土色
    { 222, 208, 135 },   // 11: 明るい黄色
    {  58, 162,  65 },   // 12: 深緑
    { 183, 102, 181 },   // 13: 赤紫
    { 204, 204, 204 },   // 14: 灰色
    { 255, 255, 255 },   // 15: 白

    // ---- palette_diz_new ----
    {  44,  42, 112 },   // 16: dith_col2(1, 4)
    {  92,  47,  40 },   // 17: dith_col2(1, 6)
    {  50, 109, 119 },   // 18: dith_col2(1, 7)
    { 102,  97,  47 },   // 19: dith_col2(1,10)
    {  29,  81,  32 },   // 20: dith_col2(1,12)
    {  91,  51,  90 },   // 21: dith_col2(1,13)
    { 102, 102, 102 },   // 22: dith_col2(1,14)
    { 127, 127, 127 },   // 23: dith_col2(1,15)

    {  89, 196,  99 },   // 24: dith_col2(2, 3)
    {  75, 134, 148 },   // 25: dith_col2(2, 4)
    {  95, 151, 157 },   // 26: dith_col2(2, 5)
    { 123, 139,  77 },   // 27: dith_col2(2, 6)
    {  81, 201, 156 },   // 28: dith_col2(2, 7)
    { 140, 142,  81 },   // 29: dith_col2(2, 8)
    { 158, 160,  99 },   // 30: dith_col2(2, 9)
    { 142, 196, 104 },   // 31: dith_col2(2,11)
    { 122, 143, 127 },   // 32: dith_col2(2,13)
    { 133, 194, 138 },   // 33: dith_col2(2,14)
    { 158, 219, 164 },   // 34: dith_col2(2,15)

    { 102, 146, 174 },   // 35: dith_col2(3, 4)
    { 122, 163, 183 },   // 36: dith_col2(3, 5)
    { 150, 151, 103 },   // 37: dith_col2(3, 6)
    { 108, 213, 182 },   // 38: dith_col2(3, 7)
    { 167, 154, 107 },   // 39: dith_col2(3, 8)
    { 185, 172, 125 },   // 40: dith_col2(3, 9)
    { 160, 201, 109 },   // 41: dith_col2(3,10)
    { 149, 155, 153 },   // 42: dith_col2(3,13)
    { 160, 206, 164 },   // 43: dith_col2(3,14)
    { 185, 231, 190 },   // 44: dith_col2(3,15)

    { 108, 101, 232 },   // 45: dith_col2(4, 5)
    { 137,  89, 152 },   // 46: dith_col2(4, 6)
    {  95, 152, 231 },   // 47: dith_col2(4, 7)
    { 154,  93, 156 },   // 48: dith_col2(4, 8)
    { 172, 111, 174 },   // 49: dith_col2(4, 9)
    { 146, 140, 159 },   // 50: dith_col2(4,10)
    { 155, 146, 179 },   // 51: dith_col2(4,11)
    {  73, 123, 144 },   // 52: dith_col2(4,12)
    { 136,  93, 202 },   // 53: dith_col2(4,13)
    { 146, 144, 214 },   // 54: dith_col2(4,14)
    { 172, 170, 239 },   // 55: dith_col2(4,15)

    { 156, 106, 161 },   // 56: dith_col2(5, 6)
    { 114, 168, 240 },   // 57: dith_col2(5, 7)
    { 173, 109, 165 },   // 58: dith_col2(5, 8)
    { 191, 127, 183 },   // 59: dith_col2(5, 9)
    { 166, 156, 167 },   // 60: dith_col2(5,10)
    { 175, 163, 188 },   // 61: dith_col2(5,11)
    {  93, 140, 153 },   // 62: dith_col2(5,12)
    { 155, 110, 211 },   // 63: dith_col2(5,13)
    { 166, 161, 222 },   // 64: dith_col2(5,14)
    { 191, 186, 248 },   // 65: dith_col2(5,15)

    { 143, 156, 160 },   // 66: dith_col2(6, 7)
    { 194, 144,  87 },   // 67: dith_col2(6,10)
    { 203, 151, 108 },   // 68: dith_col2(6,11)
    { 121, 128,  73 },   // 69: dith_col2(6,12)
    { 184,  98, 131 },   // 70: dith_col2(6,13)
    { 194, 149, 142 },   // 71: dith_col2(6,14)

    { 160, 160, 164 },   // 72: dith_col2(7, 8)
    { 229, 225, 174 },   // 73: dith_col2(10,15)
    { 219, 178, 218 },   // 74: dith_col2(13,15)
    { 178, 237, 247 },   // 75: dith_col2(7,15)
    { 255, 196, 190 },   // 76: dith_col2(9,15)
    { 238, 232, 195 },   // 77: dith_col2(11,15)

    { 213, 201, 114 },   // 78: dith_col2(10,11)
    { 185, 232, 190 },   // 79: dith_col2(3,15)
    { 108, 102, 232 },   // 80: dith_col2(4, 5)
    { 114, 169, 240 },   // 81: dith_col2(5, 7)
    { 229, 229, 229 },   // 82: dith_col2(14,15)

    { 211, 148,  91 },   // 83: dith_col2(8,10)
    { 220, 154, 112 },   // 84: dith_col2(8,11)
    { 229, 166, 109 },   // 85: dith_col2(9,10)
    { 238, 172, 130 },   // 86: dith_col2(9,11)
    { 220, 174, 168 },   // 87: dith_col2(6,15)
    { 237, 178, 172 },   // 88: dith_col2(8,15)
    { 238, 231, 195 },   // 89: dith_col2(11,15)

    // ---- palette_low_luminance ----
    {  46,  37,  22 },   // 90: dark_dithering(1, 6)
    {  51,  46,  39 },   // 91: dark_dithering(1,10)
    {  47,  60,  28 },   // 92: dark_dithering(1,12)
    {  49,  40,  82 },   // 93: dark_dithering(1, 4)
    {  46,  56,  60 },   // 94: dark_dithering(1, 7)
    {  61,  34,  61 },   // 95: dark_dithering(1,13)
};

const MSX1PQ::QuantColor MSX1PQ::kBasicColorsMsx2[15] = {
    { 0x00, 0x00, 0x00 }, // 1
    { 0x22, 0xDD, 0x22 }, // 2
    { 0x66, 0xFF, 0x66 }, // 3
    { 0x22, 0x22, 0xFF }, // 4
    { 0x44, 0x66, 0xFF }, // 5
    { 0xAA, 0x22, 0x22 }, // 6
    { 0x44, 0xDD, 0xFF }, // 7
    { 0xFF, 0x22, 0x22 }, // 8
    { 0xFF, 0x66, 0x66 }, // 9
    { 0xDD, 0xDD, 0x22 }, // 10
    { 0xDD, 0xDD, 0x88 }, // 11
    { 0x22, 0x88, 0x22 }, // 12
    { 0xDD, 0x44, 0xAA }, // 13
    { 0xAA, 0xAA, 0xAA }, // 14
    { 0xFF, 0xFF, 0xFF }, // 15
};

const int MSX1PQ::kNumQuantColors = sizeof(MSX1PQ::kQuantColors) / sizeof(MSX1PQ::kQuantColors[0]);
const int MSX1PQ::kNumBasicColors = 15;
const int MSX1PQ::kNumDarkDitherColors  = 6; // palette_low_luminance の個数
const int MSX1PQ::kFirstDarkDitherIndex = MSX1PQ::kNumQuantColors - MSX1PQ::kNumDarkDitherColors;

// ---- ディザパターン生成マクロ ----
#define MAKE_LINE_PATTERN(NAME, COL1_ID, COL2_ID) \
    static const std::uint8_t NAME[] = { \
        (std::uint8_t)((COL1_ID) - 1), \
        (std::uint8_t)((COL2_ID) - 1)  \
    }

#define MAKE_DARK_PATTERN(NAME, COL1_ID, COL2_ID) \
    static const std::uint8_t NAME[] = { \
        (std::uint8_t)((COL1_ID) - 1), (std::uint8_t)((COL1_ID) - 1), \
        (std::uint8_t)((COL1_ID) - 1), (std::uint8_t)((COL2_ID) - 1), \
        (std::uint8_t)((COL1_ID) - 1), (std::uint8_t)((COL1_ID) - 1), \
        (std::uint8_t)((COL2_ID) - 1), (std::uint8_t)((COL1_ID) - 1)  \
    }

// 基本15色の 1x1 パターン (id 1..15 → index 0..14)
static const std::uint8_t kPattern_basic_1[]  = {  0 };
static const std::uint8_t kPattern_basic_2[]  = {  1 };
static const std::uint8_t kPattern_basic_3[]  = {  2 };
static const std::uint8_t kPattern_basic_4[]  = {  3 };
static const std::uint8_t kPattern_basic_5[]  = {  4 };
static const std::uint8_t kPattern_basic_6[]  = {  5 };
static const std::uint8_t kPattern_basic_7[]  = {  6 };
static const std::uint8_t kPattern_basic_8[]  = {  7 };
static const std::uint8_t kPattern_basic_9[]  = {  8 };
static const std::uint8_t kPattern_basic_10[] = {  9 };
static const std::uint8_t kPattern_basic_11[] = { 10 };
static const std::uint8_t kPattern_basic_12[] = { 11 };
static const std::uint8_t kPattern_basic_13[] = { 12 };
static const std::uint8_t kPattern_basic_14[] = { 13 };
static const std::uint8_t kPattern_basic_15[] = { 14 };

// ---- line_dithering 用 (dith_col2 のペア全部) ----
MAKE_LINE_PATTERN(kPattern_1_4,   1,  4);
MAKE_LINE_PATTERN(kPattern_1_6,   1,  6);
MAKE_LINE_PATTERN(kPattern_1_7,   1,  7);
MAKE_LINE_PATTERN(kPattern_1_10,  1, 10);
MAKE_LINE_PATTERN(kPattern_1_12,  1, 12);
MAKE_LINE_PATTERN(kPattern_1_13,  1, 13);
MAKE_LINE_PATTERN(kPattern_1_14,  1, 14);
MAKE_LINE_PATTERN(kPattern_1_15,  1, 15);

MAKE_LINE_PATTERN(kPattern_2_3,   2,  3);
MAKE_LINE_PATTERN(kPattern_2_4,   2,  4);
MAKE_LINE_PATTERN(kPattern_2_5,   2,  5);
MAKE_LINE_PATTERN(kPattern_2_6,   2,  6);
MAKE_LINE_PATTERN(kPattern_2_7,   2,  7);
MAKE_LINE_PATTERN(kPattern_2_8,   2,  8);
MAKE_LINE_PATTERN(kPattern_2_9,   2,  9);
MAKE_LINE_PATTERN(kPattern_2_11,  2, 11);
MAKE_LINE_PATTERN(kPattern_2_13,  2, 13);
MAKE_LINE_PATTERN(kPattern_2_14,  2, 14);
MAKE_LINE_PATTERN(kPattern_2_15,  2, 15);

MAKE_LINE_PATTERN(kPattern_3_4,   3,  4);
MAKE_LINE_PATTERN(kPattern_3_5,   3,  5);
MAKE_LINE_PATTERN(kPattern_3_6,   3,  6);
MAKE_LINE_PATTERN(kPattern_3_7,   3,  7);
MAKE_LINE_PATTERN(kPattern_3_8,   3,  8);
MAKE_LINE_PATTERN(kPattern_3_9,   3,  9);
MAKE_LINE_PATTERN(kPattern_3_10,  3, 10);
MAKE_LINE_PATTERN(kPattern_3_13,  3, 13);
MAKE_LINE_PATTERN(kPattern_3_14,  3, 14);
MAKE_LINE_PATTERN(kPattern_3_15,  3, 15);

MAKE_LINE_PATTERN(kPattern_4_5,   4,  5);
MAKE_LINE_PATTERN(kPattern_4_6,   4,  6);
MAKE_LINE_PATTERN(kPattern_4_7,   4,  7);
MAKE_LINE_PATTERN(kPattern_4_8,   4,  8);
MAKE_LINE_PATTERN(kPattern_4_9,   4,  9);
MAKE_LINE_PATTERN(kPattern_4_10,  4, 10);
MAKE_LINE_PATTERN(kPattern_4_11,  4, 11);
MAKE_LINE_PATTERN(kPattern_4_12,  4, 12);
MAKE_LINE_PATTERN(kPattern_4_13,  4, 13);
MAKE_LINE_PATTERN(kPattern_4_14,  4, 14);
MAKE_LINE_PATTERN(kPattern_4_15,  4, 15);

MAKE_LINE_PATTERN(kPattern_5_6,   5,  6);
MAKE_LINE_PATTERN(kPattern_5_7,   5,  7);
MAKE_LINE_PATTERN(kPattern_5_8,   5,  8);
MAKE_LINE_PATTERN(kPattern_5_9,   5,  9);
MAKE_LINE_PATTERN(kPattern_5_10,  5, 10);
MAKE_LINE_PATTERN(kPattern_5_11,  5, 11);
MAKE_LINE_PATTERN(kPattern_5_12,  5, 12);
MAKE_LINE_PATTERN(kPattern_5_13,  5, 13);
MAKE_LINE_PATTERN(kPattern_5_14,  5, 14);
MAKE_LINE_PATTERN(kPattern_5_15,  5, 15);

MAKE_LINE_PATTERN(kPattern_6_7,   6,  7);
MAKE_LINE_PATTERN(kPattern_6_10,  6, 10);
MAKE_LINE_PATTERN(kPattern_6_11,  6, 11);
MAKE_LINE_PATTERN(kPattern_6_12,  6, 12);
MAKE_LINE_PATTERN(kPattern_6_13,  6, 13);
MAKE_LINE_PATTERN(kPattern_6_14,  6, 14);
MAKE_LINE_PATTERN(kPattern_6_15,  6, 15);

MAKE_LINE_PATTERN(kPattern_7_8,   7,  8);
MAKE_LINE_PATTERN(kPattern_7_15,  7, 15);

MAKE_LINE_PATTERN(kPattern_8_10,  8, 10);
MAKE_LINE_PATTERN(kPattern_8_11,  8, 11);
MAKE_LINE_PATTERN(kPattern_8_15,  8, 15);

MAKE_LINE_PATTERN(kPattern_9_10,  9, 10);
MAKE_LINE_PATTERN(kPattern_9_11,  9, 11);
MAKE_LINE_PATTERN(kPattern_9_15,  9, 15);

MAKE_LINE_PATTERN(kPattern_10_11, 10, 11);
MAKE_LINE_PATTERN(kPattern_10_15, 10, 15);

MAKE_LINE_PATTERN(kPattern_11_15, 11, 15);

MAKE_LINE_PATTERN(kPattern_13_15, 13, 15);
MAKE_LINE_PATTERN(kPattern_14_15, 14, 15);

// ---- dark_dithering 用 (palette_low_luminance) ----
MAKE_DARK_PATTERN(kPattern_dark_1_6,   1,  6);
MAKE_DARK_PATTERN(kPattern_dark_1_10,  1, 10);
MAKE_DARK_PATTERN(kPattern_dark_1_12,  1, 12);
MAKE_DARK_PATTERN(kPattern_dark_1_4,   1,  4);
MAKE_DARK_PATTERN(kPattern_dark_1_7,   1,  7);
MAKE_DARK_PATTERN(kPattern_dark_1_13,  1, 13);

// ---- パレットインデックス → ディザパターン ----
// MSX1PQ::kQuantColors と同じ順番で並べる
const MSX1PQ::DitherPattern MSX1PQ::kPaletteDither[] = {
    // basic 15 (1x1)
    { kPattern_basic_1,  1, 1 }, //  0
    { kPattern_basic_2,  1, 1 }, //  1
    { kPattern_basic_3,  1, 1 }, //  2
    { kPattern_basic_4,  1, 1 }, //  3
    { kPattern_basic_5,  1, 1 }, //  4
    { kPattern_basic_6,  1, 1 }, //  5
    { kPattern_basic_7,  1, 1 }, //  6
    { kPattern_basic_8,  1, 1 }, //  7
    { kPattern_basic_9,  1, 1 }, //  8
    { kPattern_basic_10, 1, 1 }, //  9
    { kPattern_basic_11, 1, 1 }, // 10
    { kPattern_basic_12, 1, 1 }, // 11
    { kPattern_basic_13, 1, 1 }, // 12
    { kPattern_basic_14, 1, 1 }, // 13
    { kPattern_basic_15, 1, 1 }, // 14

    // palette_diz_new (全部 line_dithering: 1x2)
    { kPattern_1_4,   1, 2 }, // 15: (44,42,112)
    { kPattern_1_6,   1, 2 }, // 16
    { kPattern_1_7,   1, 2 }, // 17
    { kPattern_1_10,  1, 2 }, // 18
    { kPattern_1_12,  1, 2 }, // 19
    { kPattern_1_13,  1, 2 }, // 20
    { kPattern_1_14,  1, 2 }, // 21
    { kPattern_1_15,  1, 2 }, // 22

    { kPattern_2_3,   1, 2 }, // 23
    { kPattern_2_4,   1, 2 }, // 24
    { kPattern_2_5,   1, 2 }, // 25
    { kPattern_2_6,   1, 2 }, // 26
    { kPattern_2_7,   1, 2 }, // 27
    { kPattern_2_8,   1, 2 }, // 28
    { kPattern_2_9,   1, 2 }, // 29
    { kPattern_2_11,  1, 2 }, // 30
    { kPattern_2_13,  1, 2 }, // 31
    { kPattern_2_14,  1, 2 }, // 32
    { kPattern_2_15,  1, 2 }, // 33

    { kPattern_3_4,   1, 2 }, // 34
    { kPattern_3_5,   1, 2 }, // 35
    { kPattern_3_6,   1, 2 }, // 36
    { kPattern_3_7,   1, 2 }, // 37
    { kPattern_3_8,   1, 2 }, // 38
    { kPattern_3_9,   1, 2 }, // 39
    { kPattern_3_10,  1, 2 }, // 40
    { kPattern_3_13,  1, 2 }, // 41
    { kPattern_3_14,  1, 2 }, // 42
    { kPattern_3_15,  1, 2 }, // 43

    { kPattern_4_5,   1, 2 }, // 44
    { kPattern_4_6,   1, 2 }, // 45
    { kPattern_4_7,   1, 2 }, // 46
    { kPattern_4_8,   1, 2 }, // 47
    { kPattern_4_9,   1, 2 }, // 48
    { kPattern_4_10,  1, 2 }, // 49
    { kPattern_4_11,  1, 2 }, // 50
    { kPattern_4_12,  1, 2 }, // 51
    { kPattern_4_13,  1, 2 }, // 52
    { kPattern_4_14,  1, 2 }, // 53
    { kPattern_4_15,  1, 2 }, // 54

    { kPattern_5_6,   1, 2 }, // 55
    { kPattern_5_7,   1, 2 }, // 56
    { kPattern_5_8,   1, 2 }, // 57
    { kPattern_5_9,   1, 2 }, // 58
    { kPattern_5_10,  1, 2 }, // 59
    { kPattern_5_11,  1, 2 }, // 60
    { kPattern_5_12,  1, 2 }, // 61
    { kPattern_5_13,  1, 2 }, // 62
    { kPattern_5_14,  1, 2 }, // 63
    { kPattern_5_15,  1, 2 }, // 64

    { kPattern_6_7,   1, 2 }, // 65
    { kPattern_6_10,  1, 2 }, // 66
    { kPattern_6_11,  1, 2 }, // 67
    { kPattern_6_12,  1, 2 }, // 68
    { kPattern_6_13,  1, 2 }, // 69
    { kPattern_6_14,  1, 2 }, // 70

    { kPattern_7_8,   1, 2 }, // 71
    { kPattern_10_15, 1, 2 }, // 72
    { kPattern_13_15, 1, 2 }, // 73
    { kPattern_7_15,  1, 2 }, // 74
    { kPattern_9_15,  1, 2 }, // 75
    { kPattern_11_15, 1, 2 }, // 76

    { kPattern_10_11, 1, 2 }, // 77
    { kPattern_3_15,  1, 2 }, // 78
    { kPattern_4_5,   1, 2 }, // 79 (108,102,232 も 4,5)
    { kPattern_5_7,   1, 2 }, // 80
    { kPattern_14_15, 1, 2 }, // 81

    { kPattern_8_10,  1, 2 }, // 82
    { kPattern_8_11,  1, 2 }, // 83
    { kPattern_9_10,  1, 2 }, // 84
    { kPattern_9_11,  1, 2 }, // 85
    { kPattern_6_15,  1, 2 }, // 86
    { kPattern_8_15,  1, 2 }, // 87
    { kPattern_11_15, 1, 2 }, // 88 (再利用)

    // palette_low_luminance (dark_dithering: 2x4)
    { kPattern_dark_1_6,   2, 4 }, // 89
    { kPattern_dark_1_10,  2, 4 }, // 90
    { kPattern_dark_1_12,  2, 4 }, // 91
    { kPattern_dark_1_4,   2, 4 }, // 92
    { kPattern_dark_1_7,   2, 4 }, // 93
    { kPattern_dark_1_13,  2, 4 }, // 94
};

const int MSX1PQ::kNumPaletteDither =
    sizeof(MSX1PQ::kPaletteDither) / sizeof(MSX1PQ::kPaletteDither[0]);

// ---- MSX1PQ::palette_index_to_basic_index ----
int
MSX1PQ::palette_index_to_basic_index(int palette_idx, std::int32_t xL, std::int32_t yL)
{
    if (palette_idx < 0) {
        palette_idx = 0;
    } else if (palette_idx >= MSX1PQ::kNumQuantColors) {
        palette_idx = MSX1PQ::kNumQuantColors - 1;
    }

    const MSX1PQ::DitherPattern* dp = nullptr;
    if (palette_idx < MSX1PQ::kNumPaletteDither) {
        dp = &MSX1PQ::kPaletteDither[palette_idx];
    }

    if (!dp || !dp->pattern || dp->width == 0 || dp->height == 0) {
        // 未定義時はとりあえず basic 15 に丸める
        if (palette_idx < MSX1PQ::kNumBasicColors) {
            return palette_idx;
        } else {
            return palette_idx % MSX1PQ::kNumBasicColors;
        }
    }

    std::int32_t ix = (xL >= 0) ? xL : -xL;
    std::int32_t iy = (yL >= 0) ? yL : -yL;

    std::int32_t dx = ix % dp->width;
    std::int32_t dy = iy % dp->height;

    std::int32_t idx = dy * dp->width + dx;

    int basic_idx = dp->pattern[idx]; // 0..14
    if (basic_idx < 0) basic_idx = 0;
    if (basic_idx >= MSX1PQ::kNumBasicColors) basic_idx = kNumBasicColors - 1;

    return basic_idx;
}

// ---- ディザ無し用 最近傍 basic15 ----
int
MSX1PQ::nearest_basic_rgb(std::uint8_t r, std::uint8_t g, std::uint8_t b)
{
    int  best_idx  = 0;
    long best_dist = LONG_MAX;

    for (int i = 0; i < MSX1PQ::kNumBasicColors; i++) {
        long dr = (long)r - (long)MSX1PQ::kQuantColors[i].r;
        long dg = (long)g - (long)MSX1PQ::kQuantColors[i].g;
        long db = (long)b - (long)MSX1PQ::kQuantColors[i].b;

        long dist = dr * dr + dg * dg + db * db;
        if (dist < best_dist) {
            best_dist = dist;
            best_idx  = i;
        }
    }
    return best_idx;
}
