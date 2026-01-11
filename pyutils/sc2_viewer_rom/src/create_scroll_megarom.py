#!/usr/bin/env python3
"""
MSX1 SCREEN2 の縦スクロール ROM ビルダー。

現状の実装で行うこと:
- 入力はグループ単位で受け取り、各グループ内の PNG を左端基準で幅 256px にトリミング
  ／不足分を背景色で右パディングし、高さを 8px 単位まで下パディングしたうえで縦方向に
  連結する。
- `msx1pq_cli`（PATH または --msx1pq-cli で指定）で MSX1 ルール準拠の量子化 PNG を生成し、
  ワークディレクトリに *_quantized.png としてキャッシュする。入力より新しいキャッシュが
  あれば再利用し、--no-cache 指定時のみ再生成する。
- 量子化済み画像を 256 バイト × tile_rows のパターン／カラーデータに変換し、ASCII16
  MegaROM のデータバンクへバンク境界をまたぎながら隙間なく配置する。
- BGM が指定されていれば 1 バンクに格納し、タイトル／ビューアーで再生できるようにする。
- ブートバンクにスクロールビューアーを配置し、プログラム直後に各画像 7 バイトのヘッダー
  （開始バンク、行数、初期表示位置(top/bottom)、カラーデータのバンクとアドレス）を並べ、
  末尾に 0xFF × 4 の終端情報を付与する。
- ビューアーは SCREEN 2 を初期化し、画像ヘッダーに基づいた初期表示位置からスタートする。
  上下キーで 1 タイル行(8px)スクロールし、SHIFT+上下で 4 タイル行スクロールする。
  自動スクロール／自動ページ送り／BEEP／BGM／VDP wait は ESC で開く SCREEN 0 の
  設定メニューから切り替えられる。スペースで次の画像、GRAPHキーで前の画像に循環
  切り替えし、切り替え時に簡易 Beep を鳴らす。
- タイトル画面はカウントダウン付きで表示し、SPACE で開始、ESC で設定メニューへ遷移する。
- `--use-debug-image` を指定するとテスト用パターンを生成し、それ以外ではビルド結果を
  ROM として出力、必要に応じてログを rominfo に書き出す。


"""

from __future__ import annotations

import argparse
import io
import os
import random
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
    JP_NZ,
    JP_Z,
    JP_C,
    JP_PE,
    JR,
    JR_C,
    JR_NC,
    JR_NZ,
    JR_Z,
    JR_n8,
    DJNZ,
    LD,
    DI,
    OR,
    POP,
    PUSH,
    XOR,
    AND,
    DB,
    DW,
    SUB,
    NOP,
    OUT,
    OUT_A,
    LDD,
    LDI,
    LDIR,
    EX,
    SBC,
    SRL,
    OUT_C,
    OUTI,
    RET,
    RET_NC,
    RLCA,
    BIT,
    HALT,
    EI,
    unique_label,
    define_created_funcs,
    define_all_created_funcs_label_only,
    DEFAULT_FUNC_GROUP_NAME,
    get_funcs_by_group,
    ensure_funcs_defined,
    set_funcs_call_offset,
    set_funcs_bank,
    dump_func_bytes_on_finalize,
    register_dump_target,
    dump_mem,
    dump_regs,
)
from mmsxxasmhelper.msxutils import (
    CHGCLR,
    CHGMOD,
    FORCLR,
    BAKCLR,
    BDRCLR,
    INITXT,
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
    # build_set_vram_write_func,
    set_vram_write_macro,
    build_scroll_name_table_func,
    build_scroll_name_table_func2,
    build_outi_repeat_func,
    set_screen_colors_macro,
    set_text_cursor_macro,
    write_text_with_cursor_macro,
    set_screen_display_macro,
    set_screen_display_status_flag_macro,
    quantize_msx1_image_two_colors,
    parse_color,
    nearest_palette_index,
)
from mmsxxasmhelper.config_scene import (
    Screen0ConfigEntry,
    build_screen0_config_menu,
    get_work_byte_length_for_screen0_config_menu,
)
from mmsxxasmhelper.psgstream import build_play_vgm_frame_func
from mmsxxasmhelper.title_scene import build_title_screen_func
from mmsxxasmhelper.utils import (
    pad_bytes,
    ldir_macro,
    loop_infinite_macro,
    debug_trap,
    set_debug,
    print_bytes,
    debug_print_labels,
    MemAddrAllocator,
    debug_print_pc,
)

from PIL import Image


def _localized(getter):
    def wrapper(cls, **kwargs: object) -> str:
        template = getter(cls)[cls.lang]
        return template.format(**kwargs)

    return classmethod(wrapper)


class Messages:
    lang = "jp"

    @_localized
    def description(cls) -> dict[str, str]:
        return {
            "jp": "縦長 PNG から SCREEN2 縦スクロール ROM を生成するツール",
            "en": "Generate a SCREEN2 vertical scroll ROM from tall PNGs.",
        }

    @_localized
    def input_help(cls) -> dict[str, str]:
        return {
            "jp": "入力 PNG。複数指定すると縦に連結。-i を複数回指定すると別画像として扱う。",
            "en": "Input PNGs. Multiple files are stacked vertically. Repeat -i to create separate images.",
        }

    @_localized
    def debug_image_index_help(cls) -> dict[str, str]:
        return {
            "jp": "--use-debug-image 時に埋め込む番号",
            "en": "Index to embed when --use-debug-image is enabled.",
        }

    @_localized
    def output_help(cls) -> dict[str, str]:
        return {
            "jp": "出力 ROM ファイル名（未指定なら自動命名）",
            "en": "Output ROM file name (auto-generated if omitted).",
        }

    @_localized
    def background_help(cls) -> dict[str, str]:
        return {
            "jp": "右側／下側のパディングに使う色 (例: #000000 や 0,0,0)",
            "en": "Padding color for right/bottom (e.g. #000000 or 0,0,0).",
        }

    @_localized
    def msx1pq_cli_help(cls) -> dict[str, str]:
        return {
            "jp": "msx1pq_cli 実行ファイルのパス（未指定なら PATH を検索）",
            "en": "Path to msx1pq_cli (search PATH if omitted).",
        }

    @_localized
    def workdir_help(cls) -> dict[str, str]:
        return {
            "jp": "中間ファイルを書き出すワークフォルダ（未指定なら一時フォルダ）",
            "en": "Work directory for intermediate files (temporary if omitted).",
        }

    @_localized
    def no_cache_help(cls) -> dict[str, str]:
        return {
            "jp": "ワークフォルダ内のキャッシュ済み量子化画像を使わずに再生成する",
            "en": "Regenerate quantized images instead of using cache in the work directory.",
        }

    @_localized
    def fill_byte_help(cls) -> dict[str, str]:
        return {
            "jp": "未使用領域の埋め値 (default: 0xFF)",
            "en": "Fill byte for unused areas (default: 0xFF).",
        }

    @_localized
    def title_wait_help(cls) -> dict[str, str]:
        return {
            "jp": "タイトル画面のカウントダウン秒数。0なら自動遷移なし。",
            "en": "Countdown seconds on the title screen. 0 disables auto-start.",
        }

    @_localized
    def skip_title_help(cls) -> dict[str, str]:
        return {
            "jp": "タイトル画面を表示せずにビューアーを開始する",
            "en": "Start the viewer without showing the title screen.",
        }

    @_localized
    def rom_info_help(cls) -> dict[str, str]:
        return {
            "jp": "ROM情報テキストを出力するかどうか (default: ON)",
            "en": "Whether to output ROM info text (default: ON).",
        }

    @_localized
    def beep_help(cls) -> dict[str, str]:
        return {
            "jp": "起動時のBEEP設定 (default: ON)",
            "en": "Startup BEEP setting (default: ON).",
        }

    @_localized
    def bgm_help(cls) -> dict[str, str]:
        return {
            "jp": "起動時のBGM設定 (default: OFF)",
            "en": "Startup BGM setting (default: OFF).",
        }

    @_localized
    def bgm_path_help(cls) -> dict[str, str]:
        return {
            "jp": "BGMのbinファイルパス (未指定の場合はBGM設定は強制OFF)",
            "en": "Path to BGM bin file (BGM is forced OFF if omitted).",
        }

    @_localized
    def bgm_fps_help(cls) -> dict[str, str]:
        return {
            "jp": "BGM再生FPS (default: 30)",
            "en": "BGM playback FPS (default: 30).",
        }

    @_localized
    def start_at_help(cls) -> dict[str, str]:
        return {
            "jp": "全画像の初期表示位置デフォルト (default: top)",
            "en": "Default initial position for all images (default: top).",
        }

    @_localized
    def start_at_override_help(cls) -> dict[str, str]:
        return {
            "jp": "入力画像の順に初期表示位置を指定。画像数と一致している必要あり。",
            "en": "Specify initial positions in input order; count must match images.",
        }

    @_localized
    def start_at_random_help(cls) -> dict[str, str]:
        return {
            "jp": "全画像の初期表示位置をランダムに決定する（テスト用途）",
            "en": "Randomize initial positions for all images (testing).",
        }

    @_localized
    def debug_build_help(cls) -> dict[str, str]:
        return {
            "jp": "デバッグ用ビルドモードを有効にする。",
            "en": "Enable debug build mode.",
        }

    @_localized
    def vdp_wait_name_help(cls) -> dict[str, str]:
        return {
            "jp": "VDP WAITの設定(name table) (PARTIAL/NOWAIT, default: NOWAIT)",
            "en": "VDP WAIT setting (name table) (PARTIAL/NOWAIT, default: NOWAIT).",
        }

    @_localized
    def vdp_wait_pattern_help(cls) -> dict[str, str]:
        return {
            "jp": "VDP WAITの設定(pattern gen) (PARTIAL/NOWAIT, default: NOWAIT)",
            "en": "VDP WAIT setting (pattern gen) (PARTIAL/NOWAIT, default: NOWAIT).",
        }

    @_localized
    def vdp_wait_color_help(cls) -> dict[str, str]:
        return {
            "jp": "VDP WAITの設定(color table) (PARTIAL/NOWAIT, default: NOWAIT)",
            "en": "VDP WAIT setting (color table) (PARTIAL/NOWAIT, default: NOWAIT).",
        }

    @_localized
    def msx1pq_cli_not_found(cls) -> dict[str, str]:
        return {
            "jp": "msx1pq_cli が見つかりません: {path}",
            "en": "msx1pq_cli not found: {path}",
        }

    @_localized
    def msx1pq_cli_failed(cls) -> dict[str, str]:
        return {
            "jp": "msx1pq_cli の実行に失敗しました:\n"
            "command: {command}\n"
            "stdout:\n{stdout}\n"
            "stderr:\n{stderr}",
            "en": "msx1pq_cli failed:\ncommand: {command}\nstdout:\n{stdout}\nstderr:\n{stderr}",
        }

    @_localized
    def expected_output_not_found(cls) -> dict[str, str]:
        return {
            "jp": "期待した出力が見つかりません: {out_path}",
            "en": "Expected output not found: {out_path}",
        }

    @_localized
    def output_path_is_dir(cls) -> dict[str, str]:
        return {
            "jp": "出力先がディレクトリです: {path}",
            "en": "Output path is a directory: {path}",
        }

    @_localized
    def failed_open_rom(cls) -> dict[str, str]:
        return {
            "jp": "ERROR! ROMファイルを書き込み用に開けませんでした: {path}: {exc}",
            "en": "ERROR! failed to open ROM file for writing: {path}: {exc}",
        }

    @_localized
    def empty_input_group(cls) -> dict[str, str]:
        return {
            "jp": "空の入力グループは指定できません",
            "en": "Empty input group is not allowed",
        }

    @_localized
    def path_not_found(cls) -> dict[str, str]:
        return {
            "jp": "見つかりません: {path}",
            "en": "not found: {path}",
        }

    @_localized
    def no_images_prepared(cls) -> dict[str, str]:
        return {
            "jp": "画像が準備されていません",
            "en": "No images were prepared",
        }

    @_localized
    def start_conflict(cls) -> dict[str, str]:
        return {
            "jp": "--start-at-random と --start-at-override は同時に指定できません",
            "en": "Cannot use --start-at-random with --start-at-override",
        }

    @_localized
    def start_override_mismatch(cls) -> dict[str, str]:
        return {
            "jp": "--start-at-override の数は画像数と一致させてください",
            "en": "Number of --start-at-override values must match image count",
        }

    @_localized
    def bgm_not_found(cls) -> dict[str, str]:
        return {
            "jp": "BGMファイルが見つかりません: {path}",
            "en": "BGM file not found: {path}",
        }

    @_localized
    def failed_write_rom(cls) -> dict[str, str]:
        return {
            "jp": "ERROR! ROMファイルを書き込めませんでした: {exc}",
            "en": "ERROR! failed to write ROM file: {exc}",
        }


