#include <algorithm>
#include <cctype>
#include <cstdio>
#include <filesystem>
#include <iostream>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include <png.h>

#include "../core/MSX1PQCore.h"

namespace fs = std::filesystem;

struct PixelRGBA {
    std::uint8_t red{};
    std::uint8_t green{};
    std::uint8_t blue{};
    std::uint8_t alpha{255};
};

struct CliOptions {
    fs::path input_path;
    fs::path output_dir;
    bool force_overwrite{false};

    // AE parameter equivalents
    int color_system{MSX1PQCore::MSX1PQ_COLOR_SYS_MSX1};
    bool use_dither{true};
    bool use_dark_dither{true};
    int eightdot_mode{MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BASIC1};
    int distance_mode{MSX1PQCore::MSX1PQ_DIST_MODE_HSB};
    float weight_h{1.0f};
    float weight_s{0.5f};
    float weight_b{0.75f};
    bool pre_sat{true};
    bool pre_gamma{true};
    bool pre_highlight{true};
    bool pre_skin{false};
};

static void print_usage(const char* exe) {
    std::cout << "Usage: " << exe << " --input <png | dir> --output <dir> [options]\n"
              << "\nRequired:\n"
              << "  -i, --input <path>    PNG file or directory containing PNG images\n"
              << "  -o, --output <dir>    Output directory (created if missing)\n"
              << "\nOptions:\n"
              << "  -f, --force                   Overwrite without confirmation\n"
              << "      --color-system <msx1|msx2>  Palette mode (default: msx1)\n"
              << "      --dither / --no-dither      Enable or disable dithering\n"
              << "      --dark-dither / --no-dark-dither  Use dark dither palettes\n"
              << "      --eightdot <none|fast|basic|best|best-attr|best-trans>\n"
              << "      --distance <rgb|hsb>        Distance metric (default: hsb)\n"
              << "      --weight-h <0-1>            H weight (default: 1.0)\n"
              << "      --weight-s <0-1>            S weight (default: 0.5)\n"
              << "      --weight-b <0-1>            B weight (default: 0.75)\n"
              << "      --pre-sat / --no-pre-sat    Saturation boost\n"
              << "      --pre-gamma / --no-pre-gamma  Gamma adjust\n"
              << "      --pre-highlight / --no-pre-highlight  Highlight adjust\n"
              << "      --pre-skin / --no-pre-skin  Skin tone bias\n"
              << "      --help                      Show this message\n";
}

static bool iequals(const std::string& a, const std::string& b) {
    if (a.size() != b.size()) {
        return false;
    }
    for (size_t i = 0; i < a.size(); ++i) {
        if (std::tolower(static_cast<unsigned char>(a[i])) !=
            std::tolower(static_cast<unsigned char>(b[i]))) {
            return false;
        }
    }
    return true;
}

