#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "MSX1PQPalettes.h"

namespace MSX1PQCore {

// ParamsSetup() の追加順と必ず一致させること
// AE 依存を排除した enum 定義
enum MSX1PQ_DistanceMode {
    MSX1PQ_DIST_MODE_RGB = 1,
    MSX1PQ_DIST_MODE_HSB = 2
};

enum MSX1PQ_EightDotMode {
    MSX1PQ_EIGHTDOT_MODE_NONE         = 1, // None
    MSX1PQ_EIGHTDOT_MODE_FAST1        = 2, // Lightweight version
    MSX1PQ_EIGHTDOT_MODE_BASIC1       = 3, // Standard version
    MSX1PQ_EIGHTDOT_MODE_BEST1        = 4, // Best version
    MSX1PQ_EIGHTDOT_MODE_ATTR_BEST    = 5, // Attribute cell BEST (8×N)
    MSX1PQ_EIGHTDOT_MODE_PENALTY_BEST = 6  // Transition penalty BEST
};

enum MSX1PQ_ColorSystem {
    MSX1PQ_COLOR_SYS_MSX1 = 1,
    MSX1PQ_COLOR_SYS_MSX2 = 2
};

struct QuantInfo {
    bool  use_dither{};
    bool  use_palette_color{};
    int   use_8dot2col{};
    bool  use_hsb{};
    float w_h{};
    float w_s{};
    float w_b{};
    int   pre_posterize{8};
    float pre_sat{};
    float pre_gamma{};
    float pre_highlight{};
    float pre_hue{};
    bool  use_dark_dither{};
    int   color_system{MSX1PQ_COLOR_SYS_MSX1};
    const std::uint8_t* pre_lut{nullptr};
    const float* pre_lut3d{nullptr};
    int pre_lut3d_size{0};
};

bool load_pre_lut(const std::string& path,
                  std::vector<std::uint8_t>& out1d,
                  std::vector<float>& out3d,
                  int& lut3d_size);

float clamp01f(float v);

template <typename T>
constexpr T clamp_value(const T& v, const T& lo, const T& hi)
{
    return (v < lo) ? lo : (v > hi ? hi : v);
}

void rgb_to_hsb(std::uint8_t r8, std::uint8_t g8, std::uint8_t b8,
                float &h, float &s, float &v);

void hsb_to_rgb(float h, float s, float v,
                std::uint8_t &r8, std::uint8_t &g8, std::uint8_t &b8);

void apply_preprocess(const QuantInfo *qi,
                      std::uint8_t &r8,
                      std::uint8_t &g8,
                      std::uint8_t &b8);

int nearest_palette_rgb(std::uint8_t r8, std::uint8_t g8, std::uint8_t b8,
                        int num_colors);

int nearest_palette_hsb(std::uint8_t r8, std::uint8_t g8, std::uint8_t b8,
                        float w_h, float w_s, float w_b,
                        int num_colors);

int nearest_basic_hsb(std::uint8_t r8, std::uint8_t g8, std::uint8_t b8,
                      float w_h, float w_s, float w_b);

const MSX1PQ::QuantColor* get_basic_palette(int color_system);

int find_basic_index_from_rgb(std::uint8_t r, std::uint8_t g, std::uint8_t b,
                              int color_system);

MSX1PQ::QuantColor quantize_pixel(const QuantInfo& qi,
                                  std::uint8_t r,
                                  std::uint8_t g,
                                  std::uint8_t b,
                                  std::int32_t x,
                                  std::int32_t y);

// ------------------------------------------------------------
// 横8ドット内2色制限
// ------------------------------------------------------------
static const int BASIC_COLORS = 15;

static const int ATTRCELL_HEIGHT   = 8;  // 4 or 8 で調整
static const double ATTR_LAMBDA    = 0.3; // 行の見た目とセル傾向のバランス
static const double TRANSITION_LAMBDA = 1.0; // 左右遷移ペナルティ

// Helper for transition penalty
int transition_cost_pair(int prevA, int prevB, int a, int b);

template<typename PixelT>
void apply_8dot2col_basic1(
    PixelT* data,
    std::ptrdiff_t row_pitch,
    std::int32_t   width,
    std::int32_t   height,
    int            color_system)
{
    if (!data || width <= 0 || height <= 0) {
        return;
    }

    const MSX1PQ::QuantColor* table = get_basic_palette(color_system);

    for (std::int32_t y = 0; y < height; ++y) {
        PixelT* row = data + y * row_pitch;

        for (std::int32_t bx = 0; bx * 8 < width; ++bx) {
            std::int32_t x_start = bx * 8;
            std::int32_t x_end   = x_start + 8;
            if (x_end > width) {
                x_end = width;
            }
            int block_w = static_cast<int>(x_end - x_start);
            if (block_w <= 0) continue;

            int counts[BASIC_COLORS] = {0};
            int idx_list[8];

            // 1) ブロック内の basic15 インデックスを取得＆カウント
            for (int i = 0; i < block_w; ++i) {
                PixelT& p = row[x_start + i];

                int idx = find_basic_index_from_rgb(
                    p.red, p.green, p.blue, color_system);

                if (idx < 0) idx = 0;
                if (idx >= BASIC_COLORS) idx = BASIC_COLORS - 1;

                idx_list[i] = idx;
                counts[idx]++;
            }

            // 2) 出現数 Top2
            int top1 = -1;
            int top2 = -1;
            for (int c = 0; c < BASIC_COLORS; ++c) {
                int cnt = counts[c];
                if (cnt <= 0) continue;

                if (top1 < 0 || cnt > counts[top1]) {
                    top2 = top1;
                    top1 = c;
                } else if (top2 < 0 || cnt > counts[top2]) {
                    top2 = c;
                }
            }
            if (top1 < 0) continue;
            if (top2 < 0) top2 = top1;

            // 3) Top2 以外は “どちらに近いか” で寄せる
            for (int i = 0; i < block_w; ++i) {
                int idx = idx_list[i];
                int new_idx = idx;

                if (idx != top1 && idx != top2) {
                    const MSX1PQ::QuantColor& src = table[idx];
                    const MSX1PQ::QuantColor& c1  = table[top1];
                    const MSX1PQ::QuantColor& c2  = table[top2];

                    long dr1 = static_cast<long>(src.r) - static_cast<long>(c1.r);
                    long dg1 = static_cast<long>(src.g) - static_cast<long>(c1.g);
                    long db1 = static_cast<long>(src.b) - static_cast<long>(c1.b);
                    long d1  = dr1*dr1 + dg1*dg1 + db1*db1;

                    long dr2 = static_cast<long>(src.r) - static_cast<long>(c2.r);
                    long dg2 = static_cast<long>(src.g) - static_cast<long>(c2.g);
                    long db2 = static_cast<long>(src.b) - static_cast<long>(c2.b);
                    long d2  = dr2*dr2 + dg2*dg2 + db2*db2;

                    new_idx = (d1 <= d2) ? top1 : top2;
                }

                const MSX1PQ::QuantColor& qc = table[new_idx];
                PixelT& p = row[x_start + i];
                p.red   = qc.r;
                p.green = qc.g;
                p.blue  = qc.b;
            }
        }
    }
}

template<typename PixelT>
void apply_8dot2col_fast1(
    PixelT* data,
    std::ptrdiff_t row_pitch,
    std::int32_t   width,
    std::int32_t   height,
    int            /*color_system*/)
{
    if (!data || width <= 0 || height <= 0) {
        return;
    }

    for (std::int32_t y = 0; y < height; ++y) {
        PixelT* row = data + y * row_pitch;

        for (std::int32_t bx = 0; bx * 8 < width; ++bx) {
            std::int32_t x_start = bx * 8;
            std::int32_t x_end   = x_start + 8;
            if (x_end > width) {
                x_end = width;
            }
            int block_w = static_cast<int>(x_end - x_start);
            if (block_w <= 0) continue;

            struct ColorCount {
                std::uint8_t r, g, b;
                int          count;
            };

            ColorCount uniques[8];
            int        num_unique = 0;

            // 1) ブロック内のユニーク色を集計（最大 8 種類）
            for (int i = 0; i < block_w; ++i) {
                PixelT& p = row[x_start + i];

                int j;
                for (j = 0; j < num_unique; ++j) {
                    if (uniques[j].r == p.red &&
                        uniques[j].g == p.green &&
                        uniques[j].b == p.blue) {
                        uniques[j].count++;
                        break;
                    }
                }
                if (j == num_unique && num_unique < 8) {
                    uniques[num_unique].r = p.red;
                    uniques[num_unique].g = p.green;
                    uniques[num_unique].b = p.blue;
                    uniques[num_unique].count = 1;
                    ++num_unique;
                }
            }

            if (num_unique <= 1) {
                // もともと 0～1 色なら 2色制限の必要なし
                continue;
            }

            // 2) 出現数 Top2 を探す
            int top1 = 0;
            int top2 = 1;
            if (uniques[top2].count > uniques[top1].count) {
                int tmp = top1; top1 = top2; top2 = tmp;
            }
            for (int i = 2; i < num_unique; ++i) {
                int c = uniques[i].count;
                if (c > uniques[top1].count) {
                    top2 = top1;
                    top1 = i;
                } else if (c > uniques[top2].count) {
                    top2 = i;
                }
            }

            const ColorCount& c1 = uniques[top1];
            const ColorCount& c2 = uniques[top2];

            // 3) Top2 以外の色は “どちらに近いか” で寄せる
            for (int i = 0; i < block_w; ++i) {
                PixelT& p = row[x_start + i];

                // すでに top1 / top2 ならそのまま
                if ((p.red == c1.r && p.green == c1.g && p.blue == c1.b) ||
                    (p.red == c2.r && p.green == c2.g && p.blue == c2.b)) {
                    continue;
                }

                long dr1 = static_cast<long>(p.red)   - static_cast<long>(c1.r);
                long dg1 = static_cast<long>(p.green) - static_cast<long>(c1.g);
                long db1 = static_cast<long>(p.blue)  - static_cast<long>(c1.b);
                long d1  = dr1*dr1 + dg1*dg1 + db1*db1;

                long dr2 = static_cast<long>(p.red)   - static_cast<long>(c2.r);
                long dg2 = static_cast<long>(p.green) - static_cast<long>(c2.g);
                long db2 = static_cast<long>(p.blue)  - static_cast<long>(c2.b);
                long d2  = dr2*dr2 + dg2*dg2 + db2*db2;

                if (d1 <= d2) {
                    p.red   = c1.r;
                    p.green = c1.g;
                    p.blue  = c1.b;
                } else {
                    p.red   = c2.r;
                    p.green = c2.g;
                    p.blue  = c2.b;
                }
            }
        }
    }
}

template<typename PixelT>
void apply_8dot2col_best1(
    PixelT* data,
    std::ptrdiff_t row_pitch,
    std::int32_t   width,
    std::int32_t   height,
    int            color_system)
{
    if (!data || width <= 0 || height <= 0) {
        return;
    }

    const MSX1PQ::QuantColor* table = get_basic_palette(color_system);

    // 15×15 距離テーブル（セル内共通）
    long dist2[BASIC_COLORS][BASIC_COLORS];
    for (int i = 0; i < BASIC_COLORS; ++i) {
        const MSX1PQ::QuantColor& ci = table[i];
        for (int j = 0; j < BASIC_COLORS; ++j) {
            const MSX1PQ::QuantColor& cj = table[j];
            long dr = static_cast<long>(ci.r) - static_cast<long>(cj.r);
            long dg = static_cast<long>(ci.g) - static_cast<long>(cj.g);
            long db = static_cast<long>(ci.b) - static_cast<long>(cj.b);
            dist2[i][j] = dr*dr + dg*dg + db*db;
        }
    }

    const std::int32_t num_blocks_x = (width + 7) / 8;

    for (std::int32_t y0 = 0; y0 < height; y0 += ATTRCELL_HEIGHT) {
        std::int32_t cell_h = ATTRCELL_HEIGHT;
        if (y0 + cell_h > height) {
            cell_h = height - y0;
        }
        if (cell_h <= 0) break;

        for (std::int32_t bx = 0; bx < num_blocks_x; ++bx) {
            std::int32_t x_start = bx * 8;
            if (x_start >= width) break;
            std::int32_t x_end   = x_start + 8;
            if (x_end > width) {
                x_end = width;
            }
            int block_w = static_cast<int>(x_end - x_start);
            if (block_w <= 0) continue;

            // --- (1) このセル＆この 8dot 縦帯の basic15 ヒストグラム ---
            int cell_counts[BASIC_COLORS] = {0};

            for (std::int32_t yy = 0; yy < cell_h; ++yy) {
                PixelT* row = data + (y0 + yy) * row_pitch;
                for (int i = 0; i < block_w; ++i) {
                    PixelT& p = row[x_start + i];

                    int idx = find_basic_index_from_rgb(
                        p.red, p.green, p.blue, color_system);
                    if (idx < 0) idx = 0;
                    if (idx >= BASIC_COLORS) idx = BASIC_COLORS - 1;

                    cell_counts[idx]++;
                }
            }

            // --- (2) セル内の各行 8×1 ブロックごとに 2色ペアを選ぶ ---
            for (std::int32_t yy = 0; yy < cell_h; ++yy) {
                std::int32_t y = y0 + yy;
                PixelT* row = data + y * row_pitch;

                int block_counts[BASIC_COLORS] = {0};
                int idx_list[8];

                for (int i = 0; i < block_w; ++i) {
                    PixelT& p = row[x_start + i];

                    int idx = find_basic_index_from_rgb(
                        p.red, p.green, p.blue, color_system);
                    if (idx < 0) idx = 0;
                    if (idx >= BASIC_COLORS) idx = BASIC_COLORS - 1;

                    idx_list[i] = idx;
                    block_counts[idx]++;
                }

                int unique_indices[8];
                int num_unique = 0;
                for (int k = 0; k < BASIC_COLORS && num_unique < 8; ++k) {
                    if (block_counts[k] > 0) {
                        unique_indices[num_unique++] = k;
                    }
                }
                if (num_unique <= 1) {
                    continue;
                }

                double best_score = 0.0;
                bool   first      = true;
                int    best_a     = unique_indices[0];
                int    best_b     = unique_indices[1];

                for (int ua = 0; ua < num_unique; ++ua) {
                    for (int ub = ua + 1; ub < num_unique; ++ub) {

                        int a = unique_indices[ua];
                        int b = unique_indices[ub];

                        long err_block = 0;
                        for (int k = 0; k < BASIC_COLORS; ++k) {
                            int cnt = block_counts[k];
                            if (!cnt) continue;

                            long dA = dist2[k][a];
                            long dB = dist2[k][b];
                            long d  = (dA < dB) ? dA : dB;

                            err_block += static_cast<long>(cnt) * d;
                        }

                        long err_cell = 0;
                        for (int k = 0; k < BASIC_COLORS; ++k) {
                            int cnt = cell_counts[k];
                            if (!cnt) continue;

                            long dA = dist2[k][a];
                            long dB = dist2[k][b];
                            long d  = (dA < dB) ? dA : dB;

                            err_cell += static_cast<long>(cnt) * d;
                        }

                        double score =
                            static_cast<double>(err_block) +
                            ATTR_LAMBDA * static_cast<double>(err_cell);

                        if (first || score < best_score) {
                            first      = false;
                            best_score = score;
                            best_a     = a;
                            best_b     = b;
                        }
                    }
                }

                for (int i = 0; i < block_w; ++i) {
                    int src_idx = idx_list[i];

                    long dA = dist2[src_idx][best_a];
                    long dB = dist2[src_idx][best_b];
                    int  new_idx = (dA <= dB) ? best_a : best_b;

                    const MSX1PQ::QuantColor& qc = table[new_idx];
                    PixelT& p = row[x_start + i];
                    p.red   = qc.r;
                    p.green = qc.g;
                    p.blue  = qc.b;
                }
            }
        }
    }
}

template<typename PixelT>
void apply_8dot2col_attr_best(
    PixelT* data,
    std::ptrdiff_t row_pitch,
    std::int32_t   width,
    std::int32_t   height,
    int            color_system)
{
    if (!data || width <= 0 || height <= 0) {
        return;
    }

    const MSX1PQ::QuantColor* table = get_basic_palette(color_system);

    long dist2[BASIC_COLORS][BASIC_COLORS];
    for (int i = 0; i < BASIC_COLORS; ++i) {
        const MSX1PQ::QuantColor& ci = table[i];
        for (int j = 0; j < BASIC_COLORS; ++j) {
            const MSX1PQ::QuantColor& cj = table[j];
            long dr = static_cast<long>(ci.r) - static_cast<long>(cj.r);
            long dg = static_cast<long>(ci.g) - static_cast<long>(cj.g);
            long db = static_cast<long>(ci.b) - static_cast<long>(cj.b);
            dist2[i][j] = dr*dr + dg*dg + db*db;
        }
    }

    const std::int32_t num_blocks_x = (width + 7) / 8;

    for (std::int32_t y0 = 0; y0 < height; y0 += ATTRCELL_HEIGHT) {

        std::int32_t cell_h = ATTRCELL_HEIGHT;
        if (y0 + cell_h > height) {
            cell_h = height - y0;
        }
        if (cell_h <= 0) break;

        for (std::int32_t yy = 0; yy < cell_h; ++yy) {

            std::int32_t y = y0 + yy;
            PixelT* row = data + y * row_pitch;

            int prevA = -1;
            int prevB = -1;

            for (std::int32_t bx = 0; bx < num_blocks_x; ++bx) {

                std::int32_t x_start = bx * 8;
                if (x_start >= width) break;
                std::int32_t x_end   = x_start + 8;
                if (x_end > width) {
                    x_end = width;
                }
                int block_w = static_cast<int>(x_end - x_start);
                if (block_w <= 0) continue;

                int block_counts[BASIC_COLORS] = {0};
                int idx_list[8];

                for (int i = 0; i < block_w; ++i) {
                    PixelT& p = row[x_start + i];

                    int idx = find_basic_index_from_rgb(
                        p.red, p.green, p.blue, color_system);
                    if (idx < 0) idx = 0;
                    if (idx >= BASIC_COLORS) idx = BASIC_COLORS - 1;

                    idx_list[i] = idx;
                    block_counts[idx]++;
                }

                int unique_indices[8];
                int num_unique = 0;
                for (int k = 0; k < BASIC_COLORS && num_unique < 8; ++k) {
                    if (block_counts[k] > 0) {
                        unique_indices[num_unique++] = k;
                    }
                }
                if (num_unique <= 1) {
                    continue;
                }

                int cell_counts[BASIC_COLORS] = {0};
                for (std::int32_t yyc = 0; yyc < cell_h; ++yyc) {
                    PixelT* rowc = data + (y0 + yyc) * row_pitch;
                    for (int i = 0; i < block_w; ++i) {
                        PixelT& p = rowc[x_start + i];

                        int idx = find_basic_index_from_rgb(
                            p.red, p.green, p.blue, color_system);
                        if (idx < 0) idx = 0;
                        if (idx >= BASIC_COLORS) idx = BASIC_COLORS - 1;

                        cell_counts[idx]++;
                    }
                }

                double best_score = 0.0;
                bool   first      = true;
                int    best_a     = unique_indices[0];
                int    best_b     = unique_indices[1];

                for (int ua = 0; ua < num_unique; ++ua) {
                    for (int ub = ua + 1; ub < num_unique; ++ub) {

                        int a = unique_indices[ua];
                        int b = unique_indices[ub];

                        long err_block = 0;
                        for (int k = 0; k < BASIC_COLORS; ++k) {
                            int cnt = block_counts[k];
                            if (!cnt) continue;

                            long dA = dist2[k][a];
                            long dB = dist2[k][b];
                            long d  = (dA < dB) ? dA : dB;

                            err_block += static_cast<long>(cnt) * d;
                        }

                        long err_cell = 0;
                        for (int k = 0; k < BASIC_COLORS; ++k) {
                            int cnt = cell_counts[k];
                            if (!cnt) continue;

                            long dA = dist2[k][a];
                            long dB = dist2[k][b];
                            long d  = (dA < dB) ? dA : dB;

                            err_cell += static_cast<long>(cnt) * d;
                        }

                        int tc_h = transition_cost_pair(prevA, prevB, a, b);

                        double score =
                            static_cast<double>(err_block) +
                            ATTR_LAMBDA       * static_cast<double>(err_cell) +
                            TRANSITION_LAMBDA * static_cast<double>(tc_h);

                        if (first || score < best_score) {
                            first      = false;
                            best_score = score;
                            best_a     = a;
                            best_b     = b;
                        }
                    }
                }

                for (int i = 0; i < block_w; ++i) {
                    int src_idx = idx_list[i];

                    long dA = dist2[src_idx][best_a];
                    long dB = dist2[src_idx][best_b];
                    int  new_idx = (dA <= dB) ? best_a : best_b;

                    const MSX1PQ::QuantColor& qc = table[new_idx];
                    PixelT& p = row[x_start + i];
                    p.red   = qc.r;
                    p.green = qc.g;
                    p.blue  = qc.b;
                }

                prevA = best_a;
                prevB = best_b;
            }
        }
    }
}

template<typename PixelT>
void apply_8dot2col_attr_best_penalty(
    PixelT* data,
    std::ptrdiff_t row_pitch,
    std::int32_t   width,
    std::int32_t   height,
    int            color_system)
{
    if (!data || width <= 0 || height <= 0) {
        return;
    }

    const MSX1PQ::QuantColor* table = get_basic_palette(color_system);

    long dist2[BASIC_COLORS][BASIC_COLORS];
    for (int i = 0; i < BASIC_COLORS; ++i) {
        const MSX1PQ::QuantColor& ci = table[i];
        for (int j = 0; j < BASIC_COLORS; ++j) {
            const MSX1PQ::QuantColor& cj = table[j];
            long dr = static_cast<long>(ci.r) - static_cast<long>(cj.r);
            long dg = static_cast<long>(ci.g) - static_cast<long>(cj.g);
            long db = static_cast<long>(ci.b) - static_cast<long>(cj.b);
            dist2[i][j] = dr*dr + dg*dg + db*db;
        }
    }

    const std::int32_t num_blocks_x = (width + 7) / 8;

    for (std::int32_t y0 = 0; y0 < height; y0 += ATTRCELL_HEIGHT) {

        std::int32_t cell_h = ATTRCELL_HEIGHT;
        if (y0 + cell_h > height) {
            cell_h = height - y0;
        }
        if (cell_h <= 0) break;

        for (std::int32_t yy = 0; yy < cell_h; ++yy) {

            std::int32_t y = y0 + yy;
            PixelT* row = data + y * row_pitch;

            int prevA = -1;
            int prevB = -1;

            for (std::int32_t bx = 0; bx < num_blocks_x; ++bx) {

                std::int32_t x_start = bx * 8;
                if (x_start >= width) break;
                std::int32_t x_end   = x_start + 8;
                if (x_end > width) {
                    x_end = width;
                }
                int block_w = static_cast<int>(x_end - x_start);
                if (block_w <= 0) continue;

                int block_counts[BASIC_COLORS] = {0};
                int idx_list[8];

                for (int i = 0; i < block_w; ++i) {
                    PixelT& p = row[x_start + i];

                    int idx = find_basic_index_from_rgb(
                        p.red, p.green, p.blue, color_system);
                    if (idx < 0) idx = 0;
                    if (idx >= BASIC_COLORS) idx = BASIC_COLORS - 1;

                    idx_list[i] = idx;
                    block_counts[idx]++;
                }

                int unique_indices[8];
                int num_unique = 0;
                for (int k = 0; k < BASIC_COLORS && num_unique < 8; ++k) {
                    if (block_counts[k] > 0) {
                        unique_indices[num_unique++] = k;
                    }
                }
                if (num_unique <= 1) {
                    continue;
                }

                int cell_counts[BASIC_COLORS] = {0};
                for (std::int32_t yyc = 0; yyc < cell_h; ++yyc) {
                    PixelT* rowc = data + (y0 + yyc) * row_pitch;
                    for (int i = 0; i < block_w; ++i) {
                        PixelT& p = rowc[x_start + i];

                        int idx = find_basic_index_from_rgb(
                            p.red, p.green, p.blue, color_system);
                        if (idx < 0) idx = 0;
                        if (idx >= BASIC_COLORS) idx = BASIC_COLORS - 1;

                        cell_counts[idx]++;
                    }
                }

                double best_score = 0.0;
                bool   first      = true;
                int    best_a     = unique_indices[0];
                int    best_b     = unique_indices[1];

                for (int ua = 0; ua < num_unique; ++ua) {
                    for (int ub = ua + 1; ub < num_unique; ++ub) {

                        int a = unique_indices[ua];
                        int b = unique_indices[ub];

                        long err_block = 0;
                        for (int k = 0; k < BASIC_COLORS; ++k) {
                            int cnt = block_counts[k];
                            if (!cnt) continue;

                            long dA = dist2[k][a];
                            long dB = dist2[k][b];
                            long d  = (dA < dB) ? dA : dB;

                            err_block += static_cast<long>(cnt) * d;
                        }

                        long err_cell = 0;
                        for (int k = 0; k < BASIC_COLORS; ++k) {
                            int cnt = cell_counts[k];
                            if (!cnt) continue;

                            long dA = dist2[k][a];
                            long dB = dist2[k][b];
                            long d  = (dA < dB) ? dA : dB;

                            err_cell += static_cast<long>(cnt) * d;
                        }

                        int tc_h = transition_cost_pair(prevA, prevB, a, b);

                        double score =
                            static_cast<double>(err_block) +
                            ATTR_LAMBDA       * static_cast<double>(err_cell) +
                            TRANSITION_LAMBDA * static_cast<double>(tc_h);

                        if (first || score < best_score) {
                            first      = false;
                            best_score = score;
                            best_a     = a;
                            best_b     = b;
                        }
                    }
                }

                for (int i = 0; i < block_w; ++i) {
                    int src_idx = idx_list[i];

                    long dA = dist2[src_idx][best_a];
                    long dB = dist2[src_idx][best_b];
                    int  new_idx = (dA <= dB) ? best_a : best_b;

                    const MSX1PQ::QuantColor& qc = table[new_idx];
                    PixelT& p = row[x_start + i];
                    p.red   = qc.r;
                    p.green = qc.g;
                    p.blue  = qc.b;
                }

                prevA = best_a;
                prevB = best_b;
            }
        }
    }
}

} // namespace MSX1PQCore

