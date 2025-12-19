#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>
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

struct Msx1pqOptionState {
    int color_system{MSX1PQCore::MSX1PQ_COLOR_SYS_MSX1};
    int distance_mode{MSX1PQCore::MSX1PQ_DIST_MODE_RGB};
    int eightdot_mode{MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_NONE};
    bool use_dither{false};
    bool use_palette_color{false};
    bool use_dark_dither{false};
    float w_h{1.0f};
    float w_s{1.0f};
    float w_v{1.0f};
    float w_r{1.0f};
    float w_g{1.0f};
    float w_b{1.0f};
};

struct msx1pq_context {
    Msx1pqOptionState opts{};
    std::vector<MSX1PQCore::RgbaPixel> work_pixels;
    std::vector<std::uint8_t> png_buffer;
    std::vector<std::uint8_t> sc2_buffer;
};

enum Msx1pqOptionKeyI {
    MSX1PQ_OPT_COLOR_SYSTEM   = 1,
    MSX1PQ_OPT_DISTANCE_MODE  = 2,
    MSX1PQ_OPT_EIGHTDOT_MODE  = 3,
    MSX1PQ_OPT_USE_DITHER     = 4,
    MSX1PQ_OPT_USE_PALETTE    = 5,
    MSX1PQ_OPT_USE_DARK_DITH  = 6
};

enum Msx1pqOptionKeyF {
    MSX1PQ_OPT_W_H = 1,
    MSX1PQ_OPT_W_S = 2,
    MSX1PQ_OPT_W_V = 3,
    MSX1PQ_OPT_W_R = 4,
    MSX1PQ_OPT_W_G = 5,
    MSX1PQ_OPT_W_B = 6
};

static MSX1PQCore::QuantInfo to_quant_info(const Msx1pqOptionState& opts)
{
    MSX1PQCore::QuantInfo qi;
    qi.use_dither = opts.use_dither;
    qi.use_palette_color = opts.use_palette_color;
    qi.use_8dot2col = opts.eightdot_mode;
    qi.use_dark_dither = opts.use_dark_dither;
    qi.color_system = opts.color_system;

    if (opts.distance_mode == MSX1PQCore::MSX1PQ_DIST_MODE_HSV) {
        qi.use_hsv = true;
        qi.w_h = opts.w_h;
        qi.w_s = opts.w_s;
        qi.w_b = opts.w_v;
    } else {
        qi.use_hsv = false;
        qi.w_r = opts.w_r;
        qi.w_g = opts.w_g;
        qi.w_b_rgb = opts.w_b;
    }

    return qi;
}

MSX1PQ_API msx1pq_context* msx1pq_create_context()
{
    msx1pq_context* ctx = new (std::nothrow) msx1pq_context();
    return ctx;
}

MSX1PQ_API void msx1pq_destroy_context(msx1pq_context* ctx)
{
    delete ctx;
}

MSX1PQ_API int msx1pq_set_option_i(msx1pq_context* ctx, int key, int value)
{
    if (!ctx) {
        return -1;
    }

    switch (key) {
    case MSX1PQ_OPT_COLOR_SYSTEM:
        ctx->opts.color_system = value;
        return 0;
    case MSX1PQ_OPT_DISTANCE_MODE:
        ctx->opts.distance_mode = value;
        return 0;
    case MSX1PQ_OPT_EIGHTDOT_MODE:
        ctx->opts.eightdot_mode = value;
        return 0;
    case MSX1PQ_OPT_USE_DITHER:
        ctx->opts.use_dither = (value != 0);
        return 0;
    case MSX1PQ_OPT_USE_PALETTE:
        ctx->opts.use_palette_color = (value != 0);
        return 0;
    case MSX1PQ_OPT_USE_DARK_DITH:
        ctx->opts.use_dark_dither = (value != 0);
        return 0;
    default:
        return -2;
    }
}

MSX1PQ_API int msx1pq_set_option_f(msx1pq_context* ctx, int key, float value)
{
    if (!ctx) {
        return -1;
    }

    switch (key) {
    case MSX1PQ_OPT_W_H:
        ctx->opts.w_h = value;
        return 0;
    case MSX1PQ_OPT_W_S:
        ctx->opts.w_s = value;
        return 0;
    case MSX1PQ_OPT_W_V:
        ctx->opts.w_v = value;
        return 0;
    case MSX1PQ_OPT_W_R:
        ctx->opts.w_r = value;
        return 0;
    case MSX1PQ_OPT_W_G:
        ctx->opts.w_g = value;
        return 0;
    case MSX1PQ_OPT_W_B:
        ctx->opts.w_b = value;
        return 0;
    default:
        return -2;
    }
}

MSX1PQ_API void* msx1pq_malloc(std::size_t size)
{
    return std::malloc(size);
}

MSX1PQ_API void msx1pq_free(void* ptr)
{
    std::free(ptr);
}