static std::optional<CliOptions> parse_arguments(int argc, char* argv[]) {
    CliOptions opts;

    auto expect_value = [&](int& i) -> const char* {
        if (i + 1 >= argc) {
            return nullptr;
        }
        return argv[++i];
    };

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-h" || arg == "--help") {
            print_usage(argv[0]);
            return std::nullopt;
        } else if (arg == "-i" || arg == "--input") {
            const char* val = expect_value(i);
            if (!val) {
                std::cerr << "--input requires a value\n";
                return std::nullopt;
            }
            opts.input_path = fs::path(val);
        } else if (arg == "-o" || arg == "--output") {
            const char* val = expect_value(i);
            if (!val) {
                std::cerr << "--output requires a value\n";
                return std::nullopt;
            }
            opts.output_dir = fs::path(val);
        } else if (arg == "-f" || arg == "--force") {
            opts.force_overwrite = true;
        } else if (arg == "--color-system") {
            const char* val = expect_value(i);
            if (!val) {
                std::cerr << "--color-system requires a value\n";
                return std::nullopt;
            }
            if (iequals(val, "msx1")) {
                opts.color_system = MSX1PQCore::MSX1PQ_COLOR_SYS_MSX1;
            } else if (iequals(val, "msx2")) {
                opts.color_system = MSX1PQCore::MSX1PQ_COLOR_SYS_MSX2;
            } else {
                std::cerr << "Unknown color system: " << val << "\n";
                return std::nullopt;
            }
        } else if (arg == "--dither") {
            opts.use_dither = true;
        } else if (arg == "--no-dither") {
            opts.use_dither = false;
        } else if (arg == "--dark-dither") {
            opts.use_dark_dither = true;
        } else if (arg == "--no-dark-dither") {
            opts.use_dark_dither = false;
        } else if (arg == "--eightdot") {
            const char* val = expect_value(i);
            if (!val) {
                std::cerr << "--eightdot requires a value\n";
                return std::nullopt;
            }
            if (iequals(val, "none")) {
                opts.eightdot_mode = MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_NONE;
            } else if (iequals(val, "fast")) {
                opts.eightdot_mode = MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_FAST1;
            } else if (iequals(val, "basic")) {
                opts.eightdot_mode = MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BASIC1;
            } else if (iequals(val, "best")) {
                opts.eightdot_mode = MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BEST1;
            } else if (iequals(val, "best-attr")) {
                opts.eightdot_mode = MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_ATTR_BEST;
            } else if (iequals(val, "best-trans")) {
                opts.eightdot_mode = MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_PENALTY_BEST;
            } else {
                std::cerr << "Unknown eightdot mode: " << val << "\n";
                return std::nullopt;
            }
        } else if (arg == "--distance") {
            const char* val = expect_value(i);
            if (!val) {
                std::cerr << "--distance requires a value\n";
                return std::nullopt;
            }
            if (iequals(val, "rgb")) {
                opts.distance_mode = MSX1PQCore::MSX1PQ_DIST_MODE_RGB;
            } else if (iequals(val, "hsb")) {
                opts.distance_mode = MSX1PQCore::MSX1PQ_DIST_MODE_HSB;
            } else {
                std::cerr << "Unknown distance mode: " << val << "\n";
                return std::nullopt;
            }
        } else if (arg == "--weight-h") {
            const char* val = expect_value(i);
            if (!val) return std::nullopt;
            opts.weight_h = std::stof(val);
        } else if (arg == "--weight-s") {
            const char* val = expect_value(i);
            if (!val) return std::nullopt;
            opts.weight_s = std::stof(val);
        } else if (arg == "--weight-b") {
            const char* val = expect_value(i);
            if (!val) return std::nullopt;
            opts.weight_b = std::stof(val);
        } else if (arg == "--pre-sat") {
            opts.pre_sat = true;
        } else if (arg == "--no-pre-sat") {
            opts.pre_sat = false;
        } else if (arg == "--pre-gamma") {
            opts.pre_gamma = true;
        } else if (arg == "--no-pre-gamma") {
            opts.pre_gamma = false;
        } else if (arg == "--pre-highlight") {
            opts.pre_highlight = true;
        } else if (arg == "--no-pre-highlight") {
            opts.pre_highlight = false;
        } else if (arg == "--pre-skin") {
            opts.pre_skin = true;
        } else if (arg == "--no-pre-skin") {
            opts.pre_skin = false;
        } else {
            std::cerr << "Unknown option: " << arg << "\n";
            return std::nullopt;
        }
    }

    if (opts.input_path.empty() || opts.output_dir.empty()) {
        std::cerr << "Input and output paths are required.\n";
        print_usage(argv[0]);
        return std::nullopt;
    }

    return opts;
}

static bool check_png_extension(const fs::path& p) {
    auto ext = p.extension().string();
    return iequals(ext, ".png");
}

static bool confirm_overwrite(const fs::path& p) {
    std::cout << "Output file " << p << " exists. Overwrite? [y/N]: ";
    std::cout.flush();
    std::string response;
    std::getline(std::cin, response);
    return (!response.empty() && (response[0] == 'y' || response[0] == 'Y'));
}

