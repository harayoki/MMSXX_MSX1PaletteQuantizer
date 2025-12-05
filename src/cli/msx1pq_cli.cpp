#include <algorithm>
#include <array>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <sstream>
#include <vector>

#include "../core/MSX1PQCore.h"
#include "../core/MSX1PQPalettes.h"
#include "lodepng.h"

namespace fs = std::filesystem;

struct CliOptions {
    fs::path input_path;
    fs::path output_dir;
    std::string output_prefix;
    std::string output_suffix;
    bool force{false};

    int color_system{MSX1PQCore::MSX1PQ_COLOR_SYS_MSX1};
    bool out_sc5{false};
    bool out_sc2{false};
    bool use_dither{true};
    bool use_palette_color{false};
    bool use_dark_dither{true};
    bool use_preprocess{true};
    int use_8dot2col{MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BEST1};
    bool use_hsb{true};
    float weight_h{1.0f};
    float weight_s{0.5f};
    float weight_b{0.75f};
    int pre_posterize{16};
    float pre_sat{1.0f};
    float pre_gamma{1.0f};
    float pre_highlight{1.0f};
    float pre_hue{0.0f};
    float pre_sharpness{0.0f};
    fs::path pre_lut_path;
    std::vector<std::uint8_t> pre_lut_data;
    std::vector<float> pre_lut3d_data;
    int pre_lut3d_size{0};
};

struct RgbaPixel {
    std::uint8_t red;
    std::uint8_t green;
    std::uint8_t blue;
    std::uint8_t alpha;
};
static_assert(sizeof(RgbaPixel) == 4, "RgbaPixel must be tightly packed");