def _detect_language(argv: Sequence[str]) -> str:
    return "en" if "-en" in argv or "--english" in argv else "jp"


Messages.lang = _detect_language(sys.argv)


def int_from_str(value: str) -> int:
    return int(value, 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=Messages.description()
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
        help=Messages.input_help(),
    )
    parser.add_argument(
        "--use-debug-image",
        action="store_true"
    )
    parser.add_argument(
        "--debug-image-index",
        type=int,
        default=0,
        help=Messages.debug_image_index_help(),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=Messages.output_help(),
    )
    parser.add_argument(
        "--background",
        type=str,
        default="#000000",
        help=Messages.background_help(),
    )
    parser.add_argument(
        "--msx1pq-cli",
        type=Path,
        help=Messages.msx1pq_cli_help(),
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        help=Messages.workdir_help(),
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help=Messages.no_cache_help(),
    )
    parser.add_argument(
        "--fill-byte",
        type=int_from_str,
        default=0xFF,
        help=Messages.fill_byte_help(),
    )
    parser.add_argument(
        "--title-wait-seconds",
        type=int,
        default=5,
        help=Messages.title_wait_help(),
    )
    parser.add_argument(
        "--skip-title-screen",
        action="store_true",
        help=Messages.skip_title_help(),
    )
    parser.add_argument(
        "--rom-info",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=Messages.rom_info_help(),
    )
    parser.add_argument(
        "--beep",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=Messages.beep_help(),
    )
    parser.add_argument(
        "--bgm",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=Messages.bgm_help(),
    )
    parser.add_argument(
        "--bgm-path",
        type=Path,
        help=Messages.bgm_path_help(),
    )
    parser.add_argument(
        "--bgm-fps",
        type=int,
        choices=[30, 60],
        default=30,
        help=Messages.bgm_fps_help(),
    )
    parser.add_argument(
        "--start-at",
        choices=["top", "bottom"],
        default="top",
        help=Messages.start_at_help(),
    )
    parser.add_argument(
        "--start-at-override",
        nargs="+",
        choices=["top", "bottom"],
        help=Messages.start_at_override_help(),
    )
    parser.add_argument(
        "--start-at-random",
        action="store_true",
        help=Messages.start_at_random_help(),
    )
    parser.add_argument(
        "--debug-build",
        action="store_true",
        help=Messages.debug_build_help(),
    )
    parser.add_argument(
        "--vdp-wait-for-name-table",
        choices=["PARTIAL", "NOWAIT"],
        default="NOWAIT",
        help=Messages.vdp_wait_name_help(),
    )
    parser.add_argument(
        "--vdp-wait-for-pattern-gen",
        choices=["PARTIAL", "NOWAIT"],
        default="NOWAIT",
        help=Messages.vdp_wait_pattern_help(),
    )
    parser.add_argument(
        "--vdp-wait-for-color-table",
        choices=["PARTIAL", "NOWAIT"],
        default="NOWAIT",
        help=Messages.vdp_wait_color_help(),
    )
    parser.add_argument(
        "-en",
        "--english",
        action="store_true",
        help="Use -en/--english to switch all messages to English.",
    )
    args = parser.parse_args()
    if args.english:
        Messages.lang = "en"
    vdp_wait_map = {"PARTIAL": 0, "NOWAIT": 1}
    args.vdp_wait_for_name_table = vdp_wait_map[args.vdp_wait_for_name_table]
    args.vdp_wait_for_pattern_gen = vdp_wait_map[args.vdp_wait_for_pattern_gen]
    args.vdp_wait_for_color_table = vdp_wait_map[args.vdp_wait_for_color_table]
    return args


args = parse_args()

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
PATTERN_RAM_SIZE = 0x1800
COLOR_RAM_SIZE = 0x1800
TARGET_WIDTH = 256
SCREEN_TILE_ROWS = 24
IMAGE_HEADER_ENTRY_SIZE = 7
IMAGE_HEADER_END_SIZE = 4
QUANTIZED_SUFFIX = "_quantized"


SCROLL_VIEWER_FUNC_GROUP = "scroll_viewer"

AUTO_ADVANCE_INTERVAL_FRAMES = [
    0,
    180 * 60,
    60 * 60,
    30 * 60,
    10 * 60,
    5 * 60,
    3 * 60,
    1 * 60,
    1,
]
AUTO_SCROLL_INTERVAL_FRAMES = [
    0,
    30,
    26,
    22,
    18,
    14,
    10,
    6,
    2,
    1,
]
AUTO_SCROLL_EDGE_WAIT_FRAMES = [
    0,
    300,
    266,
    232,
    198,
    164,
    130,
    96,
    60,
    30,
]
AUTO_ADVANCE_INTERVAL_CHOICES = ["NONE", "3min", "1min", "30s", "10s", " 5s", " 3s", " 1s", "MAX"]
AUTO_SCROLL_LEVEL_CHOICES = ["NONE", "1", "2", "3", "4", "5", "6", "7", "8", "MAX"]
H_TIMI_HOOK_ADDR = 0xFD9F

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
    CURRENT_IMAGE_INITIAL_SCROLL_DIRECTION = (
        madd("CURRENT_IMAGE_INITIAL_SCROLL_DIRECTION", 1, description="0=上から,255=下から"))
    CURRENT_IMAGE_COLOR_BANK_ADDR = (
        madd("CURRENT_IMAGE_COLOR_BANK_ADDR", 1,description="カラーパターンが置かれているバンク番号"))
    CURRENT_IMAGE_COLOR_ADDRESS_ADDR = (
        madd("CURRENT_IMAGE_COLOR_ADDRESS_ADDR", 2, description="カラーパターンの先頭アドレス"))
    CURRENT_SCROLL_ROW = (
        madd("CURRENT_SCROLL_ROW", 2, description="スクロール位置"))

    INPUT_HOLD = madd("INPUT_HOLD", 1, description="現在押されている全入力")
    INPUT_TRG = madd("INPUT_TRG", 1, description="今回新しく押された入力")
    SKIP_AUTO_SCROLL = madd("SKIP_AUTO_SCROLL", 1, description="手動スクロール時は自動スクロールを抑止")
    BEEP_CNT = madd("BEEP_CNT", 1, description="BEEPカウンタ")
    BEEP_ACTIVE = madd("BEEP_ACTIVE", 1 , description="BEEP状態")
    TITLE_SECONDS_REMAINING = madd(
        "TITLE_SECONDS_REMAINING", 1, description="タイトル画面の残り秒数")
    TITLE_FRAME_COUNTER = madd(
        "TITLE_FRAME_COUNTER", 1, description="1秒あたりのフレームカウンタ")
    TITLE_COUNTDOWN_DIGITS = madd(
        "TITLE_COUNTDOWN_DIGITS", 3, description="タイトルの残り秒数文字列")

    SCROLL_DIRECTION = madd("SCROLL_DIRECTION", 1, description="スクロール方向 (1=下,255=上)")

    PG_BUFFER = madd("PG_BUFFER", 256 * 3, description="1行分PG(256B)×3行の作業バッファ")
    CT_BUFFER = madd("CT_BUFFER", 256 * 3, description="1行分CT(256B)×3行の作業バッファ")
    TARGET_ROW = madd("TARGET_ROW", 2)  # 更新する画像上の行番号
    VRAM_ROW_OFFSET = madd("VRAM_ROW_OFFSET", 1)  # VRAMブロック内の0-7行目オフセット
    SYNC_SCROLL_PG_VRAM_ADDRS = madd(
        "SYNC_SCROLL_PG_VRAM_ADDRS", 2 * 3, description="同期スクロールPG転送先VRAMアドレス(3行)"
    )
    SYNC_SCROLL_CT_VRAM_ADDRS = madd(
        "SYNC_SCROLL_CT_VRAM_ADDRS", 2 * 3, description="同期スクロールCT転送先VRAMアドレス(3行)"
    )
    CONFIG_BEEP_ENABLED = madd(
        "CONFIG_BEEP_ENABLED",
        1,
        initial_value=bytes([1 if args.beep else 0]),
        description="BEEPの有効/無効",
    )
    CONFIG_BGM_ENABLED = madd(
        "CONFIG_BGM_ENABLED",
        1,
        initial_value=bytes([1 if args.bgm and args.bgm_path is not None else 0]),
        description="BGMの有効/無効",
    )
    BGM_PTR_ADDR = madd(
        "BGM_PTR_ADDR", 2, description="BGMストリームの現在位置"
    )
    BGM_LOOP_ADDR = madd(
        "BGM_LOOP_ADDR", 2, description="BGMストリームのループ先頭"
    )
    # BGM_BANK_ADDR = madd(
    #     "BGM_BANK_ADDR", 1, description="BGMストリームのバンク番号"
    # )
    CURRENT_PAGE2_BANK_ADDR = madd(
        "CURRENT_PAGE2_BANK_ADDR", 1, description="ページ2に設定中のバンク番号"
    )
    VGM_TIMER_FLAG = madd(
        "VGM_TIMER_FLAG", 1, initial_value=bytes([0]), description="VGM再生の1/2フレーム切り替えフラグ"
    )
    CONFIG_AUTO_SPEED = madd(
        "CONFIG_AUTO_SPEED", 1, initial_value=bytes([4]), description="自動切り替え速度 (0-7)"
    )
    CONFIG_AUTO_SCROLL = madd(
        "CONFIG_AUTO_SCROLL", 1, initial_value=bytes([3]), description="自動スクロール速度 (0-9)"
    )
    # CONFIG_VDP_WAIT_NAME_TABLE = madd(
    #     "CONFIG_VDP_WAIT_NAME_TABLE",
    #     1,
    #     initial_value=bytes([args.vdp_wait_for_name_table]),
    #     description="VDP WAIT (name table) (0=PARTIAL,1=NOWAIT)",
    # )
    # CONFIG_VDP_WAIT_PATTERN_GEN = madd(
    #     "CONFIG_VDP_WAIT_PATTERN_GEN",
    #     1,
    #     initial_value=bytes([args.vdp_wait_for_pattern_gen]),
    #     description="VDP WAIT (pattern gen) (0=PARTIAL,1=NOWAIT)",
    # )
    # CONFIG_VDP_WAIT_COLOR_TABLE = madd(
    #     "CONFIG_VDP_WAIT_COLOR_TABLE",
    #     1,
    #     initial_value=bytes([args.vdp_wait_for_color_table]),
    #     description="VDP WAIT (color table) (0=PARTIAL,1=NOWAIT)",
    # )
    CONFIG_AUTO_PAGE_EDGE = madd(
        "CONFIG_AUTO_PAGE_EDGE", 1, initial_value=bytes([1]), description="自動スクロール中のページ端遷移"
    )
    AUTO_ADVANCE_COUNTER = madd(
        "AUTO_ADVANCE_COUNTER", 2, description="自動切り替えまでの残りフレーム"
    )
    AUTO_SCROLL_COUNTER = madd(
        "AUTO_SCROLL_COUNTER", 2, description="自動スクロールの残りフレーム"
    )
    AUTO_SCROLL_EDGE_WAIT = madd(
        "AUTO_SCROLL_EDGE_WAIT", 2, description="自動スクロール端待ちフレーム"
    )
    AUTO_SCROLL_DIR = madd(
        "AUTO_SCROLL_DIR", 1, description="自動スクロール方向 (1=下,255=上)"
    )
    AUTO_SCROLL_TURN_STATE = madd(
        "AUTO_SCROLL_TURN_STATE", 1, description="自動スクロール折返し状態 (0=なし,1=待機,2=開始)"
    )
    CONFIG_WORK_BASE = madd(
        "CONFIG_WORK_BASE",
        get_work_byte_length_for_screen0_config_menu(),
        description="コンフィグ用ワークベース",
    )