static bool read_png(const fs::path& path,
                     std::vector<PixelRGBA>& pixels,
                     unsigned& width,
                     unsigned& height,
                     std::string& error) {
    FILE* fp = std::fopen(path.string().c_str(), "rb");
    if (!fp) {
        error = "Failed to open input file";
        return false;
    }

    png_structp png_ptr = png_create_read_struct(PNG_LIBPNG_VER_STRING, nullptr, nullptr, nullptr);
    if (!png_ptr) {
        error = "Failed to create PNG read struct";
        std::fclose(fp);
        return false;
    }

    png_infop info_ptr = png_create_info_struct(png_ptr);
    if (!info_ptr) {
        error = "Failed to create PNG info struct";
        png_destroy_read_struct(&png_ptr, nullptr, nullptr);
        std::fclose(fp);
        return false;
    }

    if (setjmp(png_jmpbuf(png_ptr))) {
        error = "Error while reading PNG";
        png_destroy_read_struct(&png_ptr, &info_ptr, nullptr);
        std::fclose(fp);
        return false;
    }

    png_init_io(png_ptr, fp);
    png_read_info(png_ptr, info_ptr);

    width = png_get_image_width(png_ptr, info_ptr);
    height = png_get_image_height(png_ptr, info_ptr);
    int bit_depth = png_get_bit_depth(png_ptr, info_ptr);
    int color_type = png_get_color_type(png_ptr, info_ptr);

    if (bit_depth == 16) {
        png_set_strip_16(png_ptr);
    }
    if (color_type == PNG_COLOR_TYPE_PALETTE) {
        png_set_palette_to_rgb(png_ptr);
    }
    if (color_type == PNG_COLOR_TYPE_GRAY && bit_depth < 8) {
        png_set_expand_gray_1_2_4_to_8(png_ptr);
    }
    if (png_get_valid(png_ptr, info_ptr, PNG_INFO_tRNS)) {
        png_set_tRNS_to_alpha(png_ptr);
    }
    if (color_type == PNG_COLOR_TYPE_RGB || color_type == PNG_COLOR_TYPE_GRAY || color_type == PNG_COLOR_TYPE_PALETTE) {
        png_set_filler(png_ptr, 0xFF, PNG_FILLER_AFTER);
    }
    if (color_type == PNG_COLOR_TYPE_GRAY || color_type == PNG_COLOR_TYPE_GRAY_ALPHA) {
        png_set_gray_to_rgb(png_ptr);
    }

    png_read_update_info(png_ptr, info_ptr);

    const png_size_t rowbytes = png_get_rowbytes(png_ptr, info_ptr);
    std::vector<png_byte> row_data(rowbytes * height);
    std::vector<png_bytep> row_pointers(height);
    for (size_t y = 0; y < height; ++y) {
        row_pointers[y] = row_data.data() + y * rowbytes;
    }

    png_read_image(png_ptr, row_pointers.data());
    png_read_end(png_ptr, nullptr);

    png_destroy_read_struct(&png_ptr, &info_ptr, nullptr);
    std::fclose(fp);

    pixels.resize(static_cast<size_t>(width) * static_cast<size_t>(height));
    for (size_t y = 0; y < height; ++y) {
        png_bytep row = row_pointers[y];
        for (size_t x = 0; x < width; ++x) {
            size_t idx = (y * width) + x;
            png_bytep px = row + x * 4;
            pixels[idx].red   = px[0];
            pixels[idx].green = px[1];
            pixels[idx].blue  = px[2];
            pixels[idx].alpha = px[3];
        }
    }

    return true;
}