namespace {

std::string to_lower_copy(const std::string& s);

enum class UsageLanguage {
    English,
    Japanese,
};

constexpr const char* kVersion = "v0.7b";

std::optional<std::string> get_env_value(const char* name) {
#ifdef _MSC_VER
    char* buffer = nullptr;
    size_t size = 0;
    if (_dupenv_s(&buffer, &size, name) == 0 && buffer != nullptr) {
        std::string value(buffer);
        std::free(buffer);
        return value;
    }
    return std::nullopt;
#else
    if (const char* value = std::getenv(name)) {
        return std::string(value);
    }
    return std::nullopt;
#endif
}

UsageLanguage detect_usage_language_from_env() {
    const char* locale_vars[] = {"LC_ALL", "LC_MESSAGES", "LANG"};
    for (const char* var : locale_vars) {
        if (auto value = get_env_value(var)) {
            std::string locale = to_lower_copy(*value);
            if (locale.find("ja") != std::string::npos) {
                return UsageLanguage::Japanese;
            }
        }
    }
    return UsageLanguage::English;
}

void print_usage(const char* prog, UsageLanguage lang = UsageLanguage::Japanese) {
    if (lang == UsageLanguage::Japanese) {
        std::cout << "MMSXX - MSX1 Palette Quantizer\n"
                  << "使い方: " << prog << " --input <ファイル|ディレクトリ> --output <ディレクトリ> [オプション]\n"
                  << "1つの画像またはフォルダ内の複数の画像を受け取り、MSX1(TMS9918)の表示ルールに則った画像に変換します。\n"
                  << "オプション:\n"
                  << "  --input, -i <ファイル|ディレクトリ>  入力PNGファイルまたはディレクトリを指定\n"
                  << "  --output, -o <ディレクトリ>       出力先ディレクトリを指定\n"
                  << "  --out-prefix <文字列>          出力ファイル名の先頭に付与する接頭辞を指定\n"
                  << "  --out-suffix <文字列>          出力ファイル名の末尾（拡張子の前）に付与する接尾辞を指定\n"
                  << "  --out-sc5                   PNGではなくSCREEN5 .sc5バイナリで出力\n"
                  << "  --out-sc2                   SCREEN2 .sc2バイナリで出力\n"
                  << "  --color-system <msx1|msx2>   (デフォルト: msx1)\n"
                  << "  --dither / --no-dither       (デフォルト: dither)\n"
                  << "  --dark-dither / --no-dark-dither (デフォルト: ダークディザーパレットを使用)\n"
                  << "  --no-preprocess             前処理をスキップ\n"
                  << "  --8dot <none|fast|basic|best|best-attr|best-trans> (デフォルト: best)\n"
                  << "  --distance <rgb|hsb>         (デフォルト: hsb)\n"
                  << "  --weight-h <0-1> --weight-s <0-1> --weight-b <0-1>\n"
                  << "  --pre-posterize <0-255>      前処理でポスタリゼーションを適用 (デフォルト: 16 1以下は処理なし)\n"
                  << "  --pre-sat <0-10>             処理前に彩度を高く補正 (デフォルト: 1.0)\n"
                  << "  --pre-gamma <0-10>           処理前にガンマを暗く補正 (デフォルト: 1.0)\n"
                  << "  --pre-highlight <0-10>       処理前にハイライトを明るく補正 (デフォルト: 1.0)\n"
                  << "  --pre-hue <-180-180>         処理前に色相を変更 (デフォルト: 0.0)\n"
                  << "  --pre-sharpness <0-1>        処理前にシャープネスを適用 (デフォルト: 0.0)\n"
                  << "  --pre-lut <ファイル>           処理前にRGB LUT(256行のRGB値)や.cube 3D LUTを適用\n"
                  << "  --palette92                  (開発用) ディザ処理を行わず92色パレットで出力\n"
                  << "  -f, --force                  上書き時に確認しない\n"
                  << "  -v, --version                バージョン情報を表示\n"
                  << "  -h, --help                   ロケールに応じてUSAGEを表示\n"
                  << "  --help-ja                    この日本語のUSAGEを表示\n"
                  << "  --help-en                    Show this usage in English\n";
        return;
    }

    std::cout << "MMSXX - MSX1 Palette Quantizer\n"
              << "Usage: " << prog << " --input <file|dir> --output <dir> [options]\n"
              << "Convert a single image or multiple images in a folder into images that comply with MSX1 (TMS9918) display rules.\n"
                  << "Options:\n"
                  << "  --input, -i <file|dir>       Specify the input PNG file or directory\n"
                  << "  --output, -o <dir>           Specify the output directory\n"
                  << "  --out-prefix <string>       Prefix to add to output file names\n"
                  << "  --out-suffix <string>       Suffix to add before the output file extension\n"
                  << "  --out-sc5                   Output SCREEN5 .sc5 binary instead of PNG\n"
                  << "  --out-sc2                   Output SCREEN2 .sc2 binary\n"
              << "  --color-system <msx1|msx2>   (default: msx1)\n"
              << "  --dither / --no-dither       (default: dither)\n"
              << "  --palette92                  (for dev) Output 92 color palette without dithering\n"
              << "  --dark-dither / --no-dark-dither (default: use dark dither palettes)\n"
              << "  --no-preprocess             Skip preprocessing adjustments\n"
              << "  --8dot <none|fast|basic|best|best-attr|best-trans> (default: best)\n"
              << "  --distance <rgb|hsb>         (default: hsb)\n"
              << "  --weight-h <0-1> --weight-s <0-1> --weight-b <0-1>\n"
              << "  --pre-posterize <0-255>      Apply posterization before processing (default: 16,  skipped if <= 1)\n"
              << "  --pre-sat <0-10>             Increase saturation before processing (default: 1.0)\n"
              << "  --pre-gamma <0-10>           Darken gamma before processing (default: 1.0)\n"
              << "  --pre-highlight <0-10>       Brighten highlights before processing (default: 1.0)\n"
              << "  --pre-hue <-180-180>         Adjust hue before processing (default: 0.0)\n"
              << "  --pre-sharpness <0-1>        Apply sharpening before processing (default: 0.0)\n"
              << "  --pre-lut <file>             Apply RGB LUT (256 rows) or .cube 3D LUT before processing\n"
              << "  -f, --force                  Overwrite without confirmation\n"
              << "  -v, --version                Show version information\n"
              << "  -h, --help                   Show usage based on locale (Japanese if detected)\n"
              << "  --help-ja                    この日本語のUSAGEを表示\n"
              << "  --help-en                    Show this usage in English\n";
}

void print_version(const char* prog) {
    std::cout << prog << " version " << kVersion << "\n";
}

std::optional<int> parse_8dot_mode(const std::string& value) {
    static const std::map<std::string, int> kMap = {
        {"none", MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_NONE},
        {"fast", MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_FAST1},
        {"basic", MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BASIC1},
        {"best", MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BEST1},
        {"best-attr", MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_ATTR_BEST},
        {"best-trans", MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_PENALTY_BEST},
    };

    auto it = kMap.find(value);
    if (it != kMap.end()) {
        return it->second;
    }
    return std::nullopt;
}

bool parse_arguments(int argc, char** argv, CliOptions& opts) {
    if (argc < 2) {
        print_usage(argv[0], detect_usage_language_from_env());
        return false;
    }

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto require_value = [&](const std::string& name) -> std::string {
            if (i + 1 >= argc) {
                throw std::runtime_error("Missing value for option: " + name);
            }
            return argv[++i];
        };

        if (arg == "--input" || arg == "-i") {
            opts.input_path = require_value(arg);
        } else if (arg == "--output" || arg == "-o") {
            opts.output_dir = require_value(arg);
        } else if (arg == "--out-prefix") {
            opts.output_prefix = require_value(arg);
        } else if (arg == "--out-suffix") {
            opts.output_suffix = require_value(arg);
        } else if (arg == "--out-sc5") {
            opts.out_sc5 = true;
        } else if (arg == "--out-sc2") {
            opts.out_sc2 = true;
        } else if (arg == "--color-system") {
            std::string value = require_value(arg);
            if (value == "msx1") {
                opts.color_system = MSX1PQCore::MSX1PQ_COLOR_SYS_MSX1;
            } else if (value == "msx2") {
                opts.color_system = MSX1PQCore::MSX1PQ_COLOR_SYS_MSX2;
            } else {
                throw std::runtime_error("Unknown color system: " + value);
            }
        } else if (arg == "--dither") {
            opts.use_dither = true;
        } else if (arg == "--no-dither") {
            opts.use_dither = false;
        } else if (arg == "--palette92") {
            opts.use_palette_color = true;
        } else if (arg == "--dark-dither") {
            opts.use_dark_dither = true;
        } else if (arg == "--no-dark-dither") {
            opts.use_dark_dither = false;
        } else if (arg == "--no-preprocess") {
            opts.use_preprocess = false;
        } else if (arg == "--8dot") {
            auto parsed = parse_8dot_mode(require_value(arg));
            if (!parsed) {
                throw std::runtime_error("Unknown 8dot mode");
            }
            opts.use_8dot2col = *parsed;
        } else if (arg == "--distance") {
            std::string value = require_value(arg);
            if (value == "rgb") {
                opts.use_hsb = false;
            } else if (value == "hsb") {
                opts.use_hsb = true;
            } else {
                throw std::runtime_error("Unknown distance mode: " + value);
            }
        } else if (arg == "--weight-h") {
            opts.weight_h = std::stof(require_value(arg));
        } else if (arg == "--weight-s") {
            opts.weight_s = std::stof(require_value(arg));
        } else if (arg == "--weight-b") {
            opts.weight_b = std::stof(require_value(arg));
        } else if (arg == "--pre-posterize") {
            opts.pre_posterize = std::stoi(require_value(arg));
        } else if (arg == "--pre-sat") {
            opts.pre_sat = std::stof(require_value(arg));
        } else if (arg == "--pre-gamma") {
            opts.pre_gamma = std::stof(require_value(arg));
        } else if (arg == "--pre-highlight") {
            opts.pre_highlight = std::stof(require_value(arg));
        } else if (arg == "--pre-hue") {
            opts.pre_hue = std::stof(require_value(arg));
        } else if (arg == "--pre-sharpness") {
            opts.pre_sharpness = std::stof(require_value(arg));
        } else if (arg == "--pre-lut") {
            opts.pre_lut_path = require_value(arg);
        } else if (arg == "--force" || arg == "-f") {
            opts.force = true;
        } else if (arg == "--version" || arg == "-v") {
            print_version(argv[0]);
            return false;
        } else if (arg == "--help" || arg == "-h") {
            print_usage(argv[0], detect_usage_language_from_env());
            return false;
        } else if (arg == "--help-ja") {
            print_usage(argv[0], UsageLanguage::Japanese);
            return false;
        } else if (arg == "--help-en") {
            print_usage(argv[0], UsageLanguage::English);
            return false;
        } else {
            throw std::runtime_error("Unknown argument: " + arg);
        }
    }