static int quantize_into_context(msx1pq_context* ctx,
                                 const std::uint8_t* rgba,
                                 int width,
                                 int height,
                                 std::size_t& out_byte_size)
{
    if (!ctx || !rgba || width <= 0 || height <= 0) {
        return -1;
    }

    if (static_cast<std::size_t>(width) >
            (std::numeric_limits<std::size_t>::max() / static_cast<std::size_t>(height))) {
        return -2;
    }

    const std::size_t pixel_count =
        static_cast<std::size_t>(width) * static_cast<std::size_t>(height);
    if (pixel_count > (std::numeric_limits<std::size_t>::max() / sizeof(MSX1PQCore::RgbaPixel))) {
        return -2;
    }

    ctx->work_pixels.resize(pixel_count);

    const std::size_t byte_size = pixel_count * sizeof(MSX1PQCore::RgbaPixel);
    std::memcpy(ctx->work_pixels.data(), rgba, byte_size);

    const MSX1PQCore::QuantInfo qi = to_quant_info(ctx->opts);
    MSX1PQCore::quantize_image(
        ctx->work_pixels,
        static_cast<unsigned>(width),
        static_cast<unsigned>(height),
        qi,
        true);

    out_byte_size = byte_size;
    return 0;
}

MSX1PQ_API int msx1pq_quantize_rgba_into(msx1pq_context* ctx,
                                         const std::uint8_t* rgba,
                                         int width,
                                         int height,
                                         std::uint8_t* out_rgba,
                                         int out_capacity,
                                         int* out_size)
{
    std::size_t byte_size = 0;
    const int qret = quantize_into_context(ctx, rgba, width, height, byte_size);
    if (qret != 0) {
        return qret;
    }

    if (byte_size > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
        return -3;
    }

    if (out_size) {
        *out_size = static_cast<int>(byte_size);
    }

    if (!out_rgba) {
        return 0;
    }

    if (out_capacity < 0 ||
        static_cast<std::size_t>(out_capacity) < byte_size) {
        return -4;
    }

    std::memcpy(out_rgba, ctx->work_pixels.data(), byte_size);
    return 0;
}

MSX1PQ_API int msx1pq_get_last_rgba(const msx1pq_context* ctx,
                                    const std::uint8_t** out_ptr,
                                    int* out_size)
{
    if (!ctx || !out_ptr || !out_size) {
        return -1;
    }

    if (ctx->work_pixels.empty()) {
        *out_ptr = nullptr;
        *out_size = 0;
        return 0;
    }

    *out_ptr = reinterpret_cast<const std::uint8_t*>(ctx->work_pixels.data());
    const std::size_t byte_size = ctx->work_pixels.size() * sizeof(MSX1PQCore::RgbaPixel);
    if (byte_size > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
        return -2;
    }
    *out_size = static_cast<int>(byte_size);
    return 0;
}

MSX1PQ_API int msx1pq_encode_png_from_rgba(msx1pq_context* ctx,
                                           const std::uint8_t* rgba,
                                           int width,
                                           int height,
                                           const std::uint8_t** out_png,
                                           int* out_size)
{
    if (!ctx || !rgba || width <= 0 || height <= 0 || !out_png || !out_size) {
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

    ctx->png_buffer = std::move(png);
    if (ctx->png_buffer.empty()) {
        return -2;
    }

    if (ctx->png_buffer.size() > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
        return -3;
    }

    *out_png = ctx->png_buffer.data();
    *out_size = static_cast<int>(ctx->png_buffer.size());
    return 0;
}

MSX1PQ_API int msx1pq_get_last_png(const msx1pq_context* ctx,
                                   const std::uint8_t** out_png,
                                   int* out_size)
{
    if (!ctx || !out_png || !out_size) {
        return -1;
    }

    if (ctx->png_buffer.empty()) {
        *out_png = nullptr;
        *out_size = 0;
        return 0;
    }

    if (ctx->png_buffer.size() > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
        return -2;
    }

    *out_png = ctx->png_buffer.data();
    *out_size = static_cast<int>(ctx->png_buffer.size());
    return 0;
}

MSX1PQ_API int msx1pq_encode_sc2_from_rgba(msx1pq_context* ctx,
                                           const std::uint8_t* rgba,
                                           int width,
                                           int height,
                                           const std::uint8_t** out_sc2,
                                           int* out_size)
{
    if (!ctx || !rgba || !out_sc2 || !out_size) {
        return -1;
    }

    if (width != 256 || height != 192) {
        return -2;
    }

    std::size_t byte_size = 0;
    const int qret = quantize_into_context(ctx, rgba, width, height, byte_size);
    if (qret != 0) {
        return qret;
    }

    const bool ok = MSX1PQCore::build_sc2_binary(
        ctx->work_pixels,
        static_cast<unsigned>(width),
        static_cast<unsigned>(height),
        ctx->opts.color_system,
        ctx->sc2_buffer);

    if (!ok || ctx->sc2_buffer.empty()) {
        return -3;
    }

    if (ctx->sc2_buffer.size() > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
        return -4;
    }

    *out_sc2 = ctx->sc2_buffer.data();
    *out_size = static_cast<int>(ctx->sc2_buffer.size());
    return 0;
}

MSX1PQ_API int msx1pq_get_last_sc2(const msx1pq_context* ctx,
                                   const std::uint8_t** out_sc2,
                                   int* out_size)
{
    if (!ctx || !out_sc2 || !out_size) {
        return -1;
    }

    if (ctx->sc2_buffer.empty()) {
        *out_sc2 = nullptr;
        *out_size = 0;
        return 0;
    }

    if (ctx->sc2_buffer.size() > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
        return -2;
    }

    *out_sc2 = ctx->sc2_buffer.data();
    *out_size = static_cast<int>(ctx->sc2_buffer.size());
    return 0;
}

} // extern "C"