static bool write_png(const fs::path& path,
                      const std::vector<PixelRGBA>& pixels,
                      unsigned width,
                      unsigned height,
                      std::string& error) {
    FILE* fp = std::fopen(path.string().c_str(), "wb");
    if (!fp) {
        error = "Failed to open output file";
        return false;
    }

    png_structp png_ptr = png_create_write_struct(PNG_LIBPNG_VER_STRING, nullptr, nullptr, nullptr);
    if (!png_ptr) {
        error = "Failed to create PNG write struct";
        std::fclose(fp);
        return false;
    }

    png_infop info_ptr = png_create_info_struct(png_ptr);
    if (!info_ptr) {
        error = "Failed to create PNG info struct";
        png_destroy_write_struct(&png_ptr, nullptr);
        std::fclose(fp);
        return false;
    }

    if (setjmp(png_jmpbuf(png_ptr))) {
        error = "Error while writing PNG";
        png_destroy_write_struct(&png_ptr, &info_ptr);
        std::fclose(fp);
        return false;
    }

    png_init_io(png_ptr, fp);

    png_set_IHDR(png_ptr,
                 info_ptr,
                 width,
                 height,
                 8,
                 PNG_COLOR_TYPE_RGBA,
                 PNG_INTERLACE_NONE,
                 PNG_COMPRESSION_TYPE_BASE,
                 PNG_FILTER_TYPE_BASE);

    png_write_info(png_ptr, info_ptr);

    std::vector<png_bytep> row_pointers(height);
    std::vector<unsigned char> row_data(static_cast<size_t>(width) * 4 * height);

    for (size_t y = 0; y < height; ++y) {
        unsigned char* row = row_data.data() + y * width * 4;
        row_pointers[y] = row;
        for (size_t x = 0; x < width; ++x) {
            size_t idx = (y * width) + x;
            row[x * 4 + 0] = pixels[idx].red;
            row[x * 4 + 1] = pixels[idx].green;
            row[x * 4 + 2] = pixels[idx].blue;
            row[x * 4 + 3] = pixels[idx].alpha;
        }
    }

    png_write_image(png_ptr, row_pointers.data());
    png_write_end(png_ptr, nullptr);

    png_destroy_write_struct(&png_ptr, &info_ptr);
    std::fclose(fp);
    return true;
}

static void apply_quantization(std::vector<PixelRGBA>& pixels,
                               unsigned width,
                               unsigned height,
                               const CliOptions& opts) {
    MSX1PQCore::QuantInfo qi{};
    qi.color_system    = opts.color_system;
    qi.use_dither      = opts.use_dither;
    qi.use_dark_dither = opts.use_dark_dither;
    qi.use_8dot2col    = opts.eightdot_mode;
    qi.use_hsb         = (opts.distance_mode == MSX1PQCore::MSX1PQ_DIST_MODE_HSB);
    qi.w_h             = MSX1PQCore::clamp01f(opts.weight_h);
    qi.w_s             = MSX1PQCore::clamp01f(opts.weight_s);
    qi.w_b             = MSX1PQCore::clamp01f(opts.weight_b);
    qi.pre_sat         = opts.pre_sat;
    qi.pre_gamma       = opts.pre_gamma;
    qi.pre_highlight   = opts.pre_highlight;
    qi.pre_skin        = opts.pre_skin;

    for (unsigned y = 0; y < height; ++y) {
        for (unsigned x = 0; x < width; ++x) {
            size_t idx = static_cast<size_t>(y) * width + x;
            auto& px = pixels[idx];

            std::uint8_t r = px.red;
            std::uint8_t g = px.green;
            std::uint8_t b = px.blue;

            MSX1PQCore::apply_preprocess(&qi, r, g, b);

            int basic_idx = 0;
            if (qi.use_dither) {
                int num_colors = MSX1PQ::kNumQuantColors;
                if (!qi.use_dark_dither) {
                    num_colors = MSX1PQ::kFirstDarkDitherIndex;
                }

                int palette_idx = 0;
                if (qi.use_hsb) {
                    palette_idx = MSX1PQCore::nearest_palette_hsb(
                        r, g, b,
                        qi.w_h, qi.w_s, qi.w_b,
                        num_colors);
                } else {
                    palette_idx = MSX1PQCore::nearest_palette_rgb(
                        r, g, b,
                        num_colors);
                }

                basic_idx = MSX1PQ::palette_index_to_basic_index(
                    palette_idx,
                    static_cast<std::int32_t>(x),
                    static_cast<std::int32_t>(y));
            } else {
                if (qi.use_hsb) {
                    basic_idx = MSX1PQCore::nearest_basic_hsb(
                        r, g, b,
                        qi.w_h, qi.w_s, qi.w_b);
                } else {
                    basic_idx = MSX1PQ::nearest_basic_rgb(r, g, b);
                }
            }

            const MSX1PQ::QuantColor& qc =
                (qi.color_system == MSX1PQCore::MSX1PQ_COLOR_SYS_MSX2)
                    ? MSX1PQ::kBasicColorsMsx2[basic_idx]
                    : MSX1PQ::kQuantColors[basic_idx];

            px.red   = qc.r;
            px.green = qc.g;
            px.blue  = qc.b;
        }
    }

    if (qi.use_8dot2col > MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_NONE &&
        qi.use_8dot2col < 7) {
        std::ptrdiff_t pitch = static_cast<std::ptrdiff_t>(width);
        const auto w = static_cast<std::int32_t>(width);
        const auto h = static_cast<std::int32_t>(height);
        const int cs = qi.color_system;
        switch (qi.use_8dot2col) {
        case MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_FAST1:
            MSX1PQCore::apply_8dot2col_fast1(pixels.data(), pitch, w, h, cs);
            break;
        case MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BASIC1:
            MSX1PQCore::apply_8dot2col_basic1(pixels.data(), pitch, w, h, cs);
            break;
        case MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BEST1:
            MSX1PQCore::apply_8dot2col_best1(pixels.data(), pitch, w, h, cs);
            break;
        case MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_ATTR_BEST:
            MSX1PQCore::apply_8dot2col_attr_best(pixels.data(), pitch, w, h, cs);
            break;
        case MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_PENALTY_BEST:
            MSX1PQCore::apply_8dot2col_attr_best_penalty(pixels.data(), pitch, w, h, cs);
            break;
        default:
            break;
        }
    }
}

