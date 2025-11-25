#pragma once

#include "AEConfig.h"
#include "AE_Effect.h"

namespace MSX1PQ {
    // MSX1 カラー1つ分
    typedef struct {
        A_u_char r;
        A_u_char g;
        A_u_char b;
    } QuantColor;

    // ディザパターン
    typedef struct {
        const A_u_char* pattern; // 長さ = width * height, 値は 0..14 (基本15色インデックス)
        A_u_char        width;
        A_u_char        height;
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
    int palette_index_to_basic_index(int palette_idx, A_long xL, A_long yL);

    // ディザなし用：RGB → 基本15色インデックス
    int nearest_basic_rgb(A_u_char r, A_u_char g, A_u_char b);

    // 低輝度ディザパレットの範囲
    extern const int kNumDarkDitherColors;   // 例: 6
    extern const int kFirstDarkDitherIndex;  // 例: MSX1PQ::kNumQuantColors - 6

    extern const QuantColor kBasicColorsMsx2[];

} // namespace MSX1PQ