if args.debug_build:
    TEMP = madd(
        "TEMP",
        1,
        description="Padding",
    )
    DEBUG_DUMP_8BYTE_1 = madd("DEBUG_DUMP_8BYTE_1", 8, description="デバッグ用8バイトダンプ")
    DEBUG_DUMP_8BYTE_2 = madd("DEBUG_DUMP_8BYTE_2", 8, description="デバッグ用8バイトダンプ")
    register_dump_target("DEBUG_DUMP_8BYTE_1", DEBUG_DUMP_8BYTE_1, 8)
    register_dump_target("DEBUG_DUMP_8BYTE_2", DEBUG_DUMP_8BYTE_2, 8)


def set_page2_bank(block: Block) -> None:
    LD.mn16_A(block, ADDR.CURRENT_PAGE2_BANK_ADDR)
    LD.mn16_A(block, ASCII16_PAGE2_REG)


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


def find_msx1pq_cli(path: Path | None) -> Path | None:
    if path is not None:
        if path.is_file():
            return path
        raise SystemExit(Messages.msx1pq_cli_not_found(path=path))

    script_dir = Path(__file__).resolve().parent
    for candidate_name in ("msx1pq_cli", "msx1pq_cli.exe"):
        candidate = script_dir / candidate_name
        if candidate.is_file():
            return candidate

    resolved = shutil.which("msx1pq_cli")
    if not resolved:
        return None
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
            Messages.msx1pq_cli_failed(
                command=" ".join(cmd),
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )

    out_path = quantized_output_path(prepared_png, output_dir)
    if not out_path.is_file():
        raise SystemExit(Messages.expected_output_not_found(out_path=out_path))
    return out_path


def run_python_quantize(prepared_image: Image.Image, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    quantized = quantize_msx1_image_two_colors(prepared_image)
    quantized.save(output_path)
    return output_path


def restrict_two_colors(indices: list[int]) -> list[int]:
    """Ensure a block uses at most two colors.
    `msx1pq_cli`等 で 8dot 2 色ルールが守られている前提
    """

    unique = set(indices)
    if len(unique) <= 2:
        return indices

    raise ValueError(f"{unique} colors in 8 dots.")



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


def build_scroll_vram_xfer_func(with_wait: bool = True, group: str = DEFAULT_FUNC_GROUP_NAME) -> Func:
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
        set_page2_bank(block)

        LD.B_n8(block, 0)  # 1ページ(256byte)転送用
        LD.C_n8(block, 0x98)  # VDPデータポート

        # --- 1ページ(256byte) 転送ループ (64展開版) ---
        # OUTI_256はバンクが一緒なので使えない RAMコピーするとむしろ重くなる
        block.label("VRAM_BYTE_LOOP")
        for _ in range(32):  # 16でもいいが32のほうが2%くらいはやい
            # 1バイト転送 (18T)
            OUTI(block)  # (HL)->(C), HL++, B--

            if with_wait:
                # JR_n8(block, 0)  # ウェイト (12T)　3マイクロ秒強稼ぐ
                NOP(block, 2)  # 4*2=8T ウェイトの場合 これでも動くが危険？
        JP_NZ(block, "VRAM_BYTE_LOOP")

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
        JP_NZ(block, "VRAM_PAGE_LOOP")

    func_name = "scroll_vram_xfer" if with_wait else "sscroll_vram_xfer_no_wait"
    return Func(func_name, scroll_vram_xfer, group=group)


def build_draw_scroll_view_func(*, group: str = DEFAULT_FUNC_GROUP_NAME) -> Func:
    def draw_scroll_view(block: Block) -> None:
        """
        現在のスクロール位置に基づき 24 行ぶんの PG/CT を VRAM に転送する。
        """

        def calc_scroll_ptr(b: Block, is_color: bool):
            if is_color:
                LD.HL_mn16(b, ADDR.CURRENT_IMAGE_COLOR_ADDRESS_ADDR)
                LD.A_mn16(b, ADDR.CURRENT_IMAGE_COLOR_BANK_ADDR)
            else:
                LD.HL_n16(b, DATA_BANK_ADDR)  # PGは常に 0x8000
                LD.A_mn16(b, ADDR.CURRENT_IMAGE_START_BANK_ADDR)

            LD.E_A(b)  # E = ベースバンク

            # BC = スクロール行数 (16bit)
            PUSH.HL(b)
            LD.HL_mn16(b, ADDR.CURRENT_SCROLL_ROW)
            LD.B_H(b)
            LD.C_L(b)
            POP.HL(b)

            # 1行 = 256(0x0100)バイトなので、行数下位(C)をアドレス上位(H)に足す
            LD.A_C(b)
            AND.n8(b, 0x3F)
            ADD.A_H(b)
            LD.H_A(b)

            # C上位2bitぶんのバンク加算 (0..3)
            LD.A_C(b)
            AND.n8(b, 0xC0)
            for _ in range(6):
                SRL.r(b, "A")
            ADD.A_E(b)
            LD.E_A(b)

            # 行数上位(B)が 1 増えるごとに 256行 = 65536バイト = 4バンク(ASCII16)進む
            LD.A_B(b)
            ADD.A_A(b)  # *2
            ADD.A_A(b)  # *4
            ADD.A_E(b)
            LD.E_A(b)  # 最終的なバンク番号

            # HL が 0xC000 を超えていたらバンクを繰り上げる (正規化)
            NORM_LOOP = unique_label("_NORM")
            NORM_DONE = unique_label("_NORM_DONE")
            b.label(NORM_LOOP)
            LD.A_H(b)
            CP.n8(b, 0xC0)
            JR_C(b, NORM_DONE)
            SUB.n8(b, 0x40)  # HL -= 0x4000
            LD.H_A(b)
            INC.E(b)  # バンクインクリメント
            JR(b, NORM_LOOP)
            b.label(NORM_DONE)

        XOR.A(block)
        HALT(block)  # VBLANK待ち
        SCROLL_NAME_TABLE_FUNC_NOWAIT_SELECTED.call(block)  # VBLANK中はＶＤＰウェイトをなくせる

        # --- パターンジェネレータ転送 ---
        calc_scroll_ptr(block, is_color=False)
        PUSH.HL(block)
        PUSH.DE(block)
        LD.HL_n16(block, PATTERN_BASE)  # VRAM 0x0000
        set_vram_write_macro(block)
        POP.DE(block)
        POP.HL(block)
        LD.D_n8(block, 24)  # 24行分転送
        SCROLL_VRAM_XFER_FUNC.call(block)

        # --- カラーテーブル転送 ---
        calc_scroll_ptr(block, is_color=True)
        PUSH.HL(block)
        PUSH.DE(block)
        LD.HL_n16(block, COLOR_BASE)  # VRAM 0x2000
        set_vram_write_macro(block)
        POP.DE(block)
        POP.HL(block)
        LD.D_n8(block, 24)  # 24行分転送
        SCROLL_VRAM_XFER_FUNC.call(block)

        RET(block)

    return Func("DRAW_SCROLL_VIEW", draw_scroll_view, no_auto_ret=True, group=group)


DRAW_SCROLL_VIEW_FUNC = build_draw_scroll_view_func(group=SCROLL_VIEWER_FUNC_GROUP)


# OUTI_128_FUNC = build_outi_repeat_func(128, group=OUTI_FUNCS_GROUP)
# OUTI_256_FUNC = build_outi_repeat_func(256, group=OUTI_FUNCS_GROUP)
# OUTI_512_FUNC = build_outi_repeat_func(512, group=OUTI_FUNCS_GROUP)
# OUTI_1024_FUNC = build_outi_repeat_func(1024, group=OUTI_FUNCS_GROUP)
# OUTI_2048_FUNC = build_outi_repeat_func(2048, group=OUTI_FUNCS_GROUP)
# OUTI_FUNCS: tuple[Func, ...] = get_funcs_by_group(OUTI_FUNCS_GROUP)
# set_funcs_call_offset(OUTI_FUNCS, 0x8000)

OUTI_256_FUNC = build_outi_repeat_func(256, group=SCROLL_VIEWER_FUNC_GROUP)
OUTI_256_FUNC_NO_WAIT = build_outi_repeat_func(256, weight=0, group=SCROLL_VIEWER_FUNC_GROUP)

SCROLL_NAME_TABLE_FUNC = build_scroll_name_table_func(
    group=SCROLL_VIEWER_FUNC_GROUP
)
SCROLL_NAME_TABLE_FUNC_NOWAIT_PARTIAL = build_scroll_name_table_func2(
    OUTI_256_FUNC=OUTI_256_FUNC,
    OUTI_256_FUNC_NO_WAIT=OUTI_256_FUNC_NO_WAIT,
    use_no_wait="PARTIAL",
    group=SCROLL_VIEWER_FUNC_GROUP
)
SCROLL_NAME_TABLE_FUNC_NOWAIT = build_scroll_name_table_func2(
    OUTI_256_FUNC=OUTI_256_FUNC,
    OUTI_256_FUNC_NO_WAIT=OUTI_256_FUNC_NO_WAIT,
    use_no_wait="YES",
    group=SCROLL_VIEWER_FUNC_GROUP
)
SCROLL_NAME_TABLE_FUNC_NOWAIT_SELECTED = (
    SCROLL_NAME_TABLE_FUNC_NOWAIT_PARTIAL
    if args.vdp_wait_for_name_table == 0
    else SCROLL_NAME_TABLE_FUNC_NOWAIT
)
SCROLL_VRAM_XFER_FUNC = build_scroll_vram_xfer_func(group=SCROLL_VIEWER_FUNC_GROUP)


def build_update_image_display_func(
    image_entries_count: int, *, group: str = DEFAULT_FUNC_GROUP_NAME
) -> Func:
    """
    縦2028ドットを超える画像にも対応したかもしれない実装（未検証）
    """
    def update_image_display(block: Block) -> None:
        # 入力: A = 表示したい画像番号
        # 安全装置: 範囲外なら RET
        CP.n8(block, image_entries_count)
        RET_NC(block)

        # 1. 画像番号の保存
        LD.mn16_A(block, ADDR.CURRENT_IMAGE_ADDR)

        # 2. ヘッダテーブル(7bytes/entry)から情報をワークRAMにロード
        LD.L_A(block)
        LD.H_n8(block, 0)
        PUSH.HL(block)
        POP.DE(block)
        ADD.HL_HL(block)  # *2
        ADD.HL_HL(block)  # *4
        ADD.HL_DE(block)  # *5
        ADD.HL_DE(block)  # *6
        ADD.HL_DE(block)  # *7
        LD.DE_label(block, "IMAGE_HEADER_TABLE")
        ADD.HL_DE(block)

        # CURRENT_IMAGE_START_BANK_ADDR から 7バイト分コピー
        LD.DE_n16(block, ADDR.CURRENT_IMAGE_START_BANK_ADDR)
        for _ in range(7):
            LD.A_mHL(block)
            LD.mDE_A(block)
            INC.HL(block)
            INC.DE(block)

        # --- [16bit対応: スクロール位置のリセット] ---
        # 画像ヘッダに基づき CURRENT_SCROLL_ROW を初期化する
        INIT_POS_OK = unique_label("_INIT_POS_OK")
        INIT_FROM_TOP = unique_label("_INIT_FROM_TOP")
        INIT_FROM_BOTTOM = unique_label("_INIT_FROM_BOTTOM")

        # 画像ヘッダの初期スクロール方向が 0xFF の場合は下端開始、それ以外は上端開始
        LD.A_mn16(block, ADDR.CURRENT_IMAGE_INITIAL_SCROLL_DIRECTION)
        CP.n8(block, 0xFF)
        JR_Z(block, INIT_FROM_BOTTOM)
        JR(block, INIT_FROM_TOP)

        block.label(INIT_FROM_BOTTOM)
        # 下端開始: (総行数 - 24) をクランプして設定
        LD.HL_mn16(block, ADDR.CURRENT_IMAGE_ROW_COUNT_ADDR)
        LD.BC_n16(block, 24)
        OR.A(block)  # キャリークリア
        SBC.HL_BC(block)
        JR_NC(block, INIT_POS_OK)
        LD.HL_n16(block, 0)
        block.label(INIT_POS_OK)
        LD.mn16_HL(block, ADDR.CURRENT_SCROLL_ROW)
        JR(block, "_INIT_POS_DONE")

        # 上端開始: 常に 0
        block.label(INIT_FROM_TOP)
        LD.HL_n16(block, 0)
        LD.mn16_HL(block, ADDR.CURRENT_SCROLL_ROW)

        block.label("_INIT_POS_DONE")

        # 4. VRAM 描画実行
        DRAW_SCROLL_VIEW_FUNC.call(block)

        # 自動切り替え用カウンタを初期化
        LD.A_mn16(block, ADDR.CONFIG_AUTO_SPEED)
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)
        LD.DE_label(block, "AUTO_ADVANCE_INTERVAL_FRAMES_TABLE")
        ADD.HL_DE(block)
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)
        EX.DE_HL(block)
        LD.mn16_HL(block, ADDR.AUTO_ADVANCE_COUNTER)

        # 自動スクロール用カウンタを初期化
        LD.A_mn16(block, ADDR.CONFIG_AUTO_SCROLL)
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)
        LD.DE_label(block, "AUTO_SCROLL_INTERVAL_FRAMES_TABLE")
        ADD.HL_DE(block)
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)
        EX.DE_HL(block)
        LD.mn16_HL(block, ADDR.AUTO_SCROLL_COUNTER)
        LD.HL_n16(block, 0)
        LD.mn16_HL(block, ADDR.AUTO_SCROLL_EDGE_WAIT)
        LD.A_n8(block, 1)
        LD.mn16_A(block, ADDR.AUTO_SCROLL_DIR)
        XOR.A(block)
        LD.mn16_A(block, ADDR.AUTO_SCROLL_TURN_STATE)

        RET(block)

    return Func(
        "UPDATE_IMAGE_DISPLAY", update_image_display, no_auto_ret=True, group=group
    )


