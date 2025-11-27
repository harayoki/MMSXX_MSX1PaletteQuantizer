#include "lodepng.h"

#include <cstdio>
#include <cstring>
#include <stdexcept>

#include <png.h>

namespace lodepng {

namespace {

const char* error_message(unsigned code) {
    switch (code) {
    case 0:  return "no error";
    case 1:  return "failed to open file";
    case 2:  return "failed to initialize png reader";
    case 3:  return "failed to read png";
    case 4:  return "failed to initialize png writer";
    case 5:  return "failed to write png";
    default: return "unknown error";
    }
}

}

const char* lodepng_error_text(unsigned code) {
    return error_message(code);
}

unsigned decode(std::vector<unsigned char>& out, unsigned& w, unsigned& h, const std::string& filename) {
    FILE* fp = std::fopen(filename.c_str(), "rb");
    if (!fp) {
        return 1;
    }

    png_structp png_ptr = png_create_read_struct(PNG_LIBPNG_VER_STRING, nullptr, nullptr, nullptr);
    if (!png_ptr) {
        std::fclose(fp);
        return 2;
    }

    png_infop info_ptr = png_create_info_struct(png_ptr);
    if (!info_ptr) {
        png_destroy_read_struct(&png_ptr, nullptr, nullptr);
        std::fclose(fp);
        return 2;
    }

    if (setjmp(png_jmpbuf(png_ptr))) {
        png_destroy_read_struct(&png_ptr, &info_ptr, nullptr);
        std::fclose(fp);
        return 3;
    }

    png_init_io(png_ptr, fp);
    png_read_info(png_ptr, info_ptr);

    png_uint_32 width = 0, height = 0;
    int bit_depth = 0, color_type = 0;
    png_get_IHDR(png_ptr, info_ptr, &width, &height, &bit_depth, &color_type, nullptr, nullptr, nullptr);

    png_set_expand(png_ptr);
    if (bit_depth == 16) {
        png_set_strip_16(png_ptr);
    }
    png_set_gray_to_rgb(png_ptr);
    if (!(color_type & PNG_COLOR_MASK_ALPHA)) {
        png_set_add_alpha(png_ptr, 0xFF, PNG_FILLER_AFTER);
    }
    png_set_palette_to_rgb(png_ptr);

    png_read_update_info(png_ptr, info_ptr);

    w = width;
    h = height;
    out.resize(static_cast<size_t>(w) * static_cast<size_t>(h) * 4);

    std::vector<png_bytep> row_pointers(h);
    for (png_uint_32 y = 0; y < h; ++y) {
        row_pointers[y] = reinterpret_cast<png_bytep>(&out[y * w * 4]);
    }

    png_read_image(png_ptr, row_pointers.data());
    png_read_end(png_ptr, info_ptr);

    png_destroy_read_struct(&png_ptr, &info_ptr, nullptr);
    std::fclose(fp);
    return 0;
}

unsigned encode(const std::string& filename, const std::vector<unsigned char>& image, unsigned w, unsigned h) {
    FILE* fp = std::fopen(filename.c_str(), "wb");
    if (!fp) {
        return 1;
    }

    png_structp png_ptr = png_create_write_struct(PNG_LIBPNG_VER_STRING, nullptr, nullptr, nullptr);
    if (!png_ptr) {
        std::fclose(fp);
        return 4;
    }

    png_infop info_ptr = png_create_info_struct(png_ptr);
    if (!info_ptr) {
        png_destroy_write_struct(&png_ptr, nullptr);
        std::fclose(fp);
        return 4;
    }

    if (setjmp(png_jmpbuf(png_ptr))) {
        png_destroy_write_struct(&png_ptr, &info_ptr);
        std::fclose(fp);
        return 5;
    }

    png_init_io(png_ptr, fp);
    png_set_IHDR(
        png_ptr,
        info_ptr,
        w,
        h,
        8,
        PNG_COLOR_TYPE_RGBA,
        PNG_INTERLACE_NONE,
        PNG_COMPRESSION_TYPE_DEFAULT,
        PNG_FILTER_TYPE_DEFAULT);

    png_write_info(png_ptr, info_ptr);

    std::vector<png_bytep> row_pointers(h);
    for (png_uint_32 y = 0; y < h; ++y) {
        row_pointers[y] = const_cast<png_bytep>(&image[y * w * 4]);
    }

    png_write_image(png_ptr, row_pointers.data());
    png_write_end(png_ptr, nullptr);

    png_destroy_write_struct(&png_ptr, &info_ptr);
    std::fclose(fp);
    return 0;
}

} // namespace lodepng

