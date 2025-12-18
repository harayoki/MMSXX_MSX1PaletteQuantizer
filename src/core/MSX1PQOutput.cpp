#include "MSX1PQOutput.h"

#include <algorithm>
#include <limits>

#include "../cli/lodepng.h"

namespace MSX1PQCore {

void scale_pixels(std::vector<RgbaPixel>& pixels,
                  unsigned& width,
                  unsigned& height,
                  int scale) {
    if (scale <= 1) {
        return;
    }

    const unsigned new_width  = width * static_cast<unsigned>(scale);
    const unsigned new_height = height * static_cast<unsigned>(scale);
    std::vector<RgbaPixel> scaled(new_width * new_height);

    for (unsigned y = 0; y < new_height; ++y) {
        const unsigned src_y = y / static_cast<unsigned>(scale);
        for (unsigned x = 0; x < new_width; ++x) {
            const unsigned src_x = x / static_cast<unsigned>(scale);
            scaled[y * new_width + x] = pixels[src_y * width + src_x];
        }
    }

    pixels.swap(scaled);
    width  = new_width;
    height = new_height;
}

unsigned encode_palette_png(const std::vector<RgbaPixel>& pixels,
                            unsigned width,
                            unsigned height,
                            int color_system,
                            std::vector<unsigned char>& out_png) {
    const MSX1PQ::QuantColor* palette = get_basic_palette(color_system);

    std::vector<unsigned char> indices(pixels.size());
    for (std::size_t i = 0; i < pixels.size(); ++i) {
        const auto& px = pixels[i];
        if (px.alpha == 0) {
            indices[i] = 0;
            continue;
        }

        std::uint32_t best_distance = std::numeric_limits<std::uint32_t>::max();
        std::uint8_t best_index = 0;
        for (std::size_t pal_idx = 0; pal_idx < MSX1PQ::kNumBasicColors; ++pal_idx) {
            const auto& pal_color = palette[pal_idx];
            const int dr = static_cast<int>(px.red)   - static_cast<int>(pal_color.r);
            const int dg = static_cast<int>(px.green) - static_cast<int>(pal_color.g);
            const int db = static_cast<int>(px.blue)  - static_cast<int>(pal_color.b);
            const std::uint32_t distance = static_cast<std::uint32_t>(dr * dr + dg * dg + db * db);
            if (distance < best_distance) {
                best_distance = distance;
                best_index = static_cast<std::uint8_t>(pal_idx + 1); // palette index 1-15
                if (distance == 0) {
                    break;
                }
            }
        }
        indices[i] = best_index;
    }

    lodepng::State state;
    state.info_raw.colortype = LCT_PALETTE;
    state.info_raw.bitdepth  = 8;
    state.info_png.color.colortype = LCT_PALETTE;
    state.info_png.color.bitdepth  = 8;
    state.encoder.auto_convert     = 0; // Preserve explicit 8-bit palette output

    const auto add_palette_entry = [&](std::uint8_t r, std::uint8_t g, std::uint8_t b, std::uint8_t a) {
        lodepng_palette_add(&state.info_png.color, r, g, b, a);
        lodepng_palette_add(&state.info_raw, r, g, b, a);
    };

    add_palette_entry(0, 0, 0, 0); // index 0: transparent black
    for (std::size_t i = 0; i < MSX1PQ::kNumBasicColors; ++i) {
        const auto& color = palette[i];
        add_palette_entry(color.r, color.g, color.b, 255);
    }

    out_png.clear();
    const unsigned error = lodepng::encode(out_png, indices, width, height, state);
    return error;
}

constexpr int kSc2Width = 256;
constexpr int kSc2Height = 192;

bool build_sc2_binary(const std::vector<RgbaPixel>& pixels,
                      unsigned width,
                      unsigned height,
                      int color_system,
                      std::vector<std::uint8_t>& out_sc2) {
    std::vector<RgbaPixel> canvas(static_cast<size_t>(kSc2Width * kSc2Height));

    RgbaPixel bg{};
    bg.red = 0;
    bg.green = 0;
    bg.blue = 0;
    bg.alpha = 255;

    for (int y = 0; y < kSc2Height; ++y) {
        for (int x = 0; x < kSc2Width; ++x) {
            if (y < static_cast<int>(height) && x < static_cast<int>(width)) {
                canvas[static_cast<size_t>(y * kSc2Width + x)] = pixels[static_cast<size_t>(y * width + x)];
            } else {
                canvas[static_cast<size_t>(y * kSc2Width + x)] = bg;
            }
        }
    }

    std::vector<std::uint8_t> vram(0x4000, 0);

    for (int ty = 0; ty < 24; ++ty) {
        for (int tx = 0; tx < 32; ++tx) {
            const int ty_mod = ty & 7;
            const int char_index = ty_mod * 32 + tx;

            const int pattern_base = (ty < 8) ? 0x0000 : (ty < 16 ? 0x0800 : 0x1000);
            const int color_base = (ty < 8) ? 0x2000 : (ty < 16 ? 0x2800 : 0x3000);

            const std::size_t name_addr = static_cast<std::size_t>(0x1800 + ty * 32 + tx);
            vram[name_addr] = static_cast<std::uint8_t>(char_index);

            for (int ry = 0; ry < 8; ++ry) {
                const int y_base = ty * 8 + ry;

                int color_min = 16;
                int color_max = -1;

                for (int rx = 0; rx < 8; ++rx) {
                    const RgbaPixel& px = canvas[static_cast<std::size_t>(y_base * kSc2Width + (tx * 8 + rx))];
                    const int basic_idx = MSX1PQCore::find_basic_index_from_rgb(px.red, px.green, px.blue, color_system);
                    color_min = std::min(color_min, basic_idx);
                    color_max = std::max(color_max, basic_idx);
                }

                if (color_max < 0) {
                    color_min = 0;
                    color_max = 0;
                }

                const int bg_color = color_min + 1;
                const int fg_color = (color_max >= 0) ? (color_max + 1) : bg_color;

                std::uint8_t pattern_byte = 0;
                for (int rx = 0; rx < 8; ++rx) {
                    const RgbaPixel& px = canvas[static_cast<std::size_t>(y_base * kSc2Width + (tx * 8 + rx))];
                    const int basic_idx = MSX1PQCore::find_basic_index_from_rgb(px.red, px.green, px.blue, color_system);
                    const int color_code = basic_idx + 1;
                    pattern_byte <<= 1;
                    if (color_code == fg_color) {
                        pattern_byte |= 0x01;
                    }
                }

                const std::size_t pattern_addr = static_cast<std::size_t>(pattern_base + char_index * 8 + ry);
                const std::size_t color_addr = static_cast<std::size_t>(color_base + char_index * 8 + ry);

                vram[pattern_addr] = pattern_byte;
                vram[color_addr] = static_cast<std::uint8_t>((fg_color << 4) | (bg_color & 0x0F));
            }
        }
    }

    out_sc2.resize(vram.size() + 7);

    unsigned char header[7];
    header[0] = 0xFE;
    header[1] = 0x00;
    header[2] = 0x00;
    header[3] = 0xFF;
    header[4] = 0x3F;
    header[5] = 0x00;
    header[6] = 0x00;

    std::copy(std::begin(header), std::end(header), out_sc2.begin());
    std::copy(vram.begin(), vram.end(), out_sc2.begin() + 7);

    return true;
}

} // namespace MSX1PQCore