static std::vector<fs::path> collect_inputs(const fs::path& input) {
    std::vector<fs::path> files;
    if (fs::is_regular_file(input) && check_png_extension(input)) {
        files.push_back(input);
    } else if (fs::is_directory(input)) {
        for (const auto& entry : fs::directory_iterator(input)) {
            if (entry.is_regular_file() && check_png_extension(entry.path())) {
                files.push_back(entry.path());
            }
        }
    }
    return files;
}

int main(int argc, char* argv[]) {
    auto opts_opt = parse_arguments(argc, argv);
    if (!opts_opt.has_value()) {
        return 1;
    }
    CliOptions opts = *opts_opt;

    if (!fs::exists(opts.input_path)) {
        std::cerr << "Input path does not exist." << std::endl;
        return 1;
    }

    std::error_code ec;
    fs::create_directories(opts.output_dir, ec);
    if (ec) {
        std::cerr << "Failed to create output directory: " << ec.message() << std::endl;
        return 1;
    }

    auto inputs = collect_inputs(opts.input_path);
    if (inputs.empty()) {
        std::cerr << "No PNG files to process." << std::endl;
        return 1;
    }

    for (const auto& in_path : inputs) {
        fs::path out_path = opts.output_dir / in_path.filename();
        if (fs::exists(out_path) && !opts.force_overwrite) {
            if (!confirm_overwrite(out_path)) {
                std::cout << "Skipping " << in_path << "\n";
                continue;
            }
        }

        std::vector<PixelRGBA> pixels;
        unsigned width = 0, height = 0;
        std::string error;
        if (!read_png(in_path, pixels, width, height, error)) {
            std::cerr << "Failed to read " << in_path << ": " << error << "\n";
            continue;
        }

        apply_quantization(pixels, width, height, opts);

        if (!write_png(out_path, pixels, width, height, error)) {
            std::cerr << "Failed to write " << out_path << ": " << error << "\n";
            continue;
        }

        std::cout << "Saved: " << out_path << "\n";
    }

    return 0;
}
