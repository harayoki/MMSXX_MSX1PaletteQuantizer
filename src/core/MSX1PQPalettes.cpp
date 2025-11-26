#include "MSX1PQPalettes.h"
#include <climits>
#include <cstdint>

namespace MSX1PQ {
namespace Core {

const QuantColor kQuantColors[] = {

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
    {  13,  81,  97 },   // 18: dith_col2(1, 7)
    { 100,  50,  37 },   // 19: dith_col2(1, 8)
    { 129,  69,  57 },   // 20: dith_col2(1, 9)
    {  77, 107,  33 },   // 21: dith_col2(1,10)
    {  63,  76,  81 },   // 22: dith_col2(1,13)
    {  91, 100,  99 },   // 23: dith_col2(1,14)
    { 130, 137, 136 },   // 24: dith_col2(1,15)

    {  93, 184, 100 },   // 25: dith_col2(2, 3)
    {  65, 185, 156 },   // 26: dith_col2(2, 7)
    { 112, 187,  97 },   // 27: dith_col2(2,10)
    { 110, 164,  79 },   // 28: dith_col2(2,11)
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
    { 161, 206, 163 },   // 43: dith_col2(3,14)
    { 187, 222, 189 },   // 44: dith_col2(3,15)

    { 108, 101, 232 },   // 45: dith_col2(4, 5)
    { 137,  90, 152 },   // 46: dith_col2(4, 6)
    {  95, 145, 231 },   // 47: dith_col2(4, 7)
    { 149,  93, 146 },   // 48: dith_col2(4, 8)
    { 176, 112, 165 },   // 49: dith_col2(4, 9)
    { 125, 140, 164 },   // 50: dith_col2(4,13)
    { 139, 189, 197 },   // 51: dith_col2(4,14)
    { 171, 209, 213 },   // 52: dith_col2(4,15)

    { 145, 112, 246 },   // 53: dith_col2(5, 7)
    { 183, 111, 161 },   // 54: dith_col2(5, 8)
    { 204, 130, 180 },   // 55: dith_col2(5, 9)
    { 135, 167, 174 },   // 56: dith_col2(5,13)
    { 150, 204, 206 },   // 57: dith_col2(5,14)
    { 187, 214, 221 },   // 58: dith_col2(5,15)

    { 147, 154, 160 },   // 59: dith_col2(6,13)
    { 161, 193, 196 },   // 60: dith_col2(6,14)
    { 189, 211, 214 },   // 61: dith_col2(6,15)

    { 152, 207, 212 },   // 62: dith_col2(7,13)
    { 166, 221, 228 },   // 63: dith_col2(7,14)
    { 193, 237, 244 },   // 64: dith_col2(7,15)

    { 211, 145, 141 },   // 65: dith_col2(8, 9)
    { 185, 175, 109 },   // 66: dith_col2(8,10)
    { 165, 142, 152 },   // 67: dith_col2(8,13)
    { 177, 193, 171 },   // 68: dith_col2(8,14)
    { 204, 209, 195 },   // 69: dith_col2(8,15)

    { 208, 182, 124 },   // 70: dith_col2(9,10)
    { 193, 165, 164 },   // 71: dith_col2(9,13)
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
    { 220, 151, 143 },   // 84: dith_col2(6, 9)
    { 101,  86, 228 },   // 85: dith_col2(4, 5)
    { 144,  96, 147 },   // 86: dith_col2(4, 8)
    { 206, 133, 106 },   // 87: dith_col2(6, 8)
    { 121,  76,  58 },   // 88: dith_col2(1, 6)
    { 145,  98,  76 },   // 89: dith_col2(6, 9)
    { 110,  79,  47 },   // 90: dith_col2(1, 8)
    {  76,  79,  46 },   // 91: dith_col2(1,10)
    { 171, 207, 157 },   // 92: dith_col2(2,15)
    {  98,  74,  72 },   // 93: dith_col2(1, 6)
    {  52,  70,  81 },   // 94: dith_col2(1, 7)
    {  99,  53,  44 },   // 95: dith_col2(1, 6)

    // ---- palette_dark ----
    {  31,  31,  51 },   // 96: dark_dithering(1, 4)
    {  29,  39,  29 },   // 97: dark_dithering(1, 2)
    {  38,  29,  29 },   // 98: dark_dithering(1, 6)
    {  29,  38,  48 },   // 99: dark_dithering(1, 7)
    {  48,  29,  38 },   // 100: dark_dithering(1, 8)
    {  64,  29,  29 },   // 101: dark_dithering(1, 6)
    {  29,  54,  29 },   // 102: dark_dithering(1, 2)
    {  29,  52,  62 },   // 103: dark_dithering(1, 7)
    {  69,  29,  50 },   // 104: dark_dithering(1, 8)
    {  95,  55,  47 },   // 105: dark_dithering(1, 6)
    {  48,  59,  29 },   // 106: dark_dithering(1,10)
    {  29,  53,  29 },   // 107: dark_dithering(1, 2)
    {  61,  34,  61 },   // 108: dark_dithering(1,13)
};

const QuantColor kBasicColorsMsx2[15] = {
    { 0x00, 0x00, 0x00 }, // 1
    { 0x22, 0xDD, 0x22 }, // 2
    { 0x66, 0xFF, 0x66 }, // 3
    { 0x22, 0x22, 0xFF }, // 4
    { 0x44, 0x66, 0xFF }, // 5
    { 0xAA, 0x22, 0x22 }, // 6
    { 0x22, 0xFF, 0xFF }, // 7
    { 0xDD, 0x22, 0x22 }, // 8
    { 0xFF, 0x66, 0x66 }, // 9
    { 0xDD, 0xDD, 0x22 }, // 10
    { 0xFF, 0xFF, 0x66 }, // 11
    { 0x22, 0x88, 0x22 }, // 12
    { 0xDD, 0x22, 0xDD }, // 13
    { 0xAA, 0xAA, 0xAA }, // 14
    { 0xFF, 0xFF, 0xFF }, // 15
};

const int kNumQuantColors = sizeof(kQuantColors) / sizeof(kQuantColors[0]);
const int kNumBasicColors = 15;
const int kNumDarkDitherColors  = 6; // palette_low_luminance の個数
const int kFirstDarkDitherIndex = kNumQuantColors - kNumDarkDitherColors;

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

// 各種ディザパターン
MAKE_LINE_PATTERN(kPattern_1_4,  1,  4);
MAKE_LINE_PATTERN(kPattern_1_6,  1,  6);
MAKE_LINE_PATTERN(kPattern_1_7,  1,  7);
MAKE_LINE_PATTERN(kPattern_1_8,  1,  8);
MAKE_LINE_PATTERN(kPattern_1_9,  1,  9);
MAKE_LINE_PATTERN(kPattern_1_10, 1, 10);
MAKE_LINE_PATTERN(kPattern_1_13, 1, 13);
MAKE_LINE_PATTERN(kPattern_1_14, 1, 14);
MAKE_LINE_PATTERN(kPattern_1_15, 1, 15);

MAKE_LINE_PATTERN(kPattern_2_3,  2,  3);
MAKE_LINE_PATTERN(kPattern_2_7,  2,  7);
MAKE_LINE_PATTERN(kPattern_2_10, 2, 10);
MAKE_LINE_PATTERN(kPattern_2_11, 2, 11);
MAKE_LINE_PATTERN(kPattern_2_8,  2,  8);
MAKE_LINE_PATTERN(kPattern_2_9,  2,  9);
MAKE_LINE_PATTERN(kPattern_2_11b, 2, 11);
MAKE_LINE_PATTERN(kPattern_2_13, 2, 13);
MAKE_LINE_PATTERN(kPattern_2_14, 2, 14);
MAKE_LINE_PATTERN(kPattern_2_15, 2, 15);

MAKE_LINE_PATTERN(kPattern_3_4,  3,  4);
MAKE_LINE_PATTERN(kPattern_3_5,  3,  5);
MAKE_LINE_PATTERN(kPattern_3_6,  3,  6);
MAKE_LINE_PATTERN(kPattern_3_7,  3,  7);
MAKE_LINE_PATTERN(kPattern_3_8,  3,  8);
MAKE_LINE_PATTERN(kPattern_3_9,  3,  9);
MAKE_LINE_PATTERN(kPattern_3_10, 3, 10);
MAKE_LINE_PATTERN(kPattern_3_13, 3, 13);
MAKE_LINE_PATTERN(kPattern_3_14, 3, 14);
MAKE_LINE_PATTERN(kPattern_3_15, 3, 15);

MAKE_LINE_PATTERN(kPattern_4_5,  4,  5);
MAKE_LINE_PATTERN(kPattern_4_6,  4,  6);
MAKE_LINE_PATTERN(kPattern_4_7,  4,  7);
MAKE_LINE_PATTERN(kPattern_4_8,  4,  8);
MAKE_LINE_PATTERN(kPattern_4_9,  4,  9);
MAKE_LINE_PATTERN(kPattern_4_13, 4, 13);
MAKE_LINE_PATTERN(kPattern_4_14, 4, 14);
MAKE_LINE_PATTERN(kPattern_4_15, 4, 15);

MAKE_LINE_PATTERN(kPattern_5_7,  5,  7);
MAKE_LINE_PATTERN(kPattern_5_8,  5,  8);
MAKE_LINE_PATTERN(kPattern_5_9,  5,  9);
MAKE_LINE_PATTERN(kPattern_5_13, 5, 13);
MAKE_LINE_PATTERN(kPattern_5_14, 5, 14);
MAKE_LINE_PATTERN(kPattern_5_15, 5, 15);

MAKE_LINE_PATTERN(kPattern_6_13, 6, 13);
MAKE_LINE_PATTERN(kPattern_6_14, 6, 14);
MAKE_LINE_PATTERN(kPattern_6_15, 6, 15);

MAKE_LINE_PATTERN(kPattern_7_13, 7, 13);
MAKE_LINE_PATTERN(kPattern_7_14, 7, 14);
MAKE_LINE_PATTERN(kPattern_7_15, 7, 15);

MAKE_LINE_PATTERN(kPattern_8_9,  8,  9);
MAKE_LINE_PATTERN(kPattern_8_10, 8, 10);
MAKE_LINE_PATTERN(kPattern_8_13, 8, 13);
MAKE_LINE_PATTERN(kPattern_8_14, 8, 14);
MAKE_LINE_PATTERN(kPattern_8_15, 8, 15);

MAKE_LINE_PATTERN(kPattern_9_10, 9, 10);
MAKE_LINE_PATTERN(kPattern_9_13, 9, 13);
MAKE_LINE_PATTERN(kPattern_7_8,  7,  8);
MAKE_LINE_PATTERN(kPattern_10_15,10,15);
MAKE_LINE_PATTERN(kPattern_13_15,13,15);
MAKE_LINE_PATTERN(kPattern_7_15b, 7,15);
MAKE_LINE_PATTERN(kPattern_9_15, 9, 15);
MAKE_LINE_PATTERN(kPattern_11_15,11,15);

MAKE_LINE_PATTERN(kPattern_10_11,10,11);
MAKE_LINE_PATTERN(kPattern_3_15b, 3,15);
MAKE_LINE_PATTERN(kPattern_4_5b,  4, 5);
MAKE_LINE_PATTERN(kPattern_5_7b,  5, 7);
MAKE_LINE_PATTERN(kPattern_14_15,14,15);

MAKE_LINE_PATTERN(kPattern_8_10b, 8,10);
MAKE_LINE_PATTERN(kPattern_6_9b,  6, 9);
MAKE_LINE_PATTERN(kPattern_4_5c,  4, 5);
MAKE_LINE_PATTERN(kPattern_4_8b,  4, 8);
MAKE_LINE_PATTERN(kPattern_6_8b,  6, 8);
MAKE_LINE_PATTERN(kPattern_1_6b,  1, 6);
MAKE_LINE_PATTERN(kPattern_6_9c,  6, 9);
MAKE_LINE_PATTERN(kPattern_1_8b,  1, 8);
MAKE_LINE_PATTERN(kPattern_1_10b, 1,10);
MAKE_LINE_PATTERN(kPattern_2_15b, 2,15);
MAKE_LINE_PATTERN(kPattern_1_6c,  1, 6);
MAKE_LINE_PATTERN(kPattern_1_7b,  1, 7);
MAKE_LINE_PATTERN(kPattern_1_6d,  1, 6);

// 暗部ディザ
MAKE_DARK_PATTERN(kPattern_dark_1_4,  1,  4);
MAKE_DARK_PATTERN(kPattern_dark_1_2,  1,  2);
MAKE_DARK_PATTERN(kPattern_dark_1_6,  1,  6);
MAKE_DARK_PATTERN(kPattern_dark_1_7,  1,  7);
MAKE_DARK_PATTERN(kPattern_dark_1_8,  1,  8);
MAKE_DARK_PATTERN(kPattern_dark_1_6b, 1,  6);
MAKE_DARK_PATTERN(kPattern_dark_1_2b, 1,  2);
MAKE_DARK_PATTERN(kPattern_dark_1_7b, 1,  7);
MAKE_DARK_PATTERN(kPattern_dark_1_8b, 1,  8);
MAKE_DARK_PATTERN(kPattern_dark_1_6c, 1,  6);
MAKE_DARK_PATTERN(kPattern_dark_1_10,1, 10);
MAKE_DARK_PATTERN(kPattern_dark_1_2c, 1,  2);
MAKE_DARK_PATTERN(kPattern_dark_1_13,1, 13);

// ---- パレットインデックス → ディザパターン ----
// kQuantColors と同じ順番で並べる
const DitherPattern kPaletteDither[] = {
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

    // palette_diz_new
    { kPattern_1_4,   1, 2 }, // 16
    { kPattern_1_6,   1, 2 }, // 17
    { kPattern_1_7,   1, 2 }, // 18
    { kPattern_1_8,   1, 2 }, // 19
    { kPattern_1_9,   1, 2 }, // 20
    { kPattern_1_10,  1, 2 }, // 21
    { kPattern_1_13,  1, 2 }, // 22
    { kPattern_1_14,  1, 2 }, // 23
    { kPattern_1_15,  1, 2 }, // 24

    { kPattern_2_3,   1, 2 }, // 25
    { kPattern_2_7,   1, 2 }, // 26
    { kPattern_2_10,  1, 2 }, // 27
    { kPattern_2_11,  1, 2 }, // 28
    { kPattern_2_8,   1, 2 }, // 29
    { kPattern_2_9,   1, 2 }, // 30
    { kPattern_2_11b, 1, 2 }, // 31
    { kPattern_2_13,  1, 2 }, // 32
    { kPattern_2_14,  1, 2 }, // 33
    { kPattern_2_15,  1, 2 }, // 34

    { kPattern_3_4,   1, 2 }, // 35
    { kPattern_3_5,   1, 2 }, // 36
    { kPattern_3_6,   1, 2 }, // 37
    { kPattern_3_7,   1, 2 }, // 38
    { kPattern_3_8,   1, 2 }, // 39
    { kPattern_3_9,   1, 2 }, // 40
    { kPattern_3_10,  1, 2 }, // 41
    { kPattern_3_13,  1, 2 }, // 42
    { kPattern_3_14,  1, 2 }, // 43
    { kPattern_3_15,  1, 2 }, // 44

    { kPattern_4_5,   1, 2 }, // 45
    { kPattern_4_6,   1, 2 }, // 46
    { kPattern_4_7,   1, 2 }, // 47
    { kPattern_4_8,   1, 2 }, // 48
    { kPattern_4_9,   1, 2 }, // 49
    { kPattern_4_13,  1, 2 }, // 50
    { kPattern_4_14,  1, 2 }, // 51
    { kPattern_4_15,  1, 2 }, // 52

    { kPattern_5_7,   1, 2 }, // 53
    { kPattern_5_8,   1, 2 }, // 54
    { kPattern_5_9,   1, 2 }, // 55
    { kPattern_5_13,  1, 2 }, // 56
    { kPattern_5_14,  1, 2 }, // 57
    { kPattern_5_15,  1, 2 }, // 58

    { kPattern_6_13,  1, 2 }, // 59
    { kPattern_6_14,  1, 2 }, // 60
    { kPattern_6_15,  1, 2 }, // 61

    { kPattern_7_13,  1, 2 }, // 62
    { kPattern_7_14,  1, 2 }, // 63
    { kPattern_7_15,  1, 2 }, // 64

    { kPattern_8_9,   1, 2 }, // 65
    { kPattern_8_10,  1, 2 }, // 66
    { kPattern_8_13,  1, 2 }, // 67
    { kPattern_8_14,  1, 2 }, // 68
    { kPattern_8_15,  1, 2 }, // 69

    { kPattern_9_10,  1, 2 }, // 70
    { kPattern_9_13,  1, 2 }, // 71
    { kPattern_7_8,   1, 2 }, // 72
    { kPattern_10_15, 1, 2 }, // 73
    { kPattern_13_15, 1, 2 }, // 74
    { kPattern_7_15b, 1, 2 }, // 75
    { kPattern_9_15,  1, 2 }, // 76
    { kPattern_11_15, 1, 2 }, // 77

    { kPattern_10_11, 1, 2 }, // 78
    { kPattern_3_15b, 1, 2 }, // 79
    { kPattern_4_5b,  1, 2 }, // 80
    { kPattern_5_7b,  1, 2 }, // 81
    { kPattern_14_15, 1, 2 }, // 82

    { kPattern_8_10b, 1, 2 }, // 83
    { kPattern_6_9b,  1, 2 }, // 84
    { kPattern_4_5c,  1, 2 }, // 85
    { kPattern_4_8b,  1, 2 }, // 86
    { kPattern_6_8b,  1, 2 }, // 87
    { kPattern_1_6b,  1, 2 }, // 88
    { kPattern_6_9c,  1, 2 }, // 89
    { kPattern_1_8b,  1, 2 }, // 90
    { kPattern_1_10b, 1, 2 }, // 91
    { kPattern_2_15b, 1, 2 }, // 92
    { kPattern_1_6c,  1, 2 }, // 93
    { kPattern_1_7b,  1, 2 }, // 94
    { kPattern_1_6d,  1, 2 }, // 95

    // 暗部ディザ (palette_dark)
    { kPattern_dark_1_4,   2, 4 },  // 96
    { kPattern_dark_1_2,   2, 2 },  // 97
    { kPattern_dark_1_6,   2, 6 },  // 98
    { kPattern_dark_1_7,   2, 7 },  // 99
    { kPattern_dark_1_8,   2, 8 },  // 100
    { kPattern_dark_1_6b,  2, 6 },  // 101
    { kPattern_dark_1_2b,  2, 2 },  // 102
    { kPattern_dark_1_7b,  2, 7 },  // 103
    { kPattern_dark_1_8b,  2, 8 },  // 104
    { kPattern_dark_1_6c,  2, 6 },  // 105
    { kPattern_dark_1_10,  2,10 },  // 106
    { kPattern_dark_1_2c,  2, 2 },  // 107
    { kPattern_dark_1_13,  2,13 },  // 108
};

const int kNumPaletteDither = sizeof(kPaletteDither) / sizeof(kPaletteDither[0]);

// ---- パレットインデックス＋座標 → 基本15色インデックス ----
int
palette_index_to_basic_index(int palette_idx, int xL, int yL)
{
    if (palette_idx < 0) {
        palette_idx = 0;
    } else if (palette_idx >= kNumQuantColors) {
        palette_idx = kNumQuantColors - 1;
    }

    const DitherPattern* dp = nullptr;
    if (palette_idx < kNumPaletteDither) {
        dp = &kPaletteDither[palette_idx];
    }

    if (!dp || !dp->pattern || dp->width == 0 || dp->height == 0) {
        // ディザパターンが無ければ、そのパレット色を basic15 に丸めた値を返す
        if (palette_idx < kNumBasicColors) {
            return palette_idx;
        } else {
            return palette_idx % kNumBasicColors;
        }
    }

    int ix = (xL >= 0) ? xL : -xL;
    int iy = (yL >= 0) ? yL : -yL;

    int dx = ix % dp->width;
    int dy = iy % dp->height;

    int idx = dy * dp->width + dx;

    int basic_idx = dp->pattern[idx]; // 0..14
    if (basic_idx < 0) basic_idx = 0;
    if (basic_idx >= kNumBasicColors) basic_idx = kNumBasicColors - 1;

    return basic_idx;
}

// ---- ディザ無し用 最近傍 basic15 ----
int
nearest_basic_rgb(std::uint8_t r, std::uint8_t g, std::uint8_t b)
{
    int  best_idx  = 0;
    long best_dist = LONG_MAX;

    for (int i = 0; i < kNumBasicColors; i++) {
        long dr = (long)r - (long)kQuantColors[i].r;
        long dg = (long)g - (long)kQuantColors[i].g;
        long db = (long)b - (long)kQuantColors[i].b;

        long dist = dr * dr + dg * dg + db * db;
        if (dist < best_dist) {
            best_dist = dist;
            best_idx  = i;
        }
    }
    return best_idx;
}

} // namespace Core
} // namespace MSX1PQ
