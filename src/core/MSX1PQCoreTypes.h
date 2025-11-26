#pragma once
#include <cstdint>

namespace MSX1PQ {
namespace Core {

// MSX1 / MSX2
enum class ColorSystem : int {
    MSX1 = 0,
    MSX2 = 1,
};

// 距離モード
enum class DistanceMode : int {
    RGB = 0,
    HSB = 1,
};

// 8dot 2色制限モード
enum class EightDotMode : int {
    None = 0,
    Fast1,
    Basic1,
    Best1,
    AttributeBest,
    PenaltyBest,
};

// RGB 8bit
struct RgbColor {
    std::uint8_t r;
    std::uint8_t g;
    std::uint8_t b;
};

// HSB の重み
struct HsbWeight {
    float h = 1.0f;
    float s = 1.0f;
    float b = 1.0f;
};

// 量子化設定
struct QuantizeConfig {
    bool         useDither     = true;
    bool         useDarkDither = false;
    EightDotMode eightDotMode  = EightDotMode::None;
    DistanceMode distanceMode  = DistanceMode::RGB;
    HsbWeight    hsbWeight     {};
    bool         preSaturation = false;
    bool         preGamma      = false;
    bool         preHighlight  = false;
    bool         preSkin       = false;
    ColorSystem  colorSystem   = ColorSystem::MSX1;
};

} // namespace Core
} // namespace MSX1PQ