UPDATE_INPUT_FUNC = build_update_input_func(
    ADDR.INPUT_HOLD, ADDR.INPUT_TRG, group=SCROLL_VIEWER_FUNC_GROUP
)

BEEP_WRITE_FUNC, SIMPLE_BEEP_FUNC, UPDATE_BEEP_FUNC = build_beep_control_utils(
    ADDR.BEEP_CNT, ADDR.BEEP_ACTIVE, group=SCROLL_VIEWER_FUNC_GROUP
)

# 上下それぞれで異なるオフセット設定を定義
SCROLL_CONFIGS = {
    "UP": [(0, 0), (8, 8), (16, 16)],  # VRAM上段にTARGET_ROW、下段に+16
    "DOWN": [(0, -16), (8, -8), (16, 0)],  # VRAM下段にTARGET_ROW、上段に-16
}


def build_sync_scroll_prepare_func(direction: str, *, group: str = DEFAULT_FUNC_GROUP_NAME) -> Func:
    def sync_scroll_prepare(block: Block) -> None:
        # --- 1. VRAM内の物理行 (0-7) を計算して保存 ---
        LD.HL_mn16(block, ADDR.TARGET_ROW)
        LD.A_L(block)
        AND.n8(block, 0x07)
        LD.mn16_A(block, ADDR.VRAM_ROW_OFFSET)

        # 方向に応じたオフセットでループ
        for buf_index, (line_idx, img_adj) in enumerate(SCROLL_CONFIGS[direction]):
            # --- VRAM転送先を事前計算 ---
            LD.A_mn16(block, ADDR.VRAM_ROW_OFFSET)
            if line_idx != 0:
                ADD.A_n8(block, line_idx)
            LD.H_A(block)
            LD.L_n8(block, 0)
            LD.mn16_HL(block, ADDR.SYNC_SCROLL_PG_VRAM_ADDRS + (2 * buf_index))

            LD.A_mn16(block, ADDR.VRAM_ROW_OFFSET)
            ADD.A_n8(block, 0x20 + line_idx)
            LD.H_A(block)
            LD.L_n8(block, 0)
            LD.mn16_HL(block, ADDR.SYNC_SCROLL_CT_VRAM_ADDRS + (2 * buf_index))

            # --- 画像上の参照行 A = TARGET_ROW + img_adj ---
            LD.HL_mn16(block, ADDR.TARGET_ROW)
            if img_adj != 0:
                if img_adj > 0:
                    LD.BC_n16(block, img_adj)
                    ADD.HL_BC(block)
                else:
                    LD.BC_n16(block, -img_adj)
                    OR.A(block)
                    SBC.HL_BC(block)
            PUSH.HL(block)  # 画像行を保存

            # --- A: パターン(PG)準備 ---
            # バンク切り替え
            POP.HL(block)
            PUSH.HL(block)
            LD.B_H(block)
            LD.C_L(block)
            LD.HL_n16(block, DATA_BANK_ADDR)
            LD.A_mn16(block, ADDR.CURRENT_IMAGE_START_BANK_ADDR)
            LD.E_A(block)

            LD.A_C(block)
            AND.n8(block, 0x3F)
            ADD.A_H(block)
            LD.H_A(block)

            LD.A_C(block)
            AND.n8(block, 0xC0)
            for _ in range(6):
                SRL.r(block, "A")
            ADD.A_E(block)
            LD.E_A(block)

            LD.A_B(block)
            ADD.A_A(block)
            ADD.A_A(block)
            ADD.A_E(block)
            LD.E_A(block)

            l_norm_pg = unique_label(f"NORM_PG_{direction}_{line_idx}")
            block.label(l_norm_pg)
            LD.A_H(block)
            CP.n8(block, 0xC0)
            JR_C(block, l_norm_pg + "D")
            SUB.n8(block, 0x40)
            LD.H_A(block)
            INC.E(block)
            JR(block, l_norm_pg)
            block.label(l_norm_pg + "D")

            LD.A_E(block)
            set_page2_bank(block)

            LD.DE_n16(block, ADDR.PG_BUFFER + (0x100 * buf_index))
            LD.BC_n16(block, 256)
            LDIR(block)

            # --- B: カラー(CT)準備 ---
            POP.HL(block)
            LD.B_H(block)
            LD.C_L(block)
            LD.HL_mn16(block, ADDR.CURRENT_IMAGE_COLOR_ADDRESS_ADDR)
            LD.A_mn16(block, ADDR.CURRENT_IMAGE_COLOR_BANK_ADDR)
            LD.E_A(block)

            LD.A_C(block)
            AND.n8(block, 0x3F)
            ADD.A_H(block)
            LD.H_A(block)

            LD.A_C(block)
            AND.n8(block, 0xC0)
            for _ in range(6):
                SRL.r(block, "A")
            ADD.A_E(block)
            LD.E_A(block)

            LD.A_B(block)
            ADD.A_A(block)
            ADD.A_A(block)
            ADD.A_E(block)
            LD.E_A(block)

            # バンク正規化
            l_norm = unique_label(f"NORM_CT_{direction}_{line_idx}")
            block.label(l_norm)
            LD.A_H(block)
            CP.n8(block, 0xC0)
            JR_C(block, l_norm + "D")
            SUB.n8(block, 0x40)
            LD.H_A(block)
            INC.E(block)
            JR(block, l_norm)
            block.label(l_norm + "D")
            LD.A_E(block)
            set_page2_bank(block)
            LD.L_n8(block, 0)

            LD.DE_n16(block, ADDR.CT_BUFFER + (0x100 * buf_index))
            LD.BC_n16(block, 256)
            LDIR(block)

        RET(block)

    return Func(f"SYNC_SCROLL_PREPARE_{direction}", sync_scroll_prepare, no_auto_ret=True, group=group)


def build_sync_scroll_transfer_func(direction: str, *, group: str = DEFAULT_FUNC_GROUP_NAME) -> Func:
    def sync_scroll_transfer(block: Block) -> None:

        if args.vdp_wait_for_pattern_gen == 1:
            outi_pg_func = OUTI_256_FUNC_NO_WAIT
        else:
            outi_pg_func = OUTI_256_FUNC

        if args.vdp_wait_for_color_table == 1:
            outi_ct_func = OUTI_256_FUNC_NO_WAIT
        else:
            outi_ct_func = OUTI_256_FUNC

        LD.C_n8(block, 0x98)

        # 方向に応じたオフセットでループ
        for buf_index, (line_idx, _img_adj) in enumerate(SCROLL_CONFIGS[direction]):
            # --- A: パターン(PG)転送 ---
            LD.DE_n16(block, ADDR.PG_BUFFER + (0x100 * buf_index))
            LD.HL_mn16(block, ADDR.SYNC_SCROLL_PG_VRAM_ADDRS + (2 * buf_index))
            set_vram_write_macro(block)
            EX.DE_HL(block)
            outi_pg_func.call(block)

            # --- B: カラー(CT)転送 ---
            LD.DE_n16(block, ADDR.CT_BUFFER + (0x100 * buf_index))
            LD.HL_mn16(block, ADDR.SYNC_SCROLL_CT_VRAM_ADDRS + (2 * buf_index))
            set_vram_write_macro(block)
            EX.DE_HL(block)
            outi_ct_func.call(block)

        RET(block)

    return Func(f"SYNC_SCROLL_TRANSFER_{direction}", sync_scroll_transfer, no_auto_ret=True, group=group)


