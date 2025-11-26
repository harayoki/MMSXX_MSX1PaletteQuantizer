#pragma once
#include <cstdint>

namespace MSX1PQ {
namespace Core {

// パレット1色
struct QuantColor {
    std::uint8_t r;
    std::uint8_t g;
    std::uint8_t b;
};

// ディザパターン
struct DitherPattern {
    const std::uint8_t* pattern; // 長さ = width * height, 値は「基本15色インデックス」
    int width;
    int height;
};

// パレット配列 (MSX1 基本色 + ディザ中間色 + 低輝度パレット)
extern const QuantColor kQuantColors[];
extern const int        kNumQuantColors;

// 基本15色の数
extern const int        kNumBasicColors;

// パレットごとのディザ割り当て
extern const DitherPattern kPaletteDither[];
extern const int           kNumPaletteDither;

// パレットインデックス＋座標 → 基本15色インデックス
int palette_index_to_basic_index(int palette_idx, int x, int y);

// ディザなし用：RGB → 基本15色インデックス
int nearest_basic_rgb(std::uint8_t r, std::uint8_t g, std::uint8_t b);

// 低輝度ディザパレットの範囲
extern const int kNumDarkDitherColors;   // 例: 6
extern const int kFirstDarkDitherIndex;  // 例: kNumQuantColors - 6

// MSX2 用基本色が必要なら
extern const QuantColor kBasicColorsMsx2[];

} // namespace Core
} // namespace MSX1PQ
