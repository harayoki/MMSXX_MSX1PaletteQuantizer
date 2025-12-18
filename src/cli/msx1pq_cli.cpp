#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <iterator>
#include <stdexcept>
#include <string>
#include <sstream>
#include <vector>
#include <array>

#include "../core/MSX1PQCore.h"
#include "../core/MSX1PQPalettes.h"
#include "lodepng.h"

namespace fs = std::filesystem;

struct CliOptions {
    fs::path input_path;
    std::vector<fs::path> input_paths;
    fs::path output_dir;
    std::string output_prefix;
    std::string output_suffix;
    bool force{false};

    std::array<bool, 16> palette_enabled{{
        true, true, true, true, true, true, true, true,
        true, true, true, true, true, true, true, true}};

    int color_system{MSX1PQCore::MSX1PQ_COLOR_SYS_MSX1};
    bool out_sc2{false};
    bool use_dither{true};
    bool use_palette_color{false};
    bool use_dark_dither{true};
    bool use_preprocess{true};
    int use_8dot2col{MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_BEST1};
    bool use_hsv{false};
    float weight_h{1.0f};
    float weight_s{0.5f};
    float weight_b{0.75f};
    float weight_r{1.0f};
    float weight_g{1.0f};
    float weight_b_rgb{1.0f};
    int pre_posterize{16};
    float pre_sat{0.0f};
    float pre_gamma{1.0f};
    float pre_contrast{1.0f};
    float pre_hue{0.0f};
    float pre_sharpen_black{0.0f};
    fs::path pre_lut_path;
    std::vector<std::uint8_t> pre_lut_data;
    std::vector<float> pre_lut3d_data;
    int pre_lut3d_size{0};
    int scale{1};

    struct FitSize {
        int width{0};
        int height{0};
    };

    std::optional<FitSize> fit_size;
    int background_color{1};
    int offset_x{0};

    enum class AnchorPosition {
        TopLeft,
        TopCenter,
        TopRight,
        CenterLeft,
        Center,
        CenterRight,
        BottomLeft,
        BottomCenter,
        BottomRight,
    };

