"""Minimal MSX ROM sample built with :mod:`mmsxxasmhelper`.

- ``core`` のニーモニックラッパーでブロックを組み立てる。
- ``utils`` のデバッグトラップや無限ループマクロを使う。
- ``msxutils`` のスタック退避や ROM ヘッダ配置マクロを呼ぶ。

主に API の位置づけを把握するためのサンプルで、
``dist/msxrom_boot.bin`` に 16 KiB ROM を出力する。
"""

from __future__ import annotations

from pathlib import Path

from mmsxxasmhelper.core import Block, DB, Func, INC, LD
from mmsxxasmhelper.msxutils import (
    place_msx_rom_header_macro,
    restore_stack_pointer_macro,
    store_stack_pointer_macro,
)
from mmsxxasmhelper.utils import debug_trap, loop_infinite_macro


BOOT_ENTRY_POINT = 0x4010
ROM_ORIGIN = 0x4000
ROM_PAGE_SIZE = 0x4000
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "dist" / "msxrom_boot.bin"


# 1) マクロ相当の関数サンプル -------------------------------------------------


def clear_a_macro(b: Block) -> None:
    """A レジスタを 0 クリアする簡単マクロ。"""

    LD.A_n8(b, 0x00)


# 2) 関数本体サンプル ----------------------------------------------------------


def inc_a_times(b: Block, times: int = 1) -> None:
    """A レジスタを指定回数インクリメントする関数本体。"""

    for _ in range(times):
        INC.A(b)


# Func としてラップ -------------------------------------------------------------

INC_A_TIMES = Func("inc_a_times", inc_a_times)


# 3) 全体コードを組み立てるサンプル -------------------------------------------


def build_example(initial_value: int = 1) -> bytes:
    """最新の ``core`` / ``utils`` / ``msxutils`` API を使った簡単なコード生成例。"""

    b = Block()

    # ROM ヘッダを配置し、メインエントリラベルを設定
    place_msx_rom_header_macro(b, entry_point=BOOT_ENTRY_POINT)
    b.label("start")

    # スタックを一時領域へ退避
    store_stack_pointer_macro(b)

    # レジスタ操作とデバッグトラップ
    LD.A_n8(b, initial_value)
    debug_trap(b)

    INC_A_TIMES.call(b)
    clear_a_macro(b)
    debug_trap(b)

    # 末尾処理
    restore_stack_pointer_macro(b)
    loop_infinite_macro(b)

    # 関数定義 (呼び出しより後ろにまとめて配置される)
    INC_A_TIMES.define(b)

    # 追加データ (0,1,2,3 の連番を DB で配置)
    b.label("table")
    DB(b, 0, 1, 2, 3)

    return b.finalize(origin=ROM_ORIGIN)


if __name__ == "__main__":
    code = build_example()

    # 16 KiB にパディングして dist 以下へ書き出す
    rom = code + bytes([0x00] * (ROM_PAGE_SIZE - len(code)))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_bytes(rom)
    print(f"ROM written: {OUTPUT_PATH} ({len(rom)} bytes)")
