#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>

#ifdef __EMSCRIPTEN__
#include <emscripten/emscripten.h>
#define MSX1PQ_API EMSCRIPTEN_KEEPALIVE
#else
#define MSX1PQ_API
#endif

#include "../core/MSX1PQCore.h"
#include "../core/MSX1PQOutput.h"
#include "../core/MSX1PQPalettes.h"
#include "../core/lodepng.h"

extern "C" {

struct Msx1pqOptions {
    int color_system;      // MSX1PQCore::MSX1PQ_COLOR_SYS_*
    int distance_mode;     // MSX1PQCore::MSX1PQ_DIST_MODE_*
    int eightdot_mode;     // MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_*
    int use_dither;        // bool
    int use_palette_color; // bool
    int use_dark_dither;   // bool
    float w_h;
    float w_s;
    float w_v;
    float w_r;
    float w_g;
    float w_b;
};

static MSX1PQCore::QuantInfo to_quant_info(const Msx1pqOptions* opts)
{
    MSX1PQCore::QuantInfo qi;
    if (!opts) {
        qi.use_dither = false;
        qi.use_palette_color = false;
        qi.use_8dot2col = MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_NONE;
        qi.use_hsv = false;
        qi.use_dark_dither = false;
        qi.color_system = MSX1PQCore::MSX1PQ_COLOR_SYS_MSX1;
        qi.w_r = qi.w_g = qi.w_b_rgb = 1.0f;
        qi.w_h = 1.0f;
        qi.w_s = 1.0f;
        qi.w_b = 1.0f;
        return qi;
    }

    qi.use_dither = opts->use_dither != 0;
    qi.use_palette_color = opts->use_palette_color != 0;
    qi.use_8dot2col = opts->eightdot_mode;
    qi.use_dark_dither = opts->use_dark_dither != 0;
    qi.color_system = opts->color_system;

    if (opts->distance_mode == MSX1PQCore::MSX1PQ_DIST_MODE_HSV) {
        qi.use_hsv = true;
        qi.w_h = opts->w_h;
        qi.w_s = opts->w_s;
        qi.w_b = opts->w_v;
    } else {
        qi.use_hsv = false;
        qi.w_r = opts->w_r;
        qi.w_g = opts->w_g;
        qi.w_b_rgb = opts->w_b;
    }

    return qi;
}

MSX1PQ_API void* msx1pq_malloc(std::size_t size)
{
    return std::malloc(size);
}

MSX1PQ_API void msx1pq_free(void* ptr)
{
    std::free(ptr);
}

MSX1PQ_API int msx1pq_quantize_rgba(const std::uint8_t* rgba,
                                    int width,
                                    int height,
                                    const Msx1pqOptions* opts,
                                    std::uint8_t** out_rgba,
                                    int* out_size)
{
    if (!rgba || width <= 0 || height <= 0 || !out_rgba || !out_size) {
        return -1;
    }

    const std::size_t pixel_count = static_cast<std::size_t>(width) * static_cast<std::size_t>(height);
    std::vector<MSX1PQCore::RgbaPixel> pixels(pixel_count);

    for (std::size_t i = 0; i < pixel_count; ++i) {
        const std::uint8_t* src = rgba + (i * 4);
        MSX1PQCore::RgbaPixel px{src[0], src[1], src[2], src[3]};
        pixels[i] = px;
    }

    const MSX1PQCore::QuantInfo qi = to_quant_info(opts);
    MSX1PQCore::quantize_image(pixels, static_cast<unsigned>(width), static_cast<unsigned>(height), qi, true);

    *out_size = static_cast<int>(pixel_count * 4);
    std::uint8_t* buffer = static_cast<std::uint8_t*>(std::malloc(static_cast<std::size_t>(*out_size)));
    if (!buffer) {
        return -2;
    }

    std::memcpy(buffer, pixels.data(), static_cast<std::size_t>(*out_size));
    *out_rgba = buffer;
    return 0;
}

MSX1PQ_API int msx1pq_encode_png(const std::uint8_t* rgba,
                                 int width,
                                 int height,
                                 std::uint8_t** out_png,
                                 int* out_size)
{
    if (!rgba || width <= 0 || height <= 0 || !out_png || !out_size) {
        return -1;
    }

    std::vector<unsigned char> png;
    const unsigned err = lodepng::encode(
        png,
        rgba,
        static_cast<unsigned>(width),
        static_cast<unsigned>(height),
        LCT_RGBA,
        8);

    if (err != 0) {
        return static_cast<int>(err);
    }

    *out_size = static_cast<int>(png.size());
    unsigned char* buffer = static_cast<unsigned char*>(std::malloc(png.size()));
    if (!buffer) {
        return -2;
    }

    std::memcpy(buffer, png.data(), png.size());
    *out_png = buffer;
    return 0;
}

MSX1PQ_API int msx1pq_decode_png(const std::uint8_t* png,
                                 int size,
                                 std::uint8_t** out_rgba,
                                 int* out_width,
                                 int* out_height)
{
    if (!png || size <= 0 || !out_rgba || !out_width || !out_height) {
        return -1;
    }

    std::vector<unsigned char> rgba;
    unsigned w = 0;
    unsigned h = 0;
    const unsigned err = lodepng::decode(
        rgba,
        w,
        h,
        png,
        static_cast<std::size_t>(size),
        LCT_RGBA,
        8);

    if (err != 0) {
        return static_cast<int>(err);
    }

    const std::size_t total = rgba.size();
    unsigned char* buffer = static_cast<unsigned char*>(std::malloc(total));
    if (!buffer) {
        return -2;
    }

    std::memcpy(buffer, rgba.data(), total);
    *out_rgba = buffer;
    *out_width = static_cast<int>(w);
    *out_height = static_cast<int>(h);
    return 0;
}

} // extern "C"