def build_config_scene_func(
    *,
    update_input_func: Func,
    bgm_on_change_func: Func | None = None,
    group: str = DEFAULT_FUNC_GROUP_NAME,
) -> tuple[Func, Sequence[Func]]:
    """設定メニューシーンを生成する。"""

    entries = [
        Screen0ConfigEntry(
            "BEEP",
            ["OFF", "O N"],
            ADDR.CONFIG_BEEP_ENABLED,
        ),
        Screen0ConfigEntry(
            "BGM",
            ["OFF", "O N"],
            ADDR.CONFIG_BGM_ENABLED,
            on_change_addr=bgm_on_change_func,
        ),
        Screen0ConfigEntry(
            "AUTO PAGE",
            AUTO_ADVANCE_INTERVAL_CHOICES,
            ADDR.CONFIG_AUTO_SPEED,
        ),
        Screen0ConfigEntry(
            "AUTO PAGE EDGE",
            ["N O", "YES"],
            ADDR.CONFIG_AUTO_PAGE_EDGE,
        ),
        Screen0ConfigEntry(
            "AUTO SCROLL",
            AUTO_SCROLL_LEVEL_CHOICES,
            ADDR.CONFIG_AUTO_SCROLL,
        ),
        # Screen0ConfigEntry(
        #     "NTWAIT",
        #     ["YES", "NO "],
        #     ADDR.CONFIG_VDP_WAIT_NAME_TABLE,
        # ),
        # Screen0ConfigEntry(
        #     "PGWAIT",
        #     ["YES", "NO "],
        #     ADDR.CONFIG_VDP_WAIT_PATTERN_GEN,
        # ),
        # Screen0ConfigEntry(
        #     "CTWAIT",
        #     ["YES", "NO "],
        #     ADDR.CONFIG_VDP_WAIT_COLOR_TABLE,
        # ),
    ]

    init_func, loop_func, table_funcs = build_screen0_config_menu(
        entries,
        update_input_func=update_input_func,
        input_trg_addr=ADDR.INPUT_TRG,
        work_base_addr=ADDR.CONFIG_WORK_BASE,
        header_lines=[
            "<HELP>",
            "ESC : ENTER | EXIT THIS HELP",
            "SPACE: NEXT IMAGE",
            "GRAPH: PREV IMAGE",
            "UP/DOWN: SCROLL",
            "SHIFT+UP/DOWN: FAST SCROLL",
        ],
        header_col=2,
        group=group,
    )

    def config_scene(block: Block) -> None:
        init_func.call(block)
        loop_func.call(block)
        RET(block)

    return Func("CONFIG_SCENE", config_scene, group=group), table_funcs


SYNC_SCROLL_UP_PREP_FUNC = build_sync_scroll_prepare_func(
    direction="UP", group=SCROLL_VIEWER_FUNC_GROUP
)
SYNC_SCROLL_DOWN_PREP_FUNC = build_sync_scroll_prepare_func(
    direction="DOWN", group=SCROLL_VIEWER_FUNC_GROUP
)
SYNC_SCROLL_UP_TRANSFER_FUNC = build_sync_scroll_transfer_func(
    direction="UP", group=SCROLL_VIEWER_FUNC_GROUP
)
SYNC_SCROLL_DOWN_TRANSFER_FUNC = build_sync_scroll_transfer_func(
    direction="DOWN", group=SCROLL_VIEWER_FUNC_GROUP
)


def build_reset_auto_scroll_turn_counters_func(
    *, group: str = DEFAULT_FUNC_GROUP_NAME
) -> Func:
    def reset_auto_scroll_turn_counters(block: Block) -> None:
        LD.HL_n16(block, 0)
        LD.mn16_HL(block, ADDR.AUTO_SCROLL_COUNTER)
        LD.mn16_HL(block, ADDR.AUTO_SCROLL_EDGE_WAIT)
        XOR.A(block)
        LD.mn16_A(block, ADDR.AUTO_SCROLL_TURN_STATE)
        RET(block)

    return Func(
        "RESET_AUTO_SCROLL_TURN_COUNTERS",
        reset_auto_scroll_turn_counters,
        group=group,
    )


