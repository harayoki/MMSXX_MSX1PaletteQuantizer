#pragma once

#include <cstdint>

namespace MSX1PQ {
    // MSX1 カラー1つ分
    typedef struct {
        std::uint8_t r;
        std::uint8_t g;
        std::uint8_t b;
    } QuantColor;

    // ディザパターン
    typedef struct {
        const std::uint8_t* pattern; // 長さ = width * height, 値は 0..14 (基本15色インデックス)
        std::uint8_t        width;
        std::uint8_t        height;
    } DitherPattern;

    // パレット配列 (MSX1基本色 + ディザ中間色 + 低輝度パレット)
    extern const QuantColor kQuantColors[];
    extern const int        kNumQuantColors;

    // 基本15色の数
    extern const int        kNumBasicColors;

    // パレットごとのディザ割り当て
    extern const DitherPattern kPaletteDither[];
    extern const int           kNumPaletteDither;

    // パレットインデックス＋座標 → 基本15色インデックス
    int palette_index_to_basic_index(int palette_idx, std::int32_t x, std::int32_t y);

    // ディザなし用：RGB → 基本15色インデックス
    int nearest_basic_rgb(std::uint8_t r, std::uint8_t g, std::uint8_t b);

    // 低輝度ディザパレットの範囲
    extern const int kNumDarkDitherColors;   // 例: 6
    extern const int kFirstDarkDitherIndex;  // 例: MSX1PQ::kNumQuantColors - 6

    extern const QuantColor kBasicColorsMsx2[];

} // namespace MSX1PQ