    if (opts.input_path.empty() || opts.output_dir.empty()) {
        throw std::runtime_error("--input and --output are required");
    }

    if (opts.out_sc2 && opts.out_sc5) {
        throw std::runtime_error("--out-sc2 and --out-sc5 cannot be used together");
    }

    if (opts.out_sc2 &&
        opts.use_8dot2col == MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_NONE) {
        throw std::runtime_error("--out-sc2 requires --8dot != none");
    }

    return true;
}

std::string to_lower_copy(const std::string& s) {
    std::string result = s;
    std::transform(result.begin(), result.end(), result.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return result;
}

bool has_png_extension(const fs::path& p) {
    return to_lower_copy(p.extension().string()) == ".png";
}

bool confirm_overwrite(const fs::path& path) {
    std::cout << "File " << path << " exists. Overwrite? [y/N]: ";
    std::string line;
    std::getline(std::cin, line);
    if (line.empty()) {
        return false;
    }
    char c = static_cast<char>(std::tolower(line[0]));
    return c == 'y';
}

void quantize_image(std::vector<RgbaPixel>& pixels, unsigned width, unsigned height, const CliOptions& opts) {
    MSX1PQCore::QuantInfo qi{};
    qi.use_dither      = opts.use_dither;
    qi.use_palette_color = opts.use_palette_color;
    qi.use_8dot2col    = opts.use_8dot2col;
    qi.use_hsb         = opts.use_hsb;
    qi.w_h             = MSX1PQCore::clamp01f(opts.weight_h);
    qi.w_s             = MSX1PQCore::clamp01f(opts.weight_s);
    qi.w_b             = MSX1PQCore::clamp01f(opts.weight_b);
    qi.pre_posterize   = std::clamp(opts.pre_posterize, 0, 255);
    qi.pre_sat         = opts.pre_sat;
    qi.pre_gamma       = opts.pre_gamma;
    qi.pre_highlight   = opts.pre_highlight;
    qi.pre_hue         = opts.pre_hue;
    qi.pre_sharpness   = MSX1PQCore::clamp01f(opts.pre_sharpness);
    qi.use_dark_dither = opts.use_dark_dither;
    qi.color_system    = opts.color_system;
    qi.pre_lut         = opts.pre_lut_data.empty() ? nullptr : opts.pre_lut_data.data();
    qi.pre_lut3d       = opts.pre_lut3d_data.empty() ? nullptr : opts.pre_lut3d_data.data();
    qi.pre_lut3d_size  = opts.pre_lut3d_size;

    if (opts.use_preprocess && qi.pre_sharpness > 0.0f) {
        const std::ptrdiff_t pitch = static_cast<std::ptrdiff_t>(width);
        const std::int32_t w = static_cast<std::int32_t>(width);
        const std::int32_t h = static_cast<std::int32_t>(height);
        MSX1PQCore::apply_sharpness_3x3(pixels.data(), pitch, w, h, qi.pre_sharpness);
    }

    for (unsigned y = 0; y < height; ++y) {
        for (unsigned x = 0; x < width; ++x) {
            RgbaPixel& px = pixels[y * width + x];
            std::uint8_t r = px.red;
            std::uint8_t g = px.green;
            std::uint8_t b = px.blue;

            if (opts.use_preprocess) {
                MSX1PQCore::apply_preprocess(&qi, r, g, b);
            }
            const MSX1PQ::QuantColor& qc = MSX1PQCore::quantize_pixel(
                qi,
                r,
                g,
                b,
                static_cast<std::int32_t>(x),
                static_cast<std::int32_t>(y));

            px.red   = qc.r;
            px.green = qc.g;
            px.blue  = qc.b;
        }
    }

    if (!qi.use_palette_color &&
        qi.use_8dot2col != MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_NONE) {
        const std::ptrdiff_t pitch = static_cast<std::ptrdiff_t>(width);
        const std::int32_t w = static_cast<std::int32_t>(width);
        const std::int32_t h = static_cast<std::int32_t>(height);

        switch (qi.use_8dot2col) {
        case MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_FAST1:
            MSX1PQCore::apply_8dot2col_fast1(pixels.data(), pitch, w, h, qi.color_system);
            break;
        case MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BASIC1:
            MSX1PQCore::apply_8dot2col_basic1(pixels.data(), pitch, w, h, qi.color_system);
            break;
        case MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BEST1:
            MSX1PQCore::apply_8dot2col_best1(pixels.data(), pitch, w, h, qi.color_system);
            break;
        case MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_ATTR_BEST:
            MSX1PQCore::apply_8dot2col_attr_best(pixels.data(), pitch, w, h, qi.color_system);
            break;
        case MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_PENALTY_BEST:
            MSX1PQCore::apply_8dot2col_attr_best_penalty(pixels.data(), pitch, w, h, qi.color_system);
            break;
        default:
            break;
        }
    }
}

bool write_png(const fs::path& output_path, const std::vector<RgbaPixel>& pixels, unsigned width, unsigned height) {
    std::vector<unsigned char> raw;
    raw.reserve(pixels.size() * 4);
    for (const auto& p : pixels) {
        raw.push_back(p.red);
        raw.push_back(p.green);
        raw.push_back(p.blue);
        raw.push_back(p.alpha);
    }

    const unsigned error = lodepng::encode(output_path.string(), raw, width, height);
    if (error) {
        std::cerr << "Failed to write PNG: " << output_path << " (" << lodepng_error_text(error) << ")\n";
        return false;
    }
    return true;
}

constexpr int kSc5Width = 256;
constexpr int kSc5Height = 212;
constexpr int kSc2Width = 256;
constexpr int kSc2Height = 192;

std::array<MSX1PQ::QuantColor, 16> make_sc5_palette(int color_system) {
    std::array<MSX1PQ::QuantColor, 16> palette{};
    palette[0] = {0, 0, 0};

    const MSX1PQ::QuantColor* base = MSX1PQCore::get_basic_palette(color_system);
    for (int i = 0; i < MSX1PQ::kNumBasicColors && (i + 1) < static_cast<int>(palette.size()); ++i) {
        palette[static_cast<size_t>(i + 1)] = base[i];
    }

    return palette;
}

int nearest_palette_index(const std::array<MSX1PQ::QuantColor, 16>& palette, const RgbaPixel& px) {
    long best_dist = 0x7fffffffL;
    int best_idx = 0;

    for (size_t i = 0; i < palette.size(); ++i) {
        long dr = static_cast<long>(px.red) - static_cast<long>(palette[i].r);
        long dg = static_cast<long>(px.green) - static_cast<long>(palette[i].g);
        long db = static_cast<long>(px.blue) - static_cast<long>(palette[i].b);

        long d2 = dr * dr + dg * dg + db * db;
        if (d2 < best_dist) {
            best_dist = d2;
            best_idx = static_cast<int>(i);
        }
    }

    return best_idx;
}

bool write_sc5(const fs::path& output_path, const std::vector<RgbaPixel>& pixels, unsigned width, unsigned height, int color_system) {
    const auto palette = make_sc5_palette(color_system);

    std::vector<std::uint8_t> color_codes(static_cast<size_t>(kSc5Width * kSc5Height), 0);

    const int copy_width = static_cast<int>(std::min<unsigned>(kSc5Width, width));
    const int copy_height = static_cast<int>(std::min<unsigned>(kSc5Height, height));

    const int src_offset_x = 0;
    const int src_offset_y = 0;
    const int dst_offset_x = 0;
    const int dst_offset_y = 0;

    for (int y = 0; y < copy_height; ++y) {
        const unsigned src_y = static_cast<unsigned>(src_offset_y + y);
        const unsigned dst_y = static_cast<unsigned>(dst_offset_y + y);
        for (int x = 0; x < copy_width; ++x) {
            const unsigned src_x = static_cast<unsigned>(src_offset_x + x);
            const unsigned dst_x = static_cast<unsigned>(dst_offset_x + x);
            const RgbaPixel& px = pixels[static_cast<size_t>(src_y * width + src_x)];
            color_codes[static_cast<size_t>(dst_y * kSc5Width + dst_x)] = static_cast<std::uint8_t>(nearest_palette_index(palette, px));
        }
    }

    std::vector<std::uint8_t> packed;
    packed.reserve(static_cast<size_t>(kSc5Width * kSc5Height / 2));
    for (int y = 0; y < kSc5Height; ++y) {
        for (int x = 0; x < kSc5Width; x += 2) {
            const std::uint8_t left = static_cast<std::uint8_t>(color_codes[static_cast<size_t>(y * kSc5Width + x)] & 0x0F);
            const std::uint8_t right = static_cast<std::uint8_t>(color_codes[static_cast<size_t>(y * kSc5Width + x + 1)] & 0x0F);
            packed.push_back(static_cast<std::uint8_t>((left << 4) | right));
        }
    }

    std::ofstream ofs(output_path, std::ios::binary);
    if (!ofs) {
        std::cerr << "Failed to open output file: " << output_path << "\n";
        return false;
    }

    // SC5ヘッダ
    unsigned char header[7];
    header[0] = 0xFE;      // BSAVE signature
    header[1] = 0x00;      // Start low
    header[2] = 0x00;      // Start high
    header[3] = 0x00;      // End low   (0x6B00)
    header[4] = 0x6B;      // End high
    header[5] = 0x00;      // Exec low
    header[6] = 0x00;      // Exec high

    ofs.write(reinterpret_cast<const char*>(header), 7);
    if (!ofs) {
        std::cerr << "Failed to write BSAVE header: " << output_path << "\n";
        return false;
    }

    ofs.write(reinterpret_cast<const char*>(packed.data()), static_cast<std::streamsize>(packed.size()));
    if (!ofs) {
        std::cerr << "Failed to write SC5 data: " << output_path << "\n";
        return false;
    }

    return true;
}

bool write_sc2(const fs::path& output_path,
               const std::vector<RgbaPixel>& pixels,
               unsigned width,
               unsigned height,
               int color_system) {
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

    std::ofstream ofs(output_path, std::ios::binary);
    if (!ofs) {
        std::cerr << "Failed to open output file: " << output_path << "\n";
        return false;
    }

    unsigned char header[7];
    header[0] = 0xFE;
    header[1] = 0x00;
    header[2] = 0x00;
    header[3] = 0xFF;
    header[4] = 0x3F;
    header[5] = 0x00;
    header[6] = 0x00;

    ofs.write(reinterpret_cast<const char*>(header), 7);
    if (!ofs) {
        std::cerr << "Failed to write BSAVE header: " << output_path << "\n";
        return false;
    }

    ofs.write(reinterpret_cast<const char*>(vram.data()), static_cast<std::streamsize>(vram.size()));
    if (!ofs) {
        std::cerr << "Failed to write SC2 data: " << output_path << "\n";
        return false;
    }

    return true;
}

bool process_file(const fs::path& input, const fs::path& output, const CliOptions& opts) {
    std::vector<unsigned char> raw;
    unsigned width = 0;
    unsigned height = 0;

    const unsigned error = lodepng::decode(raw, width, height, input.string());
    if (error) {
        std::cerr << "Failed to read PNG: " << input << " (" << lodepng_error_text(error) << ")\n";
        return false;
    }

    if (raw.size() != static_cast<size_t>(width * height * 4)) {
        std::cerr << "Unexpected image size for: " << input << "\n";
        return false;
    }

    std::vector<RgbaPixel> pixels(width * height);
    for (unsigned i = 0; i < width * height; ++i) {
        pixels[i].red   = raw[i * 4 + 0];
        pixels[i].green = raw[i * 4 + 1];
        pixels[i].blue  = raw[i * 4 + 2];
        pixels[i].alpha = raw[i * 4 + 3];
    }

    quantize_image(pixels, width, height, opts);
    if (opts.out_sc5) {
        return write_sc5(output, pixels, width, height, opts.color_system);
    }
    if (opts.out_sc2) {
        return write_sc2(output, pixels, width, height, opts.color_system);
    }
    return write_png(output, pixels, width, height);
}

std::vector<fs::path> collect_inputs(const fs::path& input_path) {
    if (fs::is_regular_file(input_path)) {
        return {input_path};
    }

    std::vector<fs::path> results;
    for (const auto& entry : fs::directory_iterator(input_path)) {
        if (entry.is_regular_file() && has_png_extension(entry.path())) {
            results.push_back(entry.path());
        }
    }
    std::sort(results.begin(), results.end());
    return results;
}

} // namespace

