#pragma once
#include <cstdint>
#include "MSX1PQCoreTypes.h"

namespace MSX1PQ {
namespace Core {

    // 単一ピクセルを MSX パレットへ量子化
    //
    // x, y:
    //   ディザパターンの参照に使う画素座標
    //
    // in_r, in_g, in_b:
    //   入力 0..255
    //
    // out_r, out_g, out_b:
    //   出力 0..255（MSX1/MSX2 パレット相当色）
    void QuantizePixel(
        const QuantizeConfig& config,
        int x,
        int y,
        std::uint8_t in_r,
        std::uint8_t in_g,
        std::uint8_t in_b,
        std::uint8_t& out_r,
        std::uint8_t& out_g,
        std::uint8_t& out_b);

    // RGBA8 画像全体を量子化
    //
    // data:
    //   RGBA（R, G, B, A の順）の生バッファ
    //
    // width, height:
    //   ピクセル数
    //
    // strideBytes:
    //   1行あたりのバイト数（通常 width * 4）
    //
    // keepAlpha:
    //   true の場合、A はそのまま維持し、RGB だけ量子化
    //   false の場合、A = 255 に固定してもよい
    void ProcessImageRGBA8(
        const QuantizeConfig& config,
        std::uint8_t* data,
        int width,
        int height,
        int strideBytes,
        bool keepAlpha = true);

} // namespace Core
} // namespace MSX1PQ
