#pragma once

#include <cstdint>
#include <vector>

#include "MSX1PQCore.h"

namespace MSX1PQCore {

struct RgbaPixel {
    std::uint8_t red;
    std::uint8_t green;
    std::uint8_t blue;
    std::uint8_t alpha;
};
static_assert(sizeof(RgbaPixel) == 4, "RgbaPixel must be tightly packed");

void scale_pixels(std::vector<RgbaPixel>& pixels,
                  unsigned& width,
                  unsigned& height,
                  int scale);

unsigned encode_palette_png(const std::vector<RgbaPixel>& pixels,
                            unsigned width,
                            unsigned height,
                            int color_system,
                            std::vector<unsigned char>& out_png);

bool build_sc2_binary(const std::vector<RgbaPixel>& pixels,
                      unsigned width,
                      unsigned height,
                      int color_system,
                      std::vector<std::uint8_t>& out_sc2);

} // namespace MSX1PQCore

