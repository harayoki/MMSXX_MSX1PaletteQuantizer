#!/usr/bin/env python3
"""
MSX1 縦スクロール ROM ビルダー。

縦長の PNG画像 を １枚（今後複数枚に機能拡張予定）受け取り 以下の手順で ROM を生成する:

1. 入力 PNG を左端を基準で横256pxにトリミング。足りない場合は右側を背景色でパディング。
2. 縦は 8px 単位になるように下側へ背景色でパディング。
3. `msx1pq_cli`（PATH もしくは引数で指定）を用いて MSX1 ルール準拠の PNG を生成。
    ※ 美しくするための前処理や加工は行われず機械的に変換する。
    質の高い画像にしたい場合はあらかじめmsx1pq_cliや他のツールで対応しておく。
4. パターンジェネレータとカラーテーブルを隙間なく連結し、バンク境界をまたいで
   ASCII16 MegaROM のデータバンクに格納。
5. プログラム領域の直後に各画像 6 バイトのヘッダ（開始バンク、行数、色データ開始
   バンクとアドレス）を 3 バイトずつの情報として並べ、最後に 4 バイトの終端情報を
   付与。
6. ビューアーとともにROMデータとして出力。

実装中
・ヘッダテーブルの行数とカラーデータ開始情報を読み取り1画面分を描画

NEXT
RAMからVRAMコピーなどを用いて（実際のアルゴリズムは未定）速さを考慮しつつ
1行単位でスクロールできるように

NEXT
・複数枚画像をROMに埋め込めるように
・複数枚画像をはグループ化可能 グループごとに縦に連結した1枚の画像として扱う
・スペースで次の画像に SHIFT＋スペースで前の画像に
・上下でスクロール
・オートスクロールモード搭載 最後の行まで達したら次の画像の一番上に
・簡易BGMルーチン搭載
・デフォルトの挙動はコマンドラインOPTION指定できまる
・ESCを押すと管理画面（SCRENN0）に切り替わり設定を替えられる。彩度ESCで復帰。
・再生画像番号指定、オートスクロール＆その速度指定、BGM ONOFFなど

※ 管理画面の機能はライブラリ化して他のツール・ゲームでも使えるようにする
項目がテキストで並び 上下で選択項目切り替え 左右で項目設定切り替え など



"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, Sequence, List

from mmsxxasmhelper.core import (
    ADD,
    Block,
    CALL,
    CP,
    DEC,
    Func,
    INC,
    JP,
    JR,
    JR_C,
    JR_NC,
    JR_NZ,
    JR_Z,
    JR_n8,
    DJNZ,
    LD,
    OR,
    POP,
    PUSH,
    XOR,
    DB,
    DW,
    SUB,
    NOP,
    OUT,
    OUT_A,
    OUT_C,
    OUTI,
    RET,
    RET_NC,
    BIT,
    HALT,
    unique_label,
    define_created_funcs,
)
from mmsxxasmhelper.msxutils import (
    CHGCLR,
    CHGMOD,
    FORCLR,
    BAKCLR,
    BDRCLR,
    LDIRVM,
    enaslt_macro,
    place_msx_rom_header_macro,
    restore_stack_pointer_macro,
    set_msx2_palette_default_macro,
    store_stack_pointer_macro,
    init_stack_pointer_macro,
    ldirvm_macro,
    build_update_input_func,
    INPUT_KEY_BIT,
    build_beep_control_utils,
    build_set_vram_write_func,
    build_scroll_name_table_func,
)
from mmsxxasmhelper.utils import (
    pad_bytes,
    ldir_macro,
    loop_infinite_macro,
    debug_trap,
    set_debug,
    print_bytes,
    debug_print_labels,
    MemAddrAllocator,
)

from PIL import Image
from simple_sc2_converter.converter import BASIC_COLORS_MSX1, parse_color

PAGE_SIZE = 0x4000
ROM_BASE = 0x4000

ASCII16_PAGE2_REG = 0x7000
DATA_BANK_ADDR = 0x8000

# VDP / SCREEN2 VRAM レイアウト
PATTERN_BASE = 0x0000
NAME_BASE = 0x1800
COLOR_BASE = 0x2000

# MSX RAM での作業領域
WORK_RAM_BASE = 0xC000
# PATTERN_RAM_BASE = WORK_RAM_BASE
PATTERN_RAM_SIZE = 0x1800
# COLOR_RAM_BASE = WORK_RAM_BASE
COLOR_RAM_SIZE = 0x1800
TARGET_WIDTH = 256
SCREEN_TILE_ROWS = 24
IMAGE_HEADER_ENTRY_SIZE = 6
IMAGE_HEADER_END_SIZE = 4
QUANTIZED_SUFFIX = "_quantized"

# 状況を保存するメモリアドレス
mem_addr_allocator = MemAddrAllocator(WORK_RAM_BASE)
madd = mem_addr_allocator.add
class ADDR:
    CURRENT_IMAGE_ADDR = (
        madd("CURRENT_IMAGE_ADDR", 1, description="画像番号"))
    CURRENT_IMAGE_START_BANK_ADDR = (
        madd("CURRENT_IMAGE_START_BANK_ADDR", 1, description="画像データを格納しているバンク番号"))
    CURRENT_IMAGE_ROW_COUNT_ADDR = (
        madd("CURRENT_IMAGE_ROW_COUNT_ADDR", 2, description="画像の行数（タイル行数）を保存"))
    CURRENT_IMAGE_COLOR_BANK_ADDR = (
        madd("CURRENT_IMAGE_COLOR_BANK_ADDR", 1,description="カラーパターンが置かれているバンク番号"))
    CURRENT_IMAGE_COLOR_ADDRESS_ADDR = (
        madd("CURRENT_IMAGE_COLOR_ADDRESS_ADDR", 2, description="カラーパターンの先頭アドレス"))
    CURRENT_SCROLL_ROW = (
        madd("CURRENT_SCROLL_ROW", 2, description="スクロール位置"))
    INPUT_HOLD = madd("INPUT_HOLD", 1, description="現在押されている全入力")
    INPUT_TRG = madd("INPUT_TRG", 1, description="今回新しく押された入力")
    BEEP_CNT = madd("BEEP_CNT", 1, description="BEEPカウンタ")
    BEEP_ACTIVE = madd("BEEP_ACTIVE", 1 , description="BEEP状態")

# mem_addr_allocator.debug_print()


@dataclass
class ImageEntry:
    start_bank: int
    tile_rows: int
    color_bank: int
    color_address: int


@dataclass
class ImageData:
    pattern: bytes
    color: bytes
    tile_rows: int


def int_from_str(value: str) -> int:
    return int(value, 0)


@contextmanager
def open_workdir(path: Path | None):
    if path is None:
        with TemporaryDirectory() as tmp:
            yield Path(tmp)
    else:
        path.mkdir(parents=True, exist_ok=True)
        yield path


def prepare_image(image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    """Crop/pad the input to 256px width and multiple-of-8 height."""

    img = image.convert("RGB")
    width, height = img.size

    cropped_width = min(width, TARGET_WIDTH)
    cropped = img.crop((0, 0, cropped_width, height))

    new_height = ((height + 7) // 8) * 8
    canvas = Image.new("RGB", (TARGET_WIDTH, new_height), background)
    canvas.paste(cropped, (0, 0))
    return canvas


def find_msx1pq_cli(path: Path | None) -> Path:
    if path is not None:
        if path.is_file():
            return path
        raise SystemExit(f"msx1pq_cli not found: {path}")

    resolved = shutil.which("msx1pq_cli")
    if not resolved:
        raise SystemExit("msx1pq_cli not found in PATH. Provide --msx1pq-cli.")
    return Path(resolved)


def quantized_output_path(prepared_png: Path, output_dir: Path) -> Path:
    return output_dir / f"{prepared_png.stem}{QUANTIZED_SUFFIX}{prepared_png.suffix}"


def is_cached_image_valid(
    cached_image: Path, expected_size: tuple[int, int], newest_source_mtime: float
) -> bool:
    if not cached_image.is_file():
        return False

    try:
        if cached_image.stat().st_mtime <= newest_source_mtime:
            return False
        with Image.open(cached_image) as img:
            return img.size == expected_size
    except OSError:
        return False


def load_quantized_image(
    index: int, path: Path, action: str, log_lines: list[str]
) -> ImageData:
    with Image.open(path) as quantized_image:
        width, height = quantized_image.size
        log_and_store(
            f"* quantized image #{index} {path} {action} ({width}x{height}px)",
            log_lines,
        )
        return build_image_data_from_image(quantized_image)


def run_msx1pq_cli(cli: Path, prepared_png: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(cli),
        "-i",
        str(prepared_png),
        "-o",
        str(output_dir),
        "--no-preprocess",
        "--out-suffix",
        QUANTIZED_SUFFIX,
        "--force",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            "msx1pq_cli failed:\n"
            f"command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    out_path = quantized_output_path(prepared_png, output_dir)
    if not out_path.is_file():
        raise SystemExit(f"Expected output not found: {out_path}")
    return out_path


def nearest_palette_index(rgb: Sequence[int]) -> int:
    """Return the closest MSX1 palette index (0-based) for an RGB triple."""
    r, g, b = rgb
    best_idx = 0
    best_dist = float("inf")
    for idx, (pr, pg, pb) in enumerate(BASIC_COLORS_MSX1):
        dist = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if dist < best_dist:
            best_dist = dist
            best_idx = idx

    return best_idx


def palette_distance(idx_a: int, idx_b: int) -> int:
    ra, ga, ba = BASIC_COLORS_MSX1[idx_a]
    rb, gb, bb = BASIC_COLORS_MSX1[idx_b]
    return (ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2


def restrict_two_colors(indices: list[int]) -> list[int]:
    """Ensure a block uses at most two colors.

    `msx1pq_cli` で 8dot 2 色ルールが守られている前提
    """

    unique = set(indices)
    if len(unique) <= 2:
        return indices

    raise ValueError(f"{unique} colors in 8 dots.")

    # 念のため 3 色以上のブロックを 2 色に丸める安全弁を入れておく？
    # counts = Counter(indices)
    # allowed = [color for color, _ in counts.most_common(2)]
    #
    # remapped: list[int] = []
    # for idx in indices:
    #     if idx in allowed:
    #         remapped.append(idx)
    #         continue
    #     remapped.append(min(allowed, key=lambda candidate: palette_distance(idx, candidate)))
    #
    # return remapped


def build_image_data_from_image(image: Image.Image) -> ImageData:
    """Convert a quantized image into pattern/color bytes."""

    width, height = image.size
    if width != TARGET_WIDTH:
        raise ValueError(f"Width must be {TARGET_WIDTH}, got {width}")
    if height % 8 > 0:
        raise ValueError(f"Height must be 8x size, got {height}")

    palette_indices = \
        [nearest_palette_index(rgb) for rgb in image.convert("RGB").getdata()]  # 左上から右へ走査
    patterns: list[bytes] = []
    colors: list[bytes] = []

    for yy in range(int(height / 8)):
        pattern_line = bytearray()  # パターンジェネレータ
        color_line = bytearray()  # カラーテーブル
        for xx in range(int(width / 8)):
            for y in range(8):
                base = (yy * 8 + y) * width + xx * 8
                block = palette_indices[base : base + 8]
                block = restrict_two_colors(block)
                color_min = min(block)
                color_max = max(block)
                fg_color = color_max + 1  # MSX palette code (1-15)
                bg_color = color_min + 1

                pattern_byte = 0
                for idx in block:
                    pattern_byte <<= 1
                    if idx == color_max:
                        pattern_byte |= 0x01
                pattern_line.append(pattern_byte & 0xFF)
                dat = (fg_color & 0x0F) << 4 | (bg_color & 0x0F)
                color_line.append(dat)
        patterns.append(bytes(pattern_line))
        colors.append(bytes(color_line))

    tile_rows = height // 8
    return ImageData(pattern=b"".join(patterns), color=b"".join(colors), tile_rows=tile_rows)


def build_reset_name_table_func() -> Func:
    def reset_name_table_call(block: Block) -> None:
        # VRAMアドレスセット (NAME_BASE = 0x1800)
        # 0x1800 を書き込みモードでセット
        LD.A_n8(block, 0x00)     # 下位8bit
        OUT(block, 0x99)
        LD.A_n8(block, 0x18 | 0x40) # 上位8bit + Write Mode(0x40)
        OUT(block, 0x99)

        # 0~255 の出力を3回繰り返す
        LD.D_n8(block, 3)        # 3ブロック分
        LD.C_n8(block, 0x98)     # VDPデータポート

        OUTER_LOOP = unique_label()
        INNER_LOOP = unique_label()

        block.label(OUTER_LOOP)
        LD.A_n8(block, 0)        # 0から開始

        block.label(INNER_LOOP)
        OUT_C.A(block)          # VDPへ A を出力 (OUT (C), A)
        # ※名前テーブルはデータが疎(1byte/1char)なので
        # ウェイト(JR $+2)がなくてもMSX1のVDPなら追いつくことが多いですが、
        # 念のため入れるならここに NOP や INC A を置きます。
        NOP(block)
        INC.A(block)             # 次のキャラクタ番号
        JR_NZ(block, INNER_LOOP) # 255を超えて0になるまでループ

        DEC.D(block)             # 残りブロック数を減らす
        JR_NZ(block, OUTER_LOOP)

    return Func("init_name_table_call", reset_name_table_call)


RESET_NAME_TABLE_FUNC = build_reset_name_table_func()




def build_scroll_vram_xfer_func() -> Func:
    def scroll_vram_xfer(block: Block) -> None:
        # --- 入力規定 ---
        # HL: 計算済みのROM開始アドレス (0x8000 - 0xBFFF)
        # E : 開始バンク番号 (パターンなら START_BANK, カラーなら COLOR_BANK)
        # D : 転送する行数 (1〜24)
        # BC: (内部で使用) CはVDPポート, Bは256byteループ用

        # ※ 事前に VRAM アドレスセットは完了していること

        block.label("VRAM_PAGE_LOOP")
        PUSH.DE(block)  # 行数(D) と バンク番号(E) を保存

        # 現在のバンクをメガROMにセット (Eレジスタの値を使用)
        LD.A_E(block)
        LD.mn16_A(block, ASCII16_PAGE2_REG)

        LD.B_n8(block, 0)  # 1ページ(256byte)転送用
        LD.C_n8(block, 0x98)  # VDPデータポート

        # --- 1ページ(256byte) 転送ループ (展開版) ---
        block.label("VRAM_BYTE_LOOP")
        for _ in range(16):
            # 1バイト転送 (18T)
            OUTI(block)  # (HL)->(C), HL++, B--
            # SCREEN 2用ウェイト (12T)　3マイクロ秒強稼ぐ
            JR_n8(block, 0)
        JR_NZ(block, "VRAM_BYTE_LOOP")

        # --- バンク境界チェック ---
        LD.A_H(block)
        CP.n8(block, 0xC0)  # HLが0xC000（バンク端）に達したか？
        JR_C(block, "NOT_NEXT_BANK")

        # --- バンク跨ぎ発生時の処理 ---
        POP.DE(block)  # 一時復帰してバンク番号(E)を取り出す
        INC.E(block)  # バンク番号を次へ（関数を呼ぶ側には影響しない）
        PUSH.DE(block)  # 更新したバンク番号を再度保存
        LD.H_n8(block, 0x80)  # アドレスを 0x8000 に戻す
        # 次のループの先頭で LD A,E / LD (0x7000),A が実行される

        block.label("NOT_NEXT_BANK")
        POP.DE(block)  # 行数(D) と バンク(E) を復帰
        DEC.D(block)  # 行数カウンタを減らす
        JR_NZ(block, "VRAM_PAGE_LOOP")

    """
    呼び出し方のイメージ
    
    ; --- パターン転送の場合 (VRAM 0x0000) ---
    LD   HL, 0x0000         ; 書き込み先VRAMアドレス
    CALL SET_VRAM_WRITE     ; VDPへのアドレスセットルーチン
    ; --- ここでHLをROMアドレスに、Eをバンクに、Dを行数にセット ---
    LD   HL, (計算したPGのROMアドレス)
    LD   A, (CURRENT_IMAGE_START_BANK_ADDR)
    LD   E, A
    LD   D, 24              ; 行数（前述の通りDレジスタを使用）
    CALL scroll_vram_xfer
    
    ; --- カラー転送の場合 (VRAM 0x2000) ---
    LD   HL, 0x2000         ; 書き込み先VRAMアドレス
    CALL SET_VRAM_WRITE
    ; --- ROMアドレス、バンク、行数をセット ---
    LD   HL, (計算したCTのROMアドレス)
    LD   A, (CURRENT_IMAGE_COLOR_BANK_ADDR)
    LD   E, A
    LD   D, 24
    CALL scroll_vram_xfer
    """

    return Func("scroll_vram_xfer", scroll_vram_xfer)


SET_VRAM_WRITE_FUNC = build_set_vram_write_func()
SCROLL_NAME_TABLE_FUNC = build_scroll_name_table_func(SET_VRAM_WRITE_FUNC)
SCROLL_VRAM_XFER_FUNC = build_scroll_vram_xfer_func()


# def build_update_image_display_func(image_entries_count: int) -> Func:
#     def update_image_display(block: Block) -> None:
#         # 入力: A = 切り替えたい画像番号
#
#         # --- 安全装置: 範囲外なら RET ---
#         CP.n8(block, image_entries_count)
#         RET_NC(block)  # A >= image_entries_count なら終了
#
#         # 1. 画像番号の保存
#         LD.mn16_A(block, ADDR.CURRENT_IMAGE_ADDR)
#
#         # 2. ヘッダテーブルから情報を読み出す
#         LD.L_A(block)
#         LD.H_n8(block, 0)
#         PUSH.HL(block)
#         POP.DE(block)
#         ADD.HL_HL(block)  # HL = index * 2
#         ADD.HL_DE(block)  # HL = index * 3
#         ADD.HL_HL(block)  # HL = index * 6
#         LD.DE_label(block, "IMAGE_HEADER_TABLE")
#         ADD.HL_DE(block)
#
#         # 3. ワークRAM（CURRENT_IMAGE_START_BANK_ADDR以降）を 6 バイト更新
#         LD.DE_n16(block, ADDR.CURRENT_IMAGE_START_BANK_ADDR)
#         for _ in range(6):
#             LD.A_mHL(block)
#             LD.mDE_A(block)
#             INC.HL(block)
#             INC.DE(block)
#
#         # 4. VRAM 描画
#         # 名前テーブル初期化（MSX1 VRAM 1800h-1AFFh）
#         RESET_NAME_TABLE_FUNC.call(block)
#
#         # パターンジェネレータ転送（VRAM 0000h-）
#         LD.HL_n16(block, PATTERN_BASE)
#         SET_VRAM_WRITE_FUNC.call(block)
#         LD.HL_n16(block, DATA_BANK_ADDR)  # 常に 8000h から
#         LD.A_mn16(block, ADDR.CURRENT_IMAGE_START_BANK_ADDR)
#         LD.E_A(block)
#         LD.D_n8(block, 24)  # 1画面分
#         SCROLL_VRAM_XFER_FUNC.call(block)
#
#         # カラーテーブル転送（VRAM 2000h-）
#         LD.HL_n16(block, COLOR_BASE)
#         SET_VRAM_WRITE_FUNC.call(block)
#         LD.HL_mn16(block, ADDR.CURRENT_IMAGE_COLOR_ADDRESS_ADDR)
#         LD.A_mn16(block, ADDR.CURRENT_IMAGE_COLOR_BANK_ADDR)
#         LD.E_A(block)
#         LD.D_n8(block, 24)
#         SCROLL_VRAM_XFER_FUNC.call(block)
#
#         RET(block)  # サブルーチンなので明示的にRET
#
#     return Func("UPDATE_IMAGE_DISPLAY", update_image_display, no_auto_ret=True)


def build_update_image_display_func2(image_entries_count: int) -> Func:
    def update_image_display(block: Block) -> None:
        # 入力: A = 表示したい画像番号
        # 安全装置: 範囲外なら RET
        CP.n8(block, image_entries_count)
        RET_NC(block)

        # 1. 画像番号の保存
        LD.mn16_A(block, ADDR.CURRENT_IMAGE_ADDR)

        # 2. ヘッダテーブル(6bytes/entry)から情報をワークRAMにロード
        LD.L_A(block)
        LD.H_n8(block, 0)
        PUSH.HL(block)
        POP.DE(block)
        ADD.HL_HL(block)  # *2
        ADD.HL_DE(block)  # *3
        ADD.HL_HL(block)  # *6
        LD.DE_label(block, "IMAGE_HEADER_TABLE")
        ADD.HL_DE(block)

        # CURRENT_IMAGE_START_BANK_ADDR から 6バイト分コピー
        LD.DE_n16(block, ADDR.CURRENT_IMAGE_START_BANK_ADDR)
        for _ in range(6):
            LD.A_mHL(block)
            LD.mDE_A(block)
            INC.HL(block)
            INC.DE(block)

        # --- [VRAM転送の動的アドレス計算ルーチン] ---
        # 共通ロジック: バンクとアドレスをスクロール行数分進める
        # 入力: HL=ベースアドレス, A=ベースバンク
        # 出力: HL=計算後アドレス, E=計算後バンク

        def calc_scroll_ptr(b: Block, is_color: bool):
            # 1行256バイトなので、CURRENT_SCROLL_ROW (16bit) の下位8bitが
            # そのまま 0x8000-0x80FF 等のオフセット（アドレスの下位8bitは常に0と仮定）
            # 上位8bit (256行単位) はバンクの移動を意味する

            if is_color:
                LD.HL_mn16(b, ADDR.CURRENT_IMAGE_COLOR_ADDRESS_ADDR)
                LD.A_mn16(b, ADDR.CURRENT_IMAGE_COLOR_BANK_ADDR)
            else:
                LD.HL_n16(b, DATA_BANK_ADDR)  # PGは常に 0x8000
                LD.A_mn16(b, ADDR.CURRENT_IMAGE_START_BANK_ADDR)

            # スクロール行数 (16bit) を取得
            # HL += (SCROLL_ROW_LOW * 256)
            # A += (SCROLL_ROW_HIGH * (256 * 256 / 16384)) ... は複雑なので、
            # シンプルに「1行ごとに 1byte/256byte」として計算

            PUSH.AF(b)
            LD.A_mn16(b, ADDR.CURRENT_SCROLL_ROW)  # Low byte (行数 0-255)
            # 1行は 256バイトなので、Low byte が 1増えると HL は 0x0100 増える
            # つまり、Hレジスタに加算すればよい
            ADD.A_H(b)
            LD.H_A(b)
            POP.AF(b)  # A = Base Bank

            # CURRENT_SCROLL_ROW の High byte (256行の倍数) を処理
            PUSH.AF(b)
            LD.A_mn16(b, ADDR.CURRENT_SCROLL_ROW + 1)
            # 256行 = 65536バイト = 4バンク分。
            # A += A * 4
            ADD.A_A(b)
            ADD.A_A(b)
            LD.E_A(b)  # バンク加算分
            POP.AF(b)
            ADD.A_E(b)
            LD.E_A(b)  # 最終バンク

            # HL が 0xC000 を超えていたらバンクを繰り上げる (ASCII16 ページ内正規化)
            NORMALIZE_BANK = unique_label("_NORMALIZE_BANK")
            NORMALIZE_BANK_DONE = unique_label("_NORMALIZE_BANK_DONE")
            b.label(NORMALIZE_BANK)
            LD.A_H(b)
            CP.n8(b, 0xC0)
            JR_C(b, NORMALIZE_BANK_DONE)
            SUB.n8(b, 0x40)  # HL -= 0x4000
            LD.H_A(b)
            INC.E(b)  # Bank++
            JR(b, NORMALIZE_BANK)
            b.label(NORMALIZE_BANK_DONE)

        # 4. VRAM 描画
        RESET_NAME_TABLE_FUNC.call(block)

        # パターンジェネレータ転送
        calc_scroll_ptr(block, is_color=False)
        # calc_scroll_ptr の結果: HL=ROMアドレス, E=バンク
        PUSH.HL(block)
        PUSH.DE(block)
        LD.HL_n16(block, PATTERN_BASE)
        SET_VRAM_WRITE_FUNC.call(block)
        POP.DE(block)
        POP.HL(block)
        LD.D_n8(block, 24)  # 常に1画面分
        SCROLL_VRAM_XFER_FUNC.call(block)

        # カラーテーブル転送
        calc_scroll_ptr(block, is_color=True)
        PUSH.HL(block)
        PUSH.DE(block)
        LD.HL_n16(block, COLOR_BASE)
        SET_VRAM_WRITE_FUNC.call(block)
        POP.DE(block)
        POP.HL(block)
        LD.D_n8(block, 24)
        SCROLL_VRAM_XFER_FUNC.call(block)

        RET(block)

    return Func("UPDATE_IMAGE_DISPLAY", update_image_display, no_auto_ret=True)


UPDATE_INPUT_FUNC = build_update_input_func(ADDR.INPUT_HOLD, ADDR.INPUT_TRG)

BEEP_WRITE_FUNC, SIMPLE_BEEP_FUNC, UPDATE_BEEP_FUNC = build_beep_control_utils(ADDR.BEEP_CNT, ADDR.BEEP_ACTIVE)


def calc_line_num_for_reg_a_macro(b: Block) -> None:
    """
    作業すべき行数をaレジスタに設定
    """
    LD.A_mn16(b, ADDR.CURRENT_IMAGE_ROW_COUNT_ADDR)  # 何行？
    CP.n8(b, SCREEN_TILE_ROWS)  # 1画面24行と比較
    ROW_COUNT_OK = unique_label()
    JR_C(b, ROW_COUNT_OK)
    LD.A_n8(b, SCREEN_TILE_ROWS)  # MAX 24行
    b.label(ROW_COUNT_OK)


def build_boot_bank(
    image_entries: Sequence[ImageEntry],
    header_bytes: Sequence[int],
    start_at: str,
    fill_byte: int,
    log_lines: List[str] | None = None,
) -> bytes:
    if not image_entries:
        raise ValueError("image_entries must not be empty")

    UPDATE_IMAGE_DISPLAY_FUNC = build_update_image_display_func2(len(image_entries))

    set_debug(True)

    if any(entry.start_bank < 1 or entry.start_bank > 0xFF for entry in image_entries):
        raise ValueError("start_bank must fit in 1 byte and be >= 1")

    b = Block()

    place_msx_rom_header_macro(b, entry_point=ROM_BASE + 0x10)

    b.label("start")
    init_stack_pointer_macro(b)
    enaslt_macro(b)

    LD.A_n8(b, 2)
    CALL(b, CHGMOD)
    set_msx2_palette_default_macro(b)

    LD.A_n8(b, 0x0F)
    LD.mn16_A(b, FORCLR)
    LD.A_n8(b, 0x00)
    LD.mn16_A(b, BAKCLR)
    LD.mn16_A(b, BDRCLR)
    CALL(b, CHGCLR)

    RESET_NAME_TABLE_FUNC.call(b)

    # 現在のページを記憶
    LD.A_n8(b, 0)
    LD.mn16_A(b, ADDR.CURRENT_IMAGE_ADDR)

    # 最初の画像のデータを得る
    LD.HL_label(b, "IMAGE_HEADER_TABLE")  # 各埋め込み画像のバンク番号やアドレスが書き込まれているアドレス
    LD.A_mHL(b)
    LD.mn16_A(b, ADDR.CURRENT_IMAGE_START_BANK_ADDR)  # 保存
    LD.mn16_A(b, ASCII16_PAGE2_REG)  # バンク切り替え

    # DE = パターンジェネレータアドレス
    INC.HL(b)
    LD.E_mHL(b)
    INC.HL(b)
    LD.D_mHL(b)
    # CURRENT_IMAGE_ROW_COUNT_ADDR = DE
    PUSH.HL(b)
    LD.HL_n16(b, ADDR.CURRENT_IMAGE_ROW_COUNT_ADDR)
    LD.mHL_E(b)
    INC.HL(b)
    LD.mHL_D(b)
    POP.HL(b)

    # CURRENT_IMAGE_COLOR_BANK_ADDR = COLOR TABLE BANK
    INC.HL(b)
    LD.A_mHL(b)
    LD.mn16_A(b, ADDR.CURRENT_IMAGE_COLOR_BANK_ADDR)

    # CURRENT_IMAGE_COLOR_ADDRESS_ADDR = COLOR TABLE ADDRESS
    INC.HL(b)
    LD.E_mHL(b)
    INC.HL(b)
    LD.D_mHL(b)
    LD.HL_n16(b, ADDR.CURRENT_IMAGE_COLOR_ADDRESS_ADDR)
    LD.mHL_E(b)
    INC.HL(b)
    LD.mHL_D(b)

    # --- [初期スクロール位置の計算] ---
    if start_at == "bottom":
        # 画像の総行数を A に取得
        LD.A_mn16(b, ADDR.CURRENT_IMAGE_ROW_COUNT_ADDR)
        # 1画面分の 24行を引く
        SUB.n8(b, 24)

        # もし総行数が 24行未満なら、キャリーフラグが立って負になる
        JR_NC(b, "INIT_POS_OK")
        XOR.A(b)  # 24行未満なら 0 にリセット

        b.label("INIT_POS_OK")
        LD.mn16_A(b, ADDR.CURRENT_SCROLL_ROW)  # 下位8bitに保存
        LD.A_n8(b, 0)
        LD.mn16_A(b, ADDR.CURRENT_SCROLL_ROW + 1)  # 上位8bitを 0 で初期化
    else:
        XOR.A(b)
        LD.mn16_A(b, ADDR.CURRENT_SCROLL_ROW)
        LD.mn16_A(b, ADDR.CURRENT_SCROLL_ROW + 1)

    # --- [初期表示] ---
    XOR.A(b)
    UPDATE_IMAGE_DISPLAY_FUNC.call(b)

    # --- [メインループ] ---
    b.label("MAIN_LOOP")
    HALT(b)  # V-Sync 待ち
    UPDATE_BEEP_FUNC.call(b)
    UPDATE_INPUT_FUNC.call(b)

    # SPACE (論理 L_BTN_A) が「今押されたか」をまずチェック
    LD.A_mn16(b, ADDR.INPUT_TRG)
    BIT.n8_A(b, INPUT_KEY_BIT.L_BTN_A)
    JR_Z(b, "MAIN_LOOP")

    # スペースが押された！ 次に SHIFT (論理 L_BTN_B) が「現在保持されているか」をチェック
    LD.A_mn16(b, ADDR.INPUT_HOLD)
    BIT.n8_A(b, INPUT_KEY_BIT.L_BTN_B)
    JR_NZ(b, "PREV_IMAGE")  # SHIFTありなら戻る

    # --- [NEXT_IMAGE: 次へ（ループ対応）] ---
    b.label("NEXT_IMAGE")
    LD.A_mn16(b, ADDR.CURRENT_IMAGE_ADDR)
    INC.A(b)
    CP.n8(b, len(image_entries))
    JR_C(b, "__GO_UPDATE__")  # 枚数未満ならそのまま更新へ
    XOR.A(b)  # 枚数に達したら 0 (最初) に戻す
    JR(b, "__GO_UPDATE__")

    # --- [PREV_IMAGE: 前へ（ループ対応）] ---
    b.label("PREV_IMAGE")
    LD.A_mn16(b, ADDR.CURRENT_IMAGE_ADDR)
    OR.A(b)  # 現在 0 かチェック
    JR_NZ(b, "__SUB_AND_UPDATE__")
    LD.A_n8(b, len(image_entries) - 1)  # 0 なら最後の画像番号へ
    JR(b, "__GO_UPDATE__")

    b.label("__SUB_AND_UPDATE__")
    DEC.A(b)

    b.label("__GO_UPDATE__")
    UPDATE_IMAGE_DISPLAY_FUNC.call(b)
    SIMPLE_BEEP_FUNC.call(b)
    JR(b, "MAIN_LOOP")

    # --- 関数定義 ---
    define_created_funcs(b)

    b.label("IMAGE_HEADER_TABLE")
    DB(b, *header_bytes)

    assembled = b.finalize(origin=ROM_BASE)
    used_bytes = len(assembled)
    if used_bytes > PAGE_SIZE:
        raise ValueError(
            f"Boot bank size exceeds one page: {used_bytes} bytes > {PAGE_SIZE}"
        )

    free_bytes = PAGE_SIZE - used_bytes
    used_percent = used_bytes / PAGE_SIZE * 100
    free_percent = free_bytes / PAGE_SIZE * 100
    log_and_store(
        "Boot bank (program area) usage: "
        f"{used_bytes}/{PAGE_SIZE} bytes ({used_percent:.2f}%) used, "
        f"{free_bytes} bytes ({free_percent:.2f}%) free",
        log_lines,
    )

    data = bytes(pad_bytes(list(assembled), PAGE_SIZE, fill_byte))
    log_and_store("---- labels ----", log_lines)
    log_and_store(debug_print_labels(b, origin=0x4000, no_print=True), log_lines)

    return data


def pack_image_into_banks(image: ImageData, fill_byte: int) -> tuple[list[bytes], int]:
    if image.tile_rows <= 0 or image.tile_rows > 0xFFFF:
        raise ValueError("tile_rows must fit in 2 bytes and be positive")

    expected_length = image.tile_rows * 256
    if len(image.pattern) != expected_length:
        raise ValueError("pattern data length mismatch")
    if len(image.color) != expected_length:
        raise ValueError("color data length mismatch")

    payload = bytearray()
    payload.extend(image.pattern)
    payload.extend(image.color)

    total_size = ((len(payload) + PAGE_SIZE - 1) // PAGE_SIZE) * PAGE_SIZE
    padded = bytes(pad_bytes(list(payload), total_size, fill_byte))
    pattern_size = len(image.pattern)
    return [padded[i : i + PAGE_SIZE] for i in range(0, len(padded), PAGE_SIZE)], pattern_size


def log_and_store(message: str, log_lines: list[str] | None) -> None:
    print(message)
    if log_lines is not None:
        log_lines.append(message)


def build(
    images: Sequence[ImageData],
    start_at: str = "bottom",
    fill_byte: int = 0xFF,
    log_lines: list[str] | None = None,
) -> bytes:
    if not 0 <= fill_byte <= 0xFF:
        raise ValueError("fill_byte must be 0..255")
    if not images:
        raise ValueError("images must not be empty")

    image_entries: list[ImageEntry] = []
    data_banks: list[bytes] = []
    next_bank = 1
    header_bytes: list[int] = []

    for i, image in enumerate(images):
        log_and_store(f"* packing image #{i} tiles:{image.tile_rows}", log_lines)

        start_bank = next_bank
        banks, pattern_size = pack_image_into_banks(image, fill_byte)
        color_bank = start_bank + pattern_size // PAGE_SIZE
        color_address = DATA_BANK_ADDR + (pattern_size % PAGE_SIZE)
        if color_bank > 0xFF:
            raise ValueError("color_bank must fit in 1 byte")
        if not DATA_BANK_ADDR <= color_address < DATA_BANK_ADDR + PAGE_SIZE:
            raise ValueError("color_address must stay within a single bank")
        image_entries.append(
            ImageEntry(
                start_bank=start_bank,
                tile_rows=image.tile_rows,
                color_bank=color_bank,
                color_address=color_address,
            )
        )
        data_banks.extend(banks)
        pattern_address = DATA_BANK_ADDR
        pattern_rom_offset = start_bank * PAGE_SIZE + (pattern_address - DATA_BANK_ADDR)
        log_and_store(
            "  pattern generator: "
            f"bank={start_bank} address=0x{pattern_address:04X} "
            f"ROM offset=0x{pattern_rom_offset:06X}",
            log_lines,
        )
        color_rom_offset = color_bank * PAGE_SIZE + (color_address - DATA_BANK_ADDR)
        log_and_store(
            "  color table: "
            f"bank={color_bank} address=0x{color_address:04X} "
            f"ROM offset=0x{color_rom_offset:06X}",
            log_lines,
        )
        next_bank += len(banks)

        header_byte = [
                start_bank,
                image.tile_rows & 0xFF,
                (image.tile_rows >> 8) & 0xFF,
                # カラーテーブルのバンク＆アドレス情報は パターンジェネレータ側から計算できるが
                # デバッグなどのやりやすさを考え、埋め込んでおく。将来的になくしてもいい。
                # 255 枚 * 6 byte =　1.494.. k Bytes : 現状
                # 255 枚 * 3 byte =　0.747.. k Bytes : 省けるバイト数 1kない 現状のブートバンクは余裕があるので許容
                color_bank & 0xFF,
                color_address & 0xFF,
                (color_address >> 8) & 0xFF,
            ]
        print(f"header #{i} {header_byte}")
        header_bytes.extend(header_byte)

    if next_bank > 0x100:
        raise ValueError("Total bank count exceeds 255, which is unsupported")

    header_bytes.extend([0xFF] * IMAGE_HEADER_END_SIZE)

    expected_header_length = (
        len(image_entries) * IMAGE_HEADER_ENTRY_SIZE + IMAGE_HEADER_END_SIZE
    )
    if len(header_bytes) != expected_header_length:
        raise AssertionError("header_bytes length mismatch")

    print_bytes(header_bytes, title="header bytes")

    banks = [build_boot_bank(image_entries, header_bytes, start_at, fill_byte)]
    banks.extend(data_banks)
    return b"".join(banks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="縦長 PNG から SCREEN2 縦スクロール ROM を生成するツール"
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="input",
        metavar="PNG",
        type=Path,
        nargs="+",
        action="append",
        required=True,
        help="入力 PNG。複数指定すると縦に連結。-i を複数回指定すると別画像として扱う。",
    )
    parser.add_argument(
        "--use-debug-image",
        action="store_true"
    )
    parser.add_argument(
        "--debug-image-index",
        type=int,
        default=0,
        help="--use-debug-image 時に埋め込む番号",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="出力 ROM ファイル名（未指定なら自動命名）",
    )
    parser.add_argument(
        "--background",
        type=str,
        default="#000000",
        help="右側／下側のパディングに使う色 (例: #000000 や 0,0,0)",
    )
    parser.add_argument(
        "--msx1pq-cli",
        type=Path,
        help="msx1pq_cli 実行ファイルのパス（未指定なら PATH を検索）",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        help="中間ファイルを書き出すワークフォルダ（未指定なら一時フォルダ）",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="ワークフォルダ内のキャッシュ済み量子化画像を使わずに再生成する",
    )
    parser.add_argument(
        "--fill-byte",
        type=int_from_str,
        default=0xFF,
        help="未使用領域の埋め値 (default: 0xFF)",
    )
    parser.add_argument(
        "--rom-info",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="ROM情報テキストを出力するかどうか (default: ON)",
    )
    parser.add_argument(
        "--start-at",
        choices=["top", "bottom"],
        default="bottom",
        help="初期表示位置 (default: bottom)",
    )
    return parser.parse_args()


def concatenate_images_vertically(images: Sequence[Image.Image]) -> Image.Image:
    height = sum(img.height for img in images)
    canvas = Image.new("RGB", (TARGET_WIDTH, height))

    y = 0
    for img in images:
        canvas.paste(img, (0, y))
        y += img.height

    return canvas


def _embed_label(data: bytearray, label: str) -> None:
    label_bytes = label.encode("ascii")
    length = len(data)
    for idx, value in enumerate(label_bytes):
        if idx >= length:
            break
        data[idx] = value


def _fill_with_story(data: bytearray, story: str, start: int = 0) -> None:
    story_bytes = story.encode("ascii")
    if not story_bytes:
        return

    for idx in range(start, len(data)):
        data[idx] = story_bytes[(idx - start) % len(story_bytes)]


def create_debug_image_data_list(debug_image_index: int) -> List[ImageData]:
    pattern = bytearray()
    for i in range(PATTERN_RAM_SIZE):
        line_block = (i // 8) % 4
        if line_block == 0:
            pattern.append(0xFF)
        elif line_block == 1:
            pattern.append(0x00)
        elif line_block == 2:
            pattern.append(0xAA)
        else:
            pattern.append(0x55)

    color = bytearray()
    for i in range(COLOR_RAM_SIZE):
        fg = (i // 8) % 15 + 1
        bg = (i // 64) % 16
        if fg == bg:
            bg = (bg + 1) % 16
        color.append((fg << 4) | bg)

    if debug_image_index > 0:
        pattern_label = f"PATTERN[{debug_image_index}] SCROLL VIEWER DEBUG"
        color_label = f"color[{debug_image_index}] scroll viewer debug"
        _embed_label(pattern, pattern_label)
        _embed_label(color, color_label)

        if debug_image_index > 1:
            story = "scroll viewer debug story fills the screen with test data. "
            pattern_story = story.upper()
            _fill_with_story(pattern, pattern_story, start=len(pattern_label))
            _fill_with_story(color, story, start=len(color_label))

    return [ImageData(pattern=bytes(pattern), color=bytes(color), tile_rows=SCREEN_TILE_ROWS)]


def ensure_output_writable(path: Path) -> None:
    if path.exists():
        if path.is_dir():
            raise SystemExit(f"Output path is a directory: {path}")
        try:
            with path.open("r+b"):
                pass
        except Exception as exc:  # pragma: no cover - CLI error path
            raise SystemExit(f"ERROR! failed to open ROM file for writing: {path}: {exc}") from exc


def main() -> None:
    args = parse_args()

    background = parse_color(args.background)
    msx1pq_cli = find_msx1pq_cli(args.msx1pq_cli)

    if args.output is not None:
        ensure_output_writable(args.output)

    log_lines: list[str] = []
    input_format_counter: Counter[str] = Counter()
    total_input_images = 0

    input_groups: list[list[Path]] = [list(group) for group in args.input]
    prepared_images: list[tuple[str, Image.Image, float]] = []
    image_data_list: list[ImageData] = []
    rom: bytes

    if args.use_debug_image:
        image_data_list = create_debug_image_data_list(args.debug_image_index)
        log_lines.append(
            f"Input images: {total_input_images} (debug image #{args.debug_image_index} used)"
        )
    else:
        for group in input_groups:
            if not group:
                raise SystemExit("Empty input group is not allowed")

            loaded_images: list[Image.Image] = []
            newest_input_mtime = 0.0
            for path in group:
                if not path.is_file():
                    raise SystemExit(f"not found: {path}")
                path_mtime = path.stat().st_mtime
                newest_input_mtime = max(newest_input_mtime, path_mtime)
                with Image.open(path) as src:
                    image_format = src.format or path.suffix.lstrip(".").upper() or "UNKNOWN"
                    input_format_counter[image_format] += 1
                    total_input_images += 1
                    loaded_images.append(prepare_image(src, background))

            merged = loaded_images[0] if len(loaded_images) == 1 else concatenate_images_vertically(loaded_images)
            group_name = "-".join(path.stem for path in group)
            prepared_images.append((group_name, merged, newest_input_mtime))

        format_summary = ", ".join(
            f"{fmt}={count}" for fmt, count in sorted(input_format_counter.items())
        )
        if not format_summary:
            format_summary = "none"
        log_lines.append(
            f"Input images: {total_input_images} file(s); formats: {format_summary}"
        )

        with open_workdir(args.workdir) as workdir:
            for idx, (group_name, image, newest_input_mtime) in enumerate(prepared_images):
                prepared_path = workdir / f"{idx:02d}_{group_name}_prepared.png"
                quantized_path = quantized_output_path(prepared_path, workdir)

                if not args.no_cache and is_cached_image_valid(
                    quantized_path, image.size, newest_input_mtime
                ):
                    log_and_store(f"REUSE image: {quantized_path}", log_lines)
                    image_data = load_quantized_image(
                        idx, quantized_path, "reused", log_lines
                    )
                    image_data_list.append(image_data)
                    continue

                image.save(prepared_path)
                quantized_path = run_msx1pq_cli(msx1pq_cli, prepared_path, workdir)
                os.unlink(prepared_path)

                image_data = load_quantized_image(
                    idx, quantized_path, "created", log_lines
                )
                image_data_list.append(image_data)

    if not image_data_list:
        raise SystemExit("No images were prepared")

    rom = build(image_data_list, start_at=args.start_at, fill_byte=args.fill_byte, log_lines=log_lines)

    out = args.output
    if out is None:
        if len(prepared_images) == 1:
            name = f"{prepared_images[0][0]}_scroll[{image_data_list[0].tile_rows * 8}px][ASCII16]"
        elif prepared_images:
            name = f"{prepared_images[0][0]}_scroll{len(prepared_images)}imgs[ASCII16]"
        else:
            name = f"debug_scroll{args.debug_image_index}[ASCII16]"
        out = Path.cwd() / f"{name}.rom"

    ensure_output_writable(out)

    try:
        out.write_bytes(rom)
    except Exception as exc:  # pragma: no cover - CLI error path
        raise SystemExit(f"ERROR! failed to write ROM file: {exc}") from exc

    log_and_store("---- mem ----", log_lines)
    log_and_store(mem_addr_allocator.as_str(), log_lines)
    log_and_store(f"Wrote {len(rom)} bytes to {out}", log_lines)

    if args.rom_info:
        rom_info_path = out.with_name(f"{out.stem}_rominfo.txt")
        rom_info_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