int main(int argc, char** argv) {
    CliOptions opts;
    try {
        if (!parse_arguments(argc, argv, opts)) {
            return 1;
        }
    } catch (const std::exception& e) {
        std::cerr << e.what() << "\n";
        print_usage(argv[0]);
        return 1;
    }

    if (!fs::exists(opts.input_path)) {
        std::cerr << "Input path does not exist: " << opts.input_path << "\n";
        return 1;
    }

    if (!opts.pre_lut_path.empty()) {
        if (!fs::exists(opts.pre_lut_path)) {
            std::cerr << "LUT file does not exist: " << opts.pre_lut_path << "\n";
            return 1;
        }
        if (!MSX1PQCore::load_pre_lut(opts.pre_lut_path.string(), opts.pre_lut_data, opts.pre_lut3d_data, opts.pre_lut3d_size)) {
            return 1;
        }
    }

    if (!fs::exists(opts.output_dir)) {
        fs::create_directories(opts.output_dir);
    }

    const auto inputs = collect_inputs(opts.input_path);
    if (inputs.empty()) {
        std::cerr << "No PNG files to process in: " << opts.input_path << "\n";
        return 1;
    }

    int success_count = 0;
    for (const auto& input : inputs) {
        fs::path output_filename = input.filename();
        if (!opts.output_prefix.empty()) {
            output_filename = fs::path(opts.output_prefix + output_filename.string());
        }
        if (!opts.output_suffix.empty()) {
            const auto ext = output_filename.extension();
            const std::string stem_with_suffix = output_filename.stem().string() + opts.output_suffix;
            output_filename = fs::path(stem_with_suffix + ext.string());
        }

        if (opts.out_sc5) {
            output_filename.replace_extension(".sc5");
        } else if (opts.out_sc2) {
            output_filename.replace_extension(".sc2");
        }

        fs::path out_path = opts.output_dir / output_filename;
        if (fs::exists(out_path) && !opts.force) {
            if (!confirm_overwrite(out_path)) {
                std::cout << "Skipped: " << out_path << "\n";
                continue;
            }
        }

        if (!has_png_extension(input)) {
            std::cout << "Skip (not PNG): " << input << "\n";
            continue;
        }

        if (process_file(input, out_path, opts)) {
            std::cout << "Processed: " << input << " -> " << out_path << "\n";
            ++success_count;
        }
    }

    if (success_count == 0) {
        return 1;
    }
    return 0;
}