RESET_AUTO_SCROLL_TURN_COUNTERS_FUNC = build_reset_auto_scroll_turn_counters_func(
    group=SCROLL_VIEWER_FUNC_GROUP
)


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
    fill_byte: int,
    title_wait_seconds: int,
    skip_title_screen: bool,
    beep_enabled_default: bool,
    bgm_enabled_default: bool,
    bgm_start_bank: int | None,
    bgm_fps: int,
    log_lines: List[str] | None = None,
    debug_build: bool = False,
) -> bytes:
    if not image_entries:
        raise ValueError("image_entries must not be empty")

    UPDATE_IMAGE_DISPLAY_FUNC = build_update_image_display_func(
        len(image_entries), group=SCROLL_VIEWER_FUNC_GROUP
    )
    TITLE_SCREEN_FUNC = build_title_screen_func(
        title_wait_seconds,
        subtitle_text="  Screen 2 Scroll Image Viewer",
        input_trg_addr=ADDR.INPUT_TRG,
        title_seconds_remaining_addr=ADDR.TITLE_SECONDS_REMAINING,
        title_frame_counter_addr=ADDR.TITLE_FRAME_COUNTER,
        title_countdown_digits_addr=ADDR.TITLE_COUNTDOWN_DIGITS,
        update_input_func=UPDATE_INPUT_FUNC,
        group=SCROLL_VIEWER_FUNC_GROUP,
    )
    def init_interrupt_hook_macro(block: Block) -> None:
        pass

    print("Building BGM playback function... bgm_start_bank:", bgm_start_bank)
    _, psg_isr_macro, mute_psg_macro = build_play_vgm_frame_func(
        ADDR.BGM_PTR_ADDR,
        ADDR.BGM_LOOP_ADDR,
        ADDR.VGM_TIMER_FLAG,
        ADDR.CONFIG_BGM_ENABLED,
        vgm_bank_num=bgm_start_bank,
        current_bank_addr=ADDR.CURRENT_PAGE2_BANK_ADDR,
        page2_bank_reg_addr=ASCII16_PAGE2_REG,
        fps30=bgm_fps == 30,
    )

    def bgm_setting_changed(block: Block) -> None:
        # BGMがOFFならPSGをミュート
        LD.A_mn16(block, ADDR.CONFIG_BGM_ENABLED)
        OR.A(block)
        LABEL_SKIP_MUTE = unique_label("BGM_SKIP_MUTE")
        JR_NZ(block, LABEL_SKIP_MUTE)
        mute_psg_macro(block)
        block.label(LABEL_SKIP_MUTE)
        RET(block)

    BGM_SETTING_CHANGED_FUNC = Func(
        "BGM_SETTING_CHANGED",
        bgm_setting_changed,
        group=SCROLL_VIEWER_FUNC_GROUP,
    )

    if bgm_start_bank is not None:

        def interrupt_handler(block: Block) -> None:
            PUSH.AF(block)
            PUSH.BC(block)
            PUSH.DE(block)
            PUSH.HL(block)
            PUSH.IX(block)
            PUSH.IY(block)
            psg_isr_macro(block)
            POP.IY(block)
            POP.IX(block)
            POP.HL(block)
            POP.DE(block)
            POP.BC(block)
            POP.AF(block)

        Func("INTERRUPT_HANDLER", interrupt_handler, group=SCROLL_VIEWER_FUNC_GROUP)

        def init_interrupt_hook(block: Block) -> None:
            DI(block)
            LD.A_n8(block, 0xC3)
            LD.mn16_A(block, H_TIMI_HOOK_ADDR)
            LD.HL_label(block, "INTERRUPT_HANDLER")
            LD.mn16_HL(block, (H_TIMI_HOOK_ADDR + 1) & 0xFFFF)
            EI(block)

        init_interrupt_hook_macro = init_interrupt_hook

    def apply_viewer_screen_settings(block: Block) -> None:
        LD.A_n8(block, 2)
        CALL(block, CHGMOD)
        set_msx2_palette_default_macro(block)

        LD.A_n8(block, 0x0F)
        LD.mn16_A(block, FORCLR)
        LD.A_n8(block, 0x00)
        LD.mn16_A(block, BAKCLR)
        LD.mn16_A(block, BDRCLR)
        CALL(block, CHGCLR)

    if debug_build:
        set_debug(True)

    # ensure_funcs_defined(OUTI_FUNCS)

    if any(entry.start_bank < 1 or entry.start_bank > 0xFF for entry in image_entries):
        raise ValueError("start_bank must fit in 1 byte and be >= 1")

    b = Block(debug=debug_build)

    CONFIG_SCENE_FUNC, CONFIG_TABLE_FUNCS = build_config_scene_func(
        update_input_func=UPDATE_INPUT_FUNC,
        bgm_on_change_func=BGM_SETTING_CHANGED_FUNC,
        group=SCROLL_VIEWER_FUNC_GROUP,
    )

    config_table_dump = io.StringIO()
    dump_func_bytes_on_finalize(
        b,
        groups=[SCROLL_VIEWER_FUNC_GROUP],
        funcs=CONFIG_TABLE_FUNCS,
        stream=config_table_dump,
    )

    place_msx_rom_header_macro(b, entry_point=ROM_BASE + 0x10)

    b.label("start")
    init_stack_pointer_macro(b)
    enaslt_macro(b)

    # コンフィグの初期値を設定
    mem_addr_allocator.emit_initial_value_loader(b)
    if bgm_start_bank is not None:
        LD.A_n8(b, bgm_start_bank & 0xFF)
        # LD.mn16_A(b, ADDR.BGM_BANK_ADDR)
        LD.HL_n16(b, DATA_BANK_ADDR)
        LD.mn16_HL(b, ADDR.BGM_PTR_ADDR)
        LD.mn16_HL(b, ADDR.BGM_LOOP_ADDR)

    AFTER_TITLE_CONFIG = unique_label("AFTER_TITLE_CONFIG")
    ENTER_CONFIG_FROM_TITLE = unique_label("ENTER_CONFIG_FROM_TITLE")

    if skip_title_screen:
        apply_viewer_screen_settings(b)
        b.label(AFTER_TITLE_CONFIG)
    else:
        TITLE_SCREEN_FUNC.call(b)
        CP.n8(b, 1)
        JR_Z(b, ENTER_CONFIG_FROM_TITLE)
        apply_viewer_screen_settings(b)
        JR(b, AFTER_TITLE_CONFIG)

        b.label(ENTER_CONFIG_FROM_TITLE)
        CONFIG_SCENE_FUNC.call(b)
        apply_viewer_screen_settings(b)

        b.label(AFTER_TITLE_CONFIG)

    XOR.A(b)
    SCROLL_NAME_TABLE_FUNC.call(b)

    # 現在のページを記憶
    LD.A_n8(b, 0)
    LD.mn16_A(b, ADDR.CURRENT_IMAGE_ADDR)

    # 最初の画像のデータを得る
    LD.HL_label(b, "IMAGE_HEADER_TABLE")  # 各埋め込み画像のバンク番号やアドレスが書き込まれているアドレス
    LD.A_mHL(b)
    LD.mn16_A(b, ADDR.CURRENT_IMAGE_START_BANK_ADDR)  # 保存
    set_page2_bank(b)  # バンク切り替え

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

    # INITIAL SCROLL DIRECTION
    INC.HL(b)
    LD.A_mHL(b)
    LD.mn16_A(b, ADDR.CURRENT_IMAGE_INITIAL_SCROLL_DIRECTION)

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

    # --- [初期表示] ---
    XOR.A(b)
    UPDATE_IMAGE_DISPLAY_FUNC.call(b)

    init_interrupt_hook_macro(b)

    # --- [メインループ] ---
    b.label("MAIN_LOOP")
    HALT(b)  # V-Sync 待ち
    UPDATE_BEEP_FUNC.call(b)
    UPDATE_INPUT_FUNC.call(b)
    XOR.A(b)
    LD.mn16_A(b, ADDR.SKIP_AUTO_SCROLL)

    # ESC でコンフィグ（ヘルプ）シーンへ遷移
    LD.A_mn16(b, ADDR.INPUT_TRG)
    BIT.n8_A(b, INPUT_KEY_BIT.L_ESC)
    JR_Z(b, "CHECK_UP")
    CONFIG_SCENE_FUNC.call(b)
    apply_viewer_screen_settings(b)
    LD.A_mn16(b, ADDR.CURRENT_IMAGE_ADDR)
    UPDATE_IMAGE_DISPLAY_FUNC.call(b)
    JP(b, "MAIN_LOOP")

    b.label("CHECK_UP")
    # --- [メインループ内の上下入力処理をここから差し替え] ---
    # 上キー判定
    LD.A_mn16(b, ADDR.INPUT_HOLD)
    BIT.n8_A(b, INPUT_KEY_BIT.L_UP)
    JR_Z(b, "CHECK_DOWN")
    LD.A_n8(b, 1)
    LD.mn16_A(b, ADDR.SKIP_AUTO_SCROLL)
    RESET_AUTO_SCROLL_TURN_COUNTERS_FUNC.call(b)
    LD.A_n8(b, 0xFF)
    LD.mn16_A(b, ADDR.AUTO_SCROLL_DIR)

    # SHIFT 押下時は 8 行スクロールして全体を再描画
    LD.A_mn16(b, ADDR.INPUT_HOLD)
    BIT.n8_A(b, INPUT_KEY_BIT.L_BTN_B)
    JR_Z(b, "SCROLL_UP_SINGLE")

    LD.HL_mn16(b, ADDR.CURRENT_SCROLL_ROW)
    LD.A_H(b)
    OR.L(b)
    JR_Z(b, "CHECK_DOWN")

    LD.BC_n16(b, 4)
    OR.A(b)
    SBC.HL_BC(b)
    JR_NC(b, "SHIFT_UP_STORE")
    LD.HL_n16(b, 0)

    b.label("SHIFT_UP_STORE")
    LD.mn16_HL(b, ADDR.CURRENT_SCROLL_ROW)
    DRAW_SCROLL_VIEW_FUNC.call(b)
    JP(b, "CHECK_AUTO_SCROLL")

    b.label("SCROLL_UP_SINGLE")

    # 0 より大きければデクリメント
    LD.HL_mn16(b, ADDR.CURRENT_SCROLL_ROW)
    LD.A_H(b)
    OR.L(b)
    JR_Z(b, "CHECK_DOWN")
    DEC.HL(b)
    LD.mn16_HL(b, ADDR.CURRENT_SCROLL_ROW)

    # --- 追記：方向フラグ(0=上)をセット ---
    XOR.A(b)
    LD.mn16_A(b, ADDR.SCROLL_DIRECTION)

    # ターゲット行は「新しく入ってきた上端の行」
    LD.mn16_HL(b, ADDR.TARGET_ROW)
    JP(b, "DO_UPDATE_SCROLL")

    b.label("CHECK_DOWN")
    # 下キー判定
    LD.A_mn16(b, ADDR.INPUT_HOLD)
    BIT.n8_A(b, INPUT_KEY_BIT.L_DOWN)
    JP_Z(b, "CHECK_AUTO_SCROLL")
    LD.A_n8(b, 1)
    LD.mn16_A(b, ADDR.SKIP_AUTO_SCROLL)
    RESET_AUTO_SCROLL_TURN_COUNTERS_FUNC.call(b)
    LD.A_n8(b, 1)
    LD.mn16_A(b, ADDR.AUTO_SCROLL_DIR)

    # SHIFT 押下時は 8 行スクロールして全体を再描画
    LD.A_mn16(b, ADDR.INPUT_HOLD)
    BIT.n8_A(b, INPUT_KEY_BIT.L_BTN_B)
    JR_Z(b, "SCROLL_DOWN_SINGLE")

    LD.HL_mn16(b, ADDR.CURRENT_IMAGE_ROW_COUNT_ADDR)
    LD.BC_n16(b, 24)
    OR.A(b)
    SBC.HL_BC(b)  # HL = limit

    LD.DE_mn16(b, ADDR.CURRENT_SCROLL_ROW)
    PUSH.HL(b)
    OR.A(b)
    SBC.HL_DE(b)
    POP.HL(b)
    JP_Z(b, "CHECK_AUTO_SCROLL")  # 下限到達
    JP_C(b, "CHECK_AUTO_SCROLL")

    EX.DE_HL(b)  # HL = current, DE = limit
    LD.BC_n16(b, 4)
    ADD.HL_BC(b)

    PUSH.HL(b)
    OR.A(b)
    SBC.HL_DE(b)
    JR_C(b, "SHIFT_DOWN_USE_CANDIDATE")
    POP.AF(b)  # 候補を破棄
    EX.DE_HL(b)  # HL = limit
    JR(b, "SHIFT_DOWN_STORE")

    b.label("SHIFT_DOWN_USE_CANDIDATE")
    POP.HL(b)

    b.label("SHIFT_DOWN_STORE")
    LD.mn16_HL(b, ADDR.CURRENT_SCROLL_ROW)
    DRAW_SCROLL_VIEW_FUNC.call(b)
    JP(b, "CHECK_AUTO_SCROLL")

    b.label("SCROLL_DOWN_SINGLE")

    # 最大値 (総行数 - 24) チェック
    LD.HL_mn16(b, ADDR.CURRENT_IMAGE_ROW_COUNT_ADDR)
    LD.BC_n16(b, 24)
    OR.A(b)
    SBC.HL_BC(b)  # HL = limit

    LD.DE_mn16(b, ADDR.CURRENT_SCROLL_ROW)
    PUSH.HL(b)
    OR.A(b)
    SBC.HL_DE(b)
    POP.HL(b)
    JP_Z(b, "CHECK_AUTO_SCROLL")  # 下限到達
    JP_C(b, "CHECK_AUTO_SCROLL")

    # 1行下へ移動
    LD.HL_mn16(b, ADDR.CURRENT_SCROLL_ROW)
    INC.HL(b)
    LD.mn16_HL(b, ADDR.CURRENT_SCROLL_ROW)

    # --- 追記：方向フラグ(1=下)をセット ---
    LD.A_n8(b, 1)
    LD.mn16_A(b, ADDR.SCROLL_DIRECTION)

    # ターゲット行は「新しく入ってきた下端の行 (開始行 + 23)」
    LD.BC_n16(b, 23)
    ADD.HL_BC(b)
    LD.mn16_HL(b, ADDR.TARGET_ROW)

    b.label("DO_UPDATE_SCROLL")
    # 1. 名前テーブルをずらす (TABLE_MOD24 を使用)
    LD.A_mn16(b, ADDR.CURRENT_SCROLL_ROW)
    LD.L_A(b)
    LD.H_n8(b, 0)
    LD.DE_label(b, "TABLE_MOD24")
    ADD.HL_DE(b)
    PUSH.HL(b)
    # 1. 新しい行の PG/CT を準備 (バッファ展開)
    LD.A_mn16(b, ADDR.SCROLL_DIRECTION)
    OR.A(b)
    JR_NZ(b, "DO_SYNC_PREP_DOWN")

    # 上スクロール用
    SYNC_SCROLL_UP_PREP_FUNC.call(b)
    JR(b, "SYNC_PREP_DONE")

    b.label("DO_SYNC_PREP_DOWN")
    # 下スクロール用
    SYNC_SCROLL_DOWN_PREP_FUNC.call(b)

    b.label("SYNC_PREP_DONE")
    POP.HL(b)

    LD.A_mHL(b)
    HALT(b)  # ここでVBLANKを待つ
    SCROLL_NAME_TABLE_FUNC_NOWAIT_SELECTED.call(b)  # VBLANK中はＶＤＰウェイトをなくせる

    # 2. 新しい行の PG/CT を転送  ADDR,TARGET_ROW に行番号が入っている
    LD.A_mn16(b, ADDR.SCROLL_DIRECTION)
    OR.A(b)
    JR_NZ(b, "DO_SYNC_XFER_DOWN")

    # 上スクロール用
    SYNC_SCROLL_UP_TRANSFER_FUNC.call(b)
    JR(b, "SYNC_XFER_DONE")

    b.label("DO_SYNC_XFER_DOWN")
    # 下スクロール用
    SYNC_SCROLL_DOWN_TRANSFER_FUNC.call(b)

    b.label("SYNC_XFER_DONE")

    JP(b, "CHECK_AUTO_PAGE")

    # --- 自動スクロール判定 ---
    b.label("CHECK_AUTO_SCROLL")
    LD.A_mn16(b, ADDR.SKIP_AUTO_SCROLL)
    OR.A(b)
    JP_NZ(b, "CHECK_AUTO_PAGE")
    LD.A_mn16(b, ADDR.CONFIG_AUTO_SCROLL)
    OR.A(b)
    JP_Z(b, "CHECK_AUTO_PAGE")

    # 端待ちカウンタが動作中なら優先して処理
    LD.HL_mn16(b, ADDR.AUTO_SCROLL_EDGE_WAIT)
    LD.A_H(b)
    OR.L(b)
    JR_Z(b, "AUTO_SCROLL_COUNTER_CHECK")
    DEC.HL(b)
    LD.mn16_HL(b, ADDR.AUTO_SCROLL_EDGE_WAIT)
    LD.A_H(b)
    OR.L(b)
    JP_NZ(b, "CHECK_AUTO_PAGE")
    LD.A_mn16(b, ADDR.AUTO_SCROLL_TURN_STATE)
    CP.n8(b, 1)
    JP_NZ(b, "CHECK_AUTO_PAGE")
    LD.A_n8(b, 2)
    LD.mn16_A(b, ADDR.AUTO_SCROLL_TURN_STATE)
    JP(b, "CHECK_AUTO_PAGE")

    b.label("AUTO_SCROLL_COUNTER_CHECK")
    LD.HL_mn16(b, ADDR.AUTO_SCROLL_COUNTER)
    LD.A_H(b)
    OR.L(b)
    JR_Z(b, "AUTO_SCROLL_STEP")
    DEC.HL(b)
    LD.mn16_HL(b, ADDR.AUTO_SCROLL_COUNTER)
    JP(b, "CHECK_AUTO_PAGE")

    b.label("AUTO_SCROLL_STEP")
    LD.A_mn16(b, ADDR.CONFIG_AUTO_SCROLL)
    LD.L_A(b)
    LD.H_n8(b, 0)
    ADD.HL_HL(b)
    LD.DE_label(b, "AUTO_SCROLL_INTERVAL_FRAMES_TABLE")
    ADD.HL_DE(b)
    LD.E_mHL(b)
    INC.HL(b)
    LD.D_mHL(b)
    EX.DE_HL(b)
    LD.mn16_HL(b, ADDR.AUTO_SCROLL_COUNTER)

    LD.A_mn16(b, ADDR.AUTO_SCROLL_TURN_STATE)
    CP.n8(b, 1)
    JR_NZ(b, "AUTO_SCROLL_STEP_DIR")
    LD.A_n8(b, 2)
    LD.mn16_A(b, ADDR.AUTO_SCROLL_TURN_STATE)

    # 方向に応じて端判定と移動
    b.label("AUTO_SCROLL_STEP_DIR")
    LD.A_mn16(b, ADDR.AUTO_SCROLL_DIR)
    CP.n8(b, 1)
    JP_Z(b, "AUTO_SCROLL_DOWN")

    # 上方向
    LD.HL_mn16(b, ADDR.CURRENT_SCROLL_ROW)
    LD.A_H(b)
    OR.L(b)
    JP_Z(b, "AUTO_SCROLL_EDGE_TOP")
    DEC.HL(b)
    LD.mn16_HL(b, ADDR.CURRENT_SCROLL_ROW)
    # --- 自動スクロール時の方向フラグ(0=上)をセット ---
    XOR.A(b)
    LD.mn16_A(b, ADDR.SCROLL_DIRECTION)
    LD.mn16_HL(b, ADDR.TARGET_ROW)
    JP(b, "DO_UPDATE_SCROLL")

    b.label("AUTO_SCROLL_EDGE_TOP")
    LD.HL_mn16(b, ADDR.AUTO_SCROLL_EDGE_WAIT)
    LD.A_H(b)
    OR.L(b)
    JP_NZ(b, "CHECK_AUTO_PAGE")
    LD.A_mn16(b, ADDR.CONFIG_AUTO_SCROLL)
    LD.L_A(b)
    LD.H_n8(b, 0)
    ADD.HL_HL(b)
    LD.DE_label(b, "AUTO_SCROLL_EDGE_WAIT_FRAMES_TABLE")
    ADD.HL_DE(b)
    LD.E_mHL(b)
    INC.HL(b)
    LD.D_mHL(b)
    EX.DE_HL(b)
    LD.mn16_HL(b, ADDR.AUTO_SCROLL_EDGE_WAIT)
    LD.A_n8(b, 1)
    LD.mn16_A(b, ADDR.AUTO_SCROLL_DIR)
    LD.A_n8(b, 1)
    LD.mn16_A(b, ADDR.AUTO_SCROLL_TURN_STATE)
    JP(b, "CHECK_AUTO_PAGE")

    b.label("AUTO_SCROLL_DOWN")
    # 最大値 (総行数 - 24) チェック
    LD.HL_mn16(b, ADDR.CURRENT_IMAGE_ROW_COUNT_ADDR)
    LD.BC_n16(b, 24)
    OR.A(b)
    SBC.HL_BC(b)  # HL = limit

    LD.DE_mn16(b, ADDR.CURRENT_SCROLL_ROW)
    PUSH.HL(b)
    OR.A(b)
    SBC.HL_DE(b)
    POP.HL(b)
    JR_Z(b, "AUTO_SCROLL_EDGE_BOTTOM")
    JR_C(b, "AUTO_SCROLL_EDGE_BOTTOM")

    # 端待ちを解除して 1行下へ移動
    LD.HL_n16(b, 0)
    LD.mn16_HL(b, ADDR.AUTO_SCROLL_EDGE_WAIT)
    LD.HL_mn16(b, ADDR.CURRENT_SCROLL_ROW)
    INC.HL(b)
    LD.mn16_HL(b, ADDR.CURRENT_SCROLL_ROW)
    # --- 自動スクロール時の方向フラグ(1=下)をセット ---
    LD.A_n8(b, 1)
    LD.mn16_A(b, ADDR.SCROLL_DIRECTION)

    # ターゲット行は「新しく入ってきた下端の行 (開始行 + 23)」
    LD.BC_n16(b, 23)
    ADD.HL_BC(b)
    LD.mn16_HL(b, ADDR.TARGET_ROW)
    JP(b, "DO_UPDATE_SCROLL")

    b.label("AUTO_SCROLL_EDGE_BOTTOM")
    LD.HL_mn16(b, ADDR.AUTO_SCROLL_EDGE_WAIT)
    LD.A_H(b)
    OR.L(b)
    JP_NZ(b, "CHECK_AUTO_PAGE")
    LD.A_mn16(b, ADDR.CONFIG_AUTO_SCROLL)
    LD.L_A(b)
    LD.H_n8(b, 0)
    ADD.HL_HL(b)
    LD.DE_label(b, "AUTO_SCROLL_EDGE_WAIT_FRAMES_TABLE")
    ADD.HL_DE(b)
    LD.E_mHL(b)
    INC.HL(b)
    LD.D_mHL(b)
    EX.DE_HL(b)
    LD.mn16_HL(b, ADDR.AUTO_SCROLL_EDGE_WAIT)
    LD.A_n8(b, 0xFF)
    LD.mn16_A(b, ADDR.AUTO_SCROLL_DIR)
    LD.A_n8(b, 1)
    LD.mn16_A(b, ADDR.AUTO_SCROLL_TURN_STATE)
    JP(b, "CHECK_AUTO_PAGE")

    # --- 自動切り替え判定 ---
    b.label("CHECK_AUTO_PAGE")
    LD.A_mn16(b, ADDR.CONFIG_AUTO_SPEED)
    OR.A(b)
    JR_Z(b, "CHECK_GRAPH")
    LD.A_mn16(b, ADDR.CONFIG_AUTO_SCROLL)
    OR.A(b)
    JR_Z(b, "AUTO_PAGE_COUNTER_CHECK")
    LD.A_mn16(b, ADDR.CONFIG_AUTO_PAGE_EDGE)
    OR.A(b)
    JR_Z(b, "AUTO_PAGE_COUNTER_CHECK")

    b.label("AUTO_PAGE_COUNTER_CHECK_EDGE")
    LD.HL_mn16(b, ADDR.AUTO_ADVANCE_COUNTER)
    LD.A_H(b)
    OR.L(b)
    JR_Z(b, "AUTO_PAGE_EDGE_CHECK")
    DEC.HL(b)
    LD.mn16_HL(b, ADDR.AUTO_ADVANCE_COUNTER)
    JR(b, "CHECK_GRAPH")

    b.label("AUTO_PAGE_EDGE_CHECK")
    LD.HL_mn16(b, ADDR.CURRENT_IMAGE_ROW_COUNT_ADDR)
    LD.BC_n16(b, 24)
    OR.A(b)
    SBC.HL_BC(b)
    JR_C(b, "AUTO_NEXT_IMAGE")
    LD.A_mn16(b, ADDR.AUTO_SCROLL_TURN_STATE)
    CP.n8(b, 2)
    JR_NZ(b, "CHECK_GRAPH")
    XOR.A(b)
    LD.mn16_A(b, ADDR.AUTO_SCROLL_TURN_STATE)
    JR(b, "AUTO_NEXT_IMAGE")

    b.label("AUTO_PAGE_COUNTER_CHECK")
    LD.HL_mn16(b, ADDR.AUTO_ADVANCE_COUNTER)
    LD.A_H(b)
    OR.L(b)
    JR_Z(b, "AUTO_NEXT_IMAGE")
    DEC.HL(b)
    LD.mn16_HL(b, ADDR.AUTO_ADVANCE_COUNTER)
    JR(b, "CHECK_GRAPH")

    b.label("AUTO_NEXT_IMAGE")
    LD.A_mn16(b, ADDR.CONFIG_AUTO_SPEED)
    LD.L_A(b)
    LD.H_n8(b, 0)
    ADD.HL_HL(b)
    LD.DE_label(b, "AUTO_ADVANCE_INTERVAL_FRAMES_TABLE")
    ADD.HL_DE(b)
    LD.E_mHL(b)
    INC.HL(b)
    LD.D_mHL(b)
    EX.DE_HL(b)
    LD.mn16_HL(b, ADDR.AUTO_ADVANCE_COUNTER)
    JR(b, "NEXT_IMAGE")

    # --- グラフキー判定 (前の画像へ) ---
    b.label("CHECK_GRAPH")
    LD.A_mn16(b, ADDR.INPUT_TRG)
    BIT.n8_A(b, INPUT_KEY_BIT.L_EXTRA)
    JP_NZ(b, "PREV_IMAGE")

    # --- スペースキー判定 (次の画像へ) ---
    b.label("CHECK_SPACE")
    BIT.n8_A(b, INPUT_KEY_BIT.L_BTN_A)
    JP_Z(b, "MAIN_LOOP")  # 押されていなければループの先頭へ

    # --- [NEXT_IMAGE: 次へ] ---
    b.label("NEXT_IMAGE")
    LD.A_mn16(b, ADDR.CURRENT_IMAGE_ADDR)
    INC.A(b)
    CP.n8(b, len(image_entries))
    JR_C(b, "__GO_UPDATE__")
    XOR.A(b)  # ループ
    JR(b, "__GO_UPDATE__")

    # --- [PREV_IMAGE: 前へ] ---
    b.label("PREV_IMAGE")
    LD.A_mn16(b, ADDR.CURRENT_IMAGE_ADDR)
    OR.A(b)
    JR_NZ(b, "__SUB_AND_UPDATE__")
    LD.A_n8(b, len(image_entries) - 1)
    JR(b, "__GO_UPDATE__")

    b.label("__SUB_AND_UPDATE__")
    DEC.A(b)

    b.label("__GO_UPDATE__")
    UPDATE_IMAGE_DISPLAY_FUNC.call(b)
    LD.A_mn16(b, ADDR.CONFIG_BEEP_ENABLED)
    OR.A(b)
    JR_Z(b, "__SKIP_BEEP__")
    SIMPLE_BEEP_FUNC.call(b)
    JP(b, "MAIN_LOOP")

    b.label("__SKIP_BEEP__")
    JP(b, "MAIN_LOOP")
    # --- 関数定義 ---
    define_created_funcs(b, group=SCROLL_VIEWER_FUNC_GROUP)

    # --- [事前計算テーブル群] ---
    # 0: 無効, 1-7: 数値が大きいほど高速になる自動切り替え秒数
    b.label("AUTO_ADVANCE_INTERVAL_FRAMES_TABLE")
    DW(b, *AUTO_ADVANCE_INTERVAL_FRAMES)
    b.label("AUTO_SCROLL_INTERVAL_FRAMES_TABLE")
    DW(b, *AUTO_SCROLL_INTERVAL_FRAMES)
    b.label("AUTO_SCROLL_EDGE_WAIT_FRAMES_TABLE")
    DW(b, *AUTO_SCROLL_EDGE_WAIT_FRAMES)

    # 1. 名前テーブル用 MOD 24 テーブル (行数 0-255 -> 0-23)
    # タイル番号のオフセット計算用。
    b.label("TABLE_MOD24")
    TABLE_MOD24 = [i % 24 for i in range(256)]
    print_bytes(TABLE_MOD24, title="TABLE_MOD24")
    DB(b, *TABLE_MOD24)

    # --- [画像データ配置ヘッダー] ---
    b.label("IMAGE_HEADER_TABLE")
    print_bytes(header_bytes, title="IMAGE_HEADER_TABLE")
    DB(b, *header_bytes)

    assembled = b.finalize(origin=ROM_BASE)

    config_table_dump.seek(0)
    for line in config_table_dump.read().splitlines():
        log_and_store(line, log_lines)

    data = bytes(pad_bytes(list(assembled), PAGE_SIZE, fill_byte))
    log_and_store("---- labels ----", log_lines)
    log_and_store(
        debug_print_labels(b, origin=0x4000, no_print=True, include_offset=True),
        log_lines,
    )

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

    return data