    AnchorPosition anchor{AnchorPosition::Center};
    std::map<std::size_t, int> index_offset_overrides;
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

constexpr const char* kVersion = "v0.8b";

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
                  << "使い方(複数入力): " << prog << " --inputs <ファイル...> --output <ディレクトリ> [オプション]\n"
                  << "1つの画像またはフォルダ内の複数の画像を受け取り、MSX1(TMS9918)の表示ルールに則った画像に変換します。\n"
                  << "オプション:\n"
                  << "  --input, -i <ファイル|ディレクトリ>  入力PNGファイルまたはディレクトリを指定\n"
                  << "  --inputs <ファイル...>            複数の入力PNGファイルを指定(オプションはすべて共通)\n"
                  << "  --output, -o <ディレクトリ>       出力先ディレクトリを指定\n"
                  << "  --out-prefix <文字列>          出力ファイル名の先頭に付与する接頭辞を指定\n"
                  << "  --out-suffix <文字列>          出力ファイル名の末尾（拡張子の前）に付与する接尾辞を指定\n"
                  << "  --out-sc2                   SCREEN2 .sc2バイナリで出力\n"
                  << "  --color-system <msx1|msx2>   (デフォルト: msx1)\n"
                  << "  --dither / --no-dither       (デフォルト: dither)\n"
                  << "  --dark-dither / --no-dark-dither (デフォルト: ダークディザーパレットを使用)\n"
                  << "  --no-preprocess             前処理をスキップ\n"
                  << "  --8dot <none|fast|basic|best|best-attr|best-trans> (デフォルト: best)\n"
                  << "  --distance <rgb|hsv>         (デフォルト: rgb)\n"
                  << "  --weight-h <0-1> --weight-s <0-1> --weight-v <0-1>\n"
                  << "  --weight-r <0-1> --weight-g <0-1> --weight-b <0-1>\n"
                  << "  --pre-posterize <0-255>      前処理でポスタリゼーションを適用 (デフォルト: 16 1以下は処理なし)\n"
                  << "  --pre-sat <0-10>             処理前に彩度を高く補正 (デフォルト: 0.0)\n"
                  << "  --pre-gamma <0-10>           処理前にガンマを適用 (デフォルト: 1.0)\n"
                  << "  --pre-contrast <0-10>        処理前にコントラストを調整 (デフォルト: 1.0)\n"
                  << "  --pre-hue <-180-180>         処理前に色相を変更 (デフォルト: 0.0)\n"
                  << "  --pre-sharpen-black <0-10>   黒周辺のみシャープ化 (デフォルト: 0.0 おすすめ: 1.0)\n"
                  << "  --disable-colors <番号|範囲>... パレット番号(1-15)を無効化。例: --disable-colors 2 4 7-8 15 (最低2色が必要)\n"
                  << "  --pre-lut <ファイル>           処理前にRGB LUT(256行のRGB値)や.cube 3D LUTを適用\n"
                  << "  --scale <1-4>                出力PNGを整数倍で拡大 (デフォルト: 1)\n"
                  << "  --fit-size <W> <H>         入力を指定サイズに調整 (デフォルト: 指定なし)\n"
                  << "  --anchor <TL|TC|TR|CL|C|CR|BL|BC|BR>  クリッピング/余白の基準位置 (デフォルト: C)\n"
                  << "  --bg-color <1-15>           余白やシフトで使う背景色パレット番号 (デフォルト: 1)\n"
                  << "  --offset-x <-7-7>           調整前に左右へオフセット (デフォルト: 0)\n"
                  << "  --offset-x-index <idx> <-7-7> 個別INDEXごとにオフセットを上書き\n"
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
              << "Usage (multiple inputs): " << prog << " --inputs <files...> --output <dir> [options]\n"
              << "Convert a single image or multiple images in a folder into images that comply with MSX1 (TMS9918) display rules.\n"
              << "Options:\n"
              << "  --input, -i <file|dir>       Specify the input PNG file or directory\n"
              << "  --inputs <files...>         Specify multiple input PNG files (all options are shared)\n"
              << "  --output, -o <dir>           Specify the output directory\n"
              << "  --out-prefix <string>       Prefix to add to output file names\n"
              << "  --out-suffix <string>       Suffix to add before the output file extension\n"
              << "  --out-sc2                   Output SCREEN2 .sc2 binary\n"
              << "  --color-system <msx1|msx2>   (default: msx1)\n"
              << "  --dither / --no-dither       (default: dither)\n"
              << "  --palette92                  (for dev) Output 92 color palette without dithering\n"
              << "  --dark-dither / --no-dark-dither (default: use dark dither palettes)\n"
              << "  --no-preprocess             Skip preprocessing adjustments\n"
              << "  --8dot <none|fast|basic|best|best-attr|best-trans> (default: best)\n"
              << "  --distance <rgb|hsv>         (default: rgb)\n"
              << "  --weight-h <0-1> --weight-s <0-1> --weight-v <0-1>\n"
              << "  --weight-r <0-1> --weight-g <0-1> --weight-b <0-1>\n"
              << "  --pre-posterize <0-255>      Apply posterization before processing (default: 16,  skipped if <= 1)\n"
              << "  --pre-sat <0-10>             Increase saturation before processing (default: 0.0)\n"
              << "  --pre-gamma <0-10>           Apply a gamma curve before processing (default: 1.0)\n"
              << "  --pre-contrast <0-10>        Adjust contrast before processing (default: 1.0)\n"
              << "  --pre-hue <-180-180>         Adjust hue before processing (default: 0.0)\n"
              << "  --pre-sharpen-black <0-10>   Sharpen only near black areas before processing (default: 0.0, recommended: 1.0)\n"
              << "  --disable-colors <index|range>... Disable palette indices (1-15). e.g. --disable-colors 2 4 7-8 15. At least two colors must remain enabled\n"
              << "  --pre-lut <file>             Apply RGB LUT (256 rows) or .cube 3D LUT before processing\n"
              << "  --scale <1-4>                Scale output PNG by an integer factor (default: 1)\n"
              << "  --fit-size <W> <H>           Adjust input to the specified size (default: none)\n"
              << "  --anchor <TL|TC|TR|CL|C|CR|BL|BC|BR>  Anchor point for cropping/padding (default: C)\n"
              << "  --bg-color <1-15>            Background palette index for padding/offset (default: 1)\n"
              << "  --offset-x <-7-7>            Horizontal offset before adjustment (default: 0)\n"
              << "  --offset-x-index <idx> <-7-7> Override horizontal offset per INDEX\n"
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

std::optional<CliOptions::AnchorPosition> parse_anchor(const std::string& value) {
    const std::string lower = to_lower_copy(value);
    if (lower == "tl") return CliOptions::AnchorPosition::TopLeft;
    if (lower == "tc") return CliOptions::AnchorPosition::TopCenter;
    if (lower == "tr") return CliOptions::AnchorPosition::TopRight;
    if (lower == "cl") return CliOptions::AnchorPosition::CenterLeft;
    if (lower == "c")  return CliOptions::AnchorPosition::Center;
    if (lower == "cr") return CliOptions::AnchorPosition::CenterRight;
    if (lower == "bl") return CliOptions::AnchorPosition::BottomLeft;
    if (lower == "bc") return CliOptions::AnchorPosition::BottomCenter;
    if (lower == "br") return CliOptions::AnchorPosition::BottomRight;
    return std::nullopt;
}

bool parse_arguments(int argc, char** argv, CliOptions& opts) {
    if (argc < 2) {
        print_usage(argv[0], detect_usage_language_from_env());
        return false;
    }

    auto parse_disable_token = [&](const std::string& token) {
        auto dash_pos = token.find('-');
        if (dash_pos == std::string::npos) {
            int idx = std::stoi(token);
            if (idx < 1 || idx >= static_cast<int>(opts.palette_enabled.size())) {
                throw std::runtime_error("Color index for disable-colors must be between 1 and 15");
            }
            opts.palette_enabled[static_cast<size_t>(idx)] = false;
            return;
        }

        std::string start_str = token.substr(0, dash_pos);
        std::string end_str = token.substr(dash_pos + 1);
        if (start_str.empty() || end_str.empty()) {
            throw std::runtime_error("Invalid range format for disable-colors. Use start-end, e.g., 3-5");
        }

        int start = std::stoi(start_str);
        int end = std::stoi(end_str);
        if (start > end) {
            throw std::runtime_error("disable-colors range start must be <= end");
        }
        if (start < 1 || end >= static_cast<int>(opts.palette_enabled.size())) {
            throw std::runtime_error("Color index for disable-colors must be between 1 and 15");
        }

        for (int idx = start; idx <= end; ++idx) {
            opts.palette_enabled[static_cast<size_t>(idx)] = false;
        }
    };

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
        } else if (arg == "--inputs") {
            if (i + 1 >= argc) {
                throw std::runtime_error("Missing values for --inputs");
            }

            int parsed_count = 0;
            while (i + 1 < argc) {
                const std::string next = argv[i + 1];
                if (!next.empty() && next[0] == '-') {
                    break;
                }
                ++i;
                opts.input_paths.emplace_back(next);
                ++parsed_count;
            }

            if (parsed_count == 0) {
                throw std::runtime_error("Missing values for --inputs");
            }
        } else if (arg == "--output" || arg == "-o") {
            opts.output_dir = require_value(arg);
        } else if (arg == "--out-prefix") {
            opts.output_prefix = require_value(arg);
        } else if (arg == "--out-suffix") {
            opts.output_suffix = require_value(arg);
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
                opts.use_hsv = false;
            } else if (value == "hsv") {
                opts.use_hsv = true;
            } else {
                throw std::runtime_error("Unknown distance mode: " + value);
            }
        } else if (arg == "--disable-colors") {
            if (i + 1 >= argc) {
                throw std::runtime_error("Missing values for --disable-colors");
            }

            int parsed_count = 0;
            while (i + 1 < argc) {
                const std::string next = argv[i + 1];
                if (!next.empty() && next[0] == '-') {
                    break;
                }
                ++i;
                parse_disable_token(next);
                ++parsed_count;
            }

            if (parsed_count == 0) {
                throw std::runtime_error("Missing values for --disable-colors");
            }
        } else if (arg == "--weight-h") {
            opts.weight_h = std::stof(require_value(arg));
        } else if (arg == "--weight-s") {
            opts.weight_s = std::stof(require_value(arg));
        } else if (arg == "--weight-v") {
            opts.weight_b = std::stof(require_value(arg));
        } else if (arg == "--weight-r") {
            opts.weight_r = std::stof(require_value(arg));
        } else if (arg == "--weight-g") {
            opts.weight_g = std::stof(require_value(arg));
        } else if (arg == "--weight-b") {
            opts.weight_b_rgb = std::stof(require_value(arg));
        } else if (arg == "--pre-posterize") {
            opts.pre_posterize = std::stoi(require_value(arg));
        } else if (arg == "--pre-sat") {
            opts.pre_sat = std::stof(require_value(arg));
        } else if (arg == "--pre-gamma") {
            opts.pre_gamma = std::stof(require_value(arg));
        } else if (arg == "--pre-contrast") {
            opts.pre_contrast = std::stof(require_value(arg));
        } else if (arg == "--pre-hue") {
            opts.pre_hue = std::stof(require_value(arg));
        } else if (arg == "--pre-sharpen-black") {
            opts.pre_sharpen_black = std::stof(require_value(arg));
        } else if (arg == "--pre-lut") {
            opts.pre_lut_path = require_value(arg);
        } else if (arg == "--scale") {
            opts.scale = std::stoi(require_value(arg));
        } else if (arg == "--fit-size") {
            CliOptions::FitSize size;
            size.width = std::stoi(require_value(arg));
            size.height = std::stoi(require_value(arg));
            opts.fit_size = size;
        } else if (arg == "--anchor") {
            auto parsed = parse_anchor(require_value(arg));
            if (!parsed) {
                throw std::runtime_error("Unknown anchor");
            }
            opts.anchor = *parsed;
        } else if (arg == "--bg-color") {
            opts.background_color = std::stoi(require_value(arg));
        } else if (arg == "--offset-x") {
            opts.offset_x = std::stoi(require_value(arg));
        } else if (arg == "--offset-x-index") {
            const std::size_t idx = static_cast<std::size_t>(std::stoul(require_value(arg)));
            opts.index_offset_overrides[idx] = std::stoi(require_value(arg));
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

    if ((!opts.input_paths.empty() && !opts.input_path.empty()) ||
        (opts.input_paths.empty() && opts.input_path.empty())) {
        throw std::runtime_error("Specify either --input or --inputs");
    }

    if (opts.output_dir.empty()) {
        throw std::runtime_error("--output is required");
    }

    const int enabled_colors = static_cast<int>(std::count(
        opts.palette_enabled.begin(), opts.palette_enabled.end(), true));
    if (enabled_colors < 1) {
        throw std::runtime_error("At least one palette color must remain enabled");
    }

    if (opts.scale < 1 || opts.scale > 4) {
        throw std::runtime_error("--scale must be between 1 and 4");
    }

    auto validate_color = [](int color) {
        if (color < 1 || color > 15) {
            throw std::runtime_error("Background color must be between 1 and 15");
        }
    };
    auto validate_offset = [](int offset) {
        if (offset < -7 || offset > 7) {
            throw std::runtime_error("Horizontal offset must be between -7 and 7");
        }
    };
    auto validate_fit_size = [](const CliOptions::FitSize& size) {
        if (size.width <= 0 || size.height <= 0) {
            throw std::runtime_error("Fit size width and height must be positive integers");
        }
    };

    validate_color(opts.background_color);
    validate_offset(opts.offset_x);
    if (opts.fit_size) {
        validate_fit_size(*opts.fit_size);
    }
    for (const auto& [_, offset] : opts.index_offset_overrides) {
        validate_offset(offset);
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

std::array<MSX1PQ::QuantColor, MSX1PQ::kNumBasicColors> get_basic_palette(int color_system);

RgbaPixel get_background_pixel(int color_index, int color_system) {
    const auto palette = get_basic_palette(color_system);
    const std::size_t palette_idx = static_cast<std::size_t>(std::clamp(
        color_index - 1,
        0,
        static_cast<int>(MSX1PQ::kNumBasicColors - 1)));
    const auto& color = palette[palette_idx];
    RgbaPixel px{};
    px.red = color.r;
    px.green = color.g;
    px.blue = color.b;
    px.alpha = 255;
    return px;
}

void apply_horizontal_offset(std::vector<RgbaPixel>& pixels, unsigned width, unsigned height, int offset_x, const RgbaPixel& bg) {
    if (offset_x == 0) {
        return;
    }

    std::vector<RgbaPixel> shifted(pixels.size(), bg);
    for (unsigned y = 0; y < height; ++y) {
        for (unsigned x = 0; x < width; ++x) {
            const int dest_x = static_cast<int>(x) + offset_x;
            if (dest_x < 0 || dest_x >= static_cast<int>(width)) {
                continue;
            }
            shifted[static_cast<std::size_t>(y * width + static_cast<unsigned>(dest_x))] = pixels[static_cast<std::size_t>(y * width + x)];
        }
    }

    pixels.swap(shifted);
}

void fit_to_canvas(std::vector<RgbaPixel>& pixels,
                   unsigned& width,
                   unsigned& height,
                   int canvas_w,
                   int canvas_h,
                   CliOptions::AnchorPosition anchor,
                   const RgbaPixel& bg) {
    const int src_w = static_cast<int>(width);
    const int src_h = static_cast<int>(height);

    const bool wider = src_w > canvas_w;
    const bool taller = src_h > canvas_h;

    int copy_w = wider ? canvas_w : src_w;
    int copy_h = taller ? canvas_h : src_h;

    const auto horizontal_anchor = [&](CliOptions::AnchorPosition pos) {
        switch (pos) {
        case CliOptions::AnchorPosition::TopLeft:
        case CliOptions::AnchorPosition::CenterLeft:
        case CliOptions::AnchorPosition::BottomLeft:
            return -1;
        case CliOptions::AnchorPosition::TopCenter:
        case CliOptions::AnchorPosition::Center:
        case CliOptions::AnchorPosition::BottomCenter:
            return 0;
        default:
            return 1;
        }
    };
    const auto vertical_anchor = [&](CliOptions::AnchorPosition pos) {
        switch (pos) {
        case CliOptions::AnchorPosition::TopLeft:
        case CliOptions::AnchorPosition::TopCenter:
        case CliOptions::AnchorPosition::TopRight:
            return -1;
        case CliOptions::AnchorPosition::CenterLeft:
        case CliOptions::AnchorPosition::Center:
        case CliOptions::AnchorPosition::CenterRight:
            return 0;
        default:
            return 1;
        }
    };

    const int h_anchor = horizontal_anchor(anchor);
    const int v_anchor = vertical_anchor(anchor);

    int src_x = 0;
    int src_y = 0;
    int dst_x = 0;
    int dst_y = 0;

    if (wider) {
        if (h_anchor < 0) {
            src_x = 0;
        } else if (h_anchor == 0) {
            src_x = (src_w - canvas_w) / 2;
        } else {
            src_x = src_w - canvas_w;
        }
    } else {
        if (h_anchor < 0) {
            dst_x = 0;
        } else if (h_anchor == 0) {
            dst_x = (canvas_w - src_w) / 2;
        } else {
            dst_x = canvas_w - src_w;
        }
    }

    if (taller) {
        if (v_anchor < 0) {
            src_y = 0;
        } else if (v_anchor == 0) {
            src_y = (src_h - canvas_h) / 2;
        } else {
            src_y = src_h - canvas_h;
        }
    } else {
        if (v_anchor < 0) {
            dst_y = 0;
        } else if (v_anchor == 0) {
            dst_y = (canvas_h - src_h) / 2;
        } else {
            dst_y = canvas_h - src_h;
        }
    }

    std::vector<RgbaPixel> canvas(static_cast<std::size_t>(canvas_w * canvas_h), bg);
    for (int y = 0; y < copy_h; ++y) {
        for (int x = 0; x < copy_w; ++x) {
            const int src_idx_x = src_x + x;
            const int src_idx_y = src_y + y;
            const int dst_idx_x = dst_x + x;
            const int dst_idx_y = dst_y + y;
            canvas[static_cast<std::size_t>(dst_idx_y * canvas_w + dst_idx_x)] =
                pixels[static_cast<std::size_t>(src_idx_y * width + src_idx_x)];
        }
    }

    pixels.swap(canvas);
    width = static_cast<unsigned>(canvas_w);
    height = static_cast<unsigned>(canvas_h);
}

void quantize_image(std::vector<RgbaPixel>& pixels, unsigned width, unsigned height, const CliOptions& opts) {
    MSX1PQCore::QuantInfo qi{};
    qi.use_dither      = opts.use_dither;
    qi.use_palette_color = opts.use_palette_color;
    qi.use_8dot2col    = opts.use_8dot2col;
    qi.use_hsv         = opts.use_hsv;
    qi.w_h             = MSX1PQCore::clamp01f(opts.weight_h);
    qi.w_s             = MSX1PQCore::clamp01f(opts.weight_s);
    qi.w_b             = MSX1PQCore::clamp01f(opts.weight_b);
    qi.w_r             = MSX1PQCore::clamp01f(opts.weight_r);
    qi.w_g             = MSX1PQCore::clamp01f(opts.weight_g);
    qi.w_b_rgb         = MSX1PQCore::clamp01f(opts.weight_b_rgb);
    qi.pre_posterize   = std::clamp(opts.pre_posterize, 0, 255);
    qi.pre_sat         = opts.pre_sat;
    qi.pre_gamma       = opts.pre_gamma;
    qi.pre_contrast    = opts.pre_contrast;
    qi.pre_hue         = opts.pre_hue;
    qi.pre_sharpen_black = MSX1PQCore::clamp_value(opts.pre_sharpen_black, 0.0f, 10.0f);
    qi.use_dark_dither = opts.use_dark_dither;
    qi.color_system    = opts.color_system;
    qi.pre_lut         = opts.pre_lut_data.empty() ? nullptr : opts.pre_lut_data.data();
    qi.pre_lut3d       = opts.pre_lut3d_data.empty() ? nullptr : opts.pre_lut3d_data.data();
    qi.pre_lut3d_size  = opts.pre_lut3d_size;

    for (int i = 0; i < MSX1PQ::kNumBasicColors; ++i) {
        const std::size_t src_idx = static_cast<std::size_t>(i + 1);
        if (src_idx < opts.palette_enabled.size()) {
            qi.palette_enabled[static_cast<std::size_t>(i)] = opts.palette_enabled[src_idx];
        }
    }

    if (opts.use_preprocess && qi.pre_sharpen_black > 0.0f) {
        const std::ptrdiff_t pitch = static_cast<std::ptrdiff_t>(width);
        MSX1PQCore::apply_black_edge_sharpen(
            pixels.data(),
            pitch,
            static_cast<std::int32_t>(width),
            static_cast<std::int32_t>(height),
            qi.pre_sharpen_black);
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

void scale_pixels(std::vector<RgbaPixel>& pixels, unsigned& width, unsigned& height, int scale) {
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

std::array<MSX1PQ::QuantColor, MSX1PQ::kNumBasicColors>
get_basic_palette(int color_system) {
    std::array<MSX1PQ::QuantColor, MSX1PQ::kNumBasicColors> palette{};

    if (color_system == MSX1PQCore::MSX1PQ_COLOR_SYS_MSX2) {
        std::copy_n(MSX1PQ::kBasicColorsMsx2, MSX1PQ::kNumBasicColors, palette.begin());
    } else {
        std::copy_n(MSX1PQ::kQuantColors, MSX1PQ::kNumBasicColors, palette.begin());
    }

    return palette;
}

bool write_palette_png(const fs::path& output_path,
                       const std::vector<RgbaPixel>& pixels,
                       unsigned width,
                       unsigned height,
                       int color_system) {
    const auto palette = get_basic_palette(color_system);

    std::vector<unsigned char> indices(pixels.size());
    for (std::size_t i = 0; i < pixels.size(); ++i) {
        const auto& px = pixels[i];
        if (px.alpha == 0) {
            indices[i] = 0;
            continue;
        }

        std::uint32_t best_distance = std::numeric_limits<std::uint32_t>::max();
        std::uint8_t best_index = 0;
        for (std::size_t pal_idx = 0; pal_idx < palette.size(); ++pal_idx) {
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

    const auto add_palette_entry = [&](std::uint8_t r, std::uint8_t g, std::uint8_t b, std::uint8_t a) {
        lodepng_palette_add(&state.info_png.color, r, g, b, a);
        lodepng_palette_add(&state.info_raw, r, g, b, a);
    };

    add_palette_entry(0, 0, 0, 0); // index 0: transparent black
    for (const auto& color : palette) {
        add_palette_entry(color.r, color.g, color.b, 255);
    }

    std::vector<unsigned char> png;
    const unsigned error = lodepng::encode(png, indices, width, height, state);
    if (error) {
        std::cerr << "Failed to write PNG: " << output_path << " (" << lodepng_error_text(error) << ")\n";
        return false;
    }

    const unsigned save_error = lodepng::save_file(png, output_path.string());
    if (save_error) {
        std::cerr << "Failed to save PNG: " << output_path << " (" << lodepng_error_text(save_error) << ")\n";
        return false;
    }
    return true;
}

constexpr int kSc2Width = 256;
constexpr int kSc2Height = 192;
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

bool process_file(const fs::path& input, const fs::path& output, const CliOptions& opts, std::size_t input_index) {
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

    const auto resolve_value_override = [](const auto& map, std::size_t idx, const auto& default_value) {
        const auto it = map.find(idx);
        if (it != map.end()) {
            return it->second;
        }
        return default_value;
    };

    const auto fit_to_size = opts.fit_size;
    const CliOptions::AnchorPosition anchor = opts.anchor;
    const int background_color = opts.background_color;
    const int offset_x = resolve_value_override(opts.index_offset_overrides, input_index, opts.offset_x);

    const RgbaPixel bg_pixel = get_background_pixel(background_color, opts.color_system);

    apply_horizontal_offset(pixels, width, height, offset_x, bg_pixel);

    if (fit_to_size) {
        fit_to_canvas(pixels, width, height, fit_to_size->width, fit_to_size->height, anchor, bg_pixel);
    }

    quantize_image(pixels, width, height, opts);
    if (opts.out_sc2) {
        return write_sc2(output, pixels, width, height, opts.color_system);
    }

    scale_pixels(pixels, width, height, opts.scale);
    return write_palette_png(output, pixels, width, height, opts.color_system);
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

    std::vector<fs::path> input_targets;
    if (!opts.input_paths.empty()) {
        input_targets = opts.input_paths;
    } else {
        input_targets.push_back(opts.input_path);
    }

    for (const auto& target : input_targets) {
        if (!fs::exists(target)) {
            std::cerr << "Input path does not exist: " << target << "\n";
            return 1;
        }
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

    std::vector<fs::path> inputs;
    for (const auto& target : input_targets) {
        const auto collected = collect_inputs(target);
        if (collected.empty()) {
            std::cerr << "No PNG files to process in: " << target << "\n";
            return 1;
        }
        inputs.insert(inputs.end(), collected.begin(), collected.end());
    }

    int success_count = 0;
    for (std::size_t input_index = 0; input_index < inputs.size(); ++input_index) {
        const auto& input = inputs[input_index];
        fs::path output_filename = input.filename();
        if (!opts.output_prefix.empty()) {
            output_filename = fs::path(opts.output_prefix + output_filename.string());
        }
        if (!opts.output_suffix.empty()) {
            const auto ext = output_filename.extension();
            const std::string stem_with_suffix = output_filename.stem().string() + opts.output_suffix;
            output_filename = fs::path(stem_with_suffix + ext.string());
        }

        if (opts.out_sc2) {
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

        if (process_file(input, out_path, opts, input_index)) {
            std::cout << "Processed: " << input << " -> " << out_path << "\n";
            ++success_count;
        }
    }

    if (success_count == 0) {
        return 1;
    }
    return 0;
}