def validate_image_data(image: ImageData) -> None:
    if image.tile_rows <= 0 or image.tile_rows > 0xFFFF:
        raise ValueError("tile_rows must fit in 2 bytes and be positive")

    expected_length = image.tile_rows * 256
    if len(image.pattern) != expected_length:
        raise ValueError("pattern data length mismatch")
    if len(image.color) != expected_length:
        raise ValueError("color data length mismatch")


def concatenate_image_data_vertically(
    images: Sequence[ImageData],
) -> ImageData:
    if not images:
        raise ValueError("images must not be empty")

    pattern_parts: list[bytes] = []
    color_parts: list[bytes] = []
    total_rows = 0

    for image in images:
        validate_image_data(image)
        pattern_parts.append(image.pattern)
        color_parts.append(image.color)
        total_rows += image.tile_rows

    if total_rows > 0xFFFF:
        raise ValueError("Total tile rows exceed 65535")

    return ImageData(
        pattern=b"".join(pattern_parts),
        color=b"".join(color_parts),
        tile_rows=total_rows,
    )


def pack_image_into_banks(image: ImageData, fill_byte: int) -> tuple[list[bytes], int]:
    validate_image_data(image)

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
    start_positions: Sequence[str] | None = None,
    fill_byte: int = 0xFF,
    title_wait_seconds: int = 3,
    skip_title_screen: bool = False,
    beep_enabled_default: bool = True,
    bgm_enabled_default: bool = False,
    bgm_fps: int = 30,
    bgm_data: bytes | None = None,
    log_lines: list[str] | None = None,
    debug_build: bool = False,
) -> bytes:
    if not 0 <= fill_byte <= 0xFF:
        raise ValueError("fill_byte must be 0..255")
    if not images:
        raise ValueError("images must not be empty")

    title_wait_seconds = max(0, min(title_wait_seconds, 255))

    log_and_store(f"Title wait seconds: {title_wait_seconds}", log_lines)
    log_and_store(
        f"Title screen: {'SKIP' if skip_title_screen else 'ON'}",
        log_lines,
    )
    log_and_store(
        f"BEEP default: {'ON' if beep_enabled_default else 'OFF'}",
        log_lines,
    )
    log_and_store(
        f"BGM default: {'ON' if bgm_enabled_default else 'OFF'}",
        log_lines,
    )
    log_and_store(f"BGM FPS: {bgm_fps}", log_lines)

    image_entries: list[ImageEntry] = []
    data_banks: list[bytes] = []
    next_bank = 1
    header_bytes: list[int] = []
    bgm_start_bank: int | None = None
    if bgm_data is not None:
        if len(bgm_data) > PAGE_SIZE:
            bgm_data = bgm_data[:PAGE_SIZE]
        bgm_start_bank = next_bank
        bgm_payload = bytearray([fill_byte] * PAGE_SIZE)
        bgm_payload[: len(bgm_data)] = bgm_data
        data_banks.append(bytes(bgm_payload))
        bgm_bank_count = 1
        next_bank += bgm_bank_count

    if start_positions is None:
        start_positions = ["top"] * len(images)
    elif len(start_positions) != len(images):
        raise ValueError("start_positions length must match images length")

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

        start_at_flag = 0xFF if start_positions[i] == "bottom" else 0
        header_byte = [
            start_bank,
            image.tile_rows & 0xFF,
            (image.tile_rows >> 8) & 0xFF,
            start_at_flag,
            # カラーテーブルのバンク＆アドレス情報は パターンジェネレータ側から計算できるが
            # デバッグなどのやりやすさを考え、埋め込んでおく。将来的になくしてもいい。
            # 255 枚 * 7 byte =　1.746.. k Bytes : 現状
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

    banks = [
        build_boot_bank(
            image_entries,
            header_bytes,
            fill_byte,
            title_wait_seconds,
            skip_title_screen,
            beep_enabled_default,
            bgm_enabled_default,
            bgm_start_bank,
            bgm_fps,
            log_lines,
            debug_build,
        )
    ]
    # banks.extend(outi_funcs_banks)
    banks.extend(data_banks)
    return b"".join(banks)



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
    """アウトプットファイルが書き込み出来るが（処理の事前に）チェックする"""
    if path.exists():
        if path.is_dir():
            raise SystemExit(Messages.output_path_is_dir(path=path))
        try:
            # openMSXで開いているROMは r+b でのOPENをパスするので同名に変更する事で状態をチェックする
            os.replace(path, path)
        except Exception as exc:  # pragma: no cover - CLI error path
            raise SystemExit(Messages.failed_open_rom(path=path, exc=exc)) from exc
    return


def main() -> None:

    background = parse_color(args.background)
    msx1pq_cli = find_msx1pq_cli(args.msx1pq_cli)
    mem_addr_allocator.debug = args.debug_build
    bgm_data: bytes | None = None
    bgm_enabled_default = args.bgm

    if args.output is not None:
        ensure_output_writable(args.output)

    log_lines: list[str] = []
    input_format_counter: Counter[str] = Counter()
    total_input_images = 0

    input_groups: list[list[Path]] = [list(group) for group in args.input]
    prepared_groups: list[tuple[str, list[tuple[str, Image.Image, float]]]] = []
    image_data_list: list[ImageData] = []
    rom: bytes
    quantized_image_counter = 0

    if args.use_debug_image:
        image_data_list = create_debug_image_data_list(args.debug_image_index)
        log_lines.append(
            f"Input images: {total_input_images} (debug image #{args.debug_image_index} used)"
        )
    else:
        for group in input_groups:
            if not group:
                raise SystemExit(Messages.empty_input_group())

            group_segments: list[tuple[str, Image.Image, float]] = []
            for path in group:
                if not path.is_file():
                    raise SystemExit(Messages.path_not_found(path=path))
                with Image.open(path) as src:
                    image_format = src.format or path.suffix.lstrip(".").upper() or "UNKNOWN"
                    input_format_counter[image_format] += 1
                    total_input_images += 1
                    prepared = prepare_image(src, background)
                    group_segments.append((path.stem, prepared, path.stat().st_mtime))

            group_name = "-".join(path.stem for path in group)
            prepared_groups.append((group_name, group_segments))

        format_summary = ", ".join(
            f"{fmt}={count}" for fmt, count in sorted(input_format_counter.items())
        )
        if not format_summary:
            format_summary = "none"
        log_lines.append(
            f"Input images: {total_input_images} file(s); formats: {format_summary}"
        )

        with open_workdir(args.workdir) as workdir:
            if msx1pq_cli is None:
                log_and_store(
                    "msx1pq_cli not found; using Python quantization fallback.",
                    log_lines,
                )
            for group_idx, (group_name, segments) in enumerate(prepared_groups):
                segment_image_data: list[ImageData] = []
                for segment_idx, (segment_name, image, src_mtime) in enumerate(segments):
                    prepared_path = (
                        workdir
                        / f"{group_idx:02d}_{segment_idx:02d}_{group_name}_{segment_name}_prepared.png"
                    )
                    quantized_path = quantized_output_path(prepared_path, workdir)

                    if not args.no_cache and is_cached_image_valid(
                        quantized_path, image.size, src_mtime
                    ):
                        log_and_store(f"REUSE image: {quantized_path}", log_lines)
                        image_data = load_quantized_image(
                            quantized_image_counter, quantized_path, "reused", log_lines
                        )
                        quantized_image_counter += 1
                        segment_image_data.append(image_data)
                        continue

                    if msx1pq_cli is None:
                        quantized_path = run_python_quantize(image, quantized_path)
                    else:
                        image.save(prepared_path)
                        quantized_path = run_msx1pq_cli(msx1pq_cli, prepared_path, workdir)
                        os.unlink(prepared_path)

                    image_data = load_quantized_image(
                        quantized_image_counter, quantized_path, "created", log_lines
                    )
                    quantized_image_counter += 1
                    segment_image_data.append(image_data)

                image_data_list.append(concatenate_image_data_vertically(segment_image_data))

    if not image_data_list:
        raise SystemExit(Messages.no_images_prepared())

    if args.start_at_random and args.start_at_override:
        raise SystemExit(Messages.start_conflict())

    if args.start_at_random:
        start_positions = [random.choice(["top", "bottom"]) for _ in image_data_list]
    elif args.start_at_override:
        if len(args.start_at_override) != len(image_data_list):
            raise SystemExit(Messages.start_override_mismatch())
        start_positions = args.start_at_override
    else:
        start_positions = [args.start_at] * len(image_data_list)

    if args.bgm_path is None:
        bgm_enabled_default = False
    else:
        if not args.bgm_path.is_file():
            raise SystemExit(Messages.bgm_not_found(path=args.bgm_path))
        bgm_data = args.bgm_path.read_bytes()
        if len(bgm_data) > PAGE_SIZE:
            log_and_store("BGM file size exceeds 16KB; truncating to 16KB", log_lines)
            bgm_data = bgm_data[:PAGE_SIZE]

    rom = build(
        image_data_list,
        start_positions=start_positions,
        fill_byte=args.fill_byte,
        title_wait_seconds=args.title_wait_seconds,
        skip_title_screen=args.skip_title_screen,
        beep_enabled_default=args.beep,
        bgm_enabled_default=bgm_enabled_default,
        bgm_fps=args.bgm_fps,
        bgm_data=bgm_data,
        log_lines=log_lines,
        debug_build=args.debug_build,
    )

    out = args.output
    if out is None:
        if len(prepared_groups) == 1:
            name = f"{prepared_groups[0][0]}_scroll[{image_data_list[0].tile_rows * 8}px][ASCII16]"
        elif prepared_groups:
            name = f"{prepared_groups[0][0]}_scroll{len(prepared_groups)}imgs[ASCII16]"
        else:
            name = f"debug_scroll{args.debug_image_index}[ASCII16]"
        out = Path.cwd() / f"{name}.rom"

    ensure_output_writable(out)

    try:
        out.write_bytes(rom)
    except Exception as exc:  # pragma: no cover - CLI error path
        raise SystemExit(Messages.failed_write_rom(exc=exc)) from exc

    log_and_store("---- mem ----", log_lines)
    log_and_store(mem_addr_allocator.as_str(), log_lines)
    log_and_store(f"Wrote {len(rom)} bytes to {out}", log_lines)

    if args.rom_info:
        rom_info_path = out.with_name(f"{out.stem}_rominfo.txt")
        rom_info_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
