import sys
from pathlib import Path
try:
    from mmsxxasmhelper.core import *
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from mmsxxasmhelper.core import *


# 1) マクロ相当の関数サンプル

def clear_a(b: Block) -> None:
    """Aレジスタを0クリアする簡単マクロ。"""

    # LD A,0
    b.emit(0x3E, 0x00)


# 2) 関数本体サンプル

def inc_a_times(b: Block, times: int = 1) -> None:
    """Aレジスタを数回インクリメントする関数本体。"""
    for i in range(times):
        INC.A(b)


# Funcとしてラップ
INC_A_TIMES = Func("inc_a_times", inc_a_times)


# 3) 全体コードを組み立てるサンプル

def build_example() -> bytes:
    """v0機能を使った簡単なコード生成例。"""

    # 定数定義
    const("INIT_VALUE", 1)
    const_bytes(
        "MSX_ROM_HEADER",
        *(pad_bytes(str_bytes("AB") + [0x10, 0x40], 16, 0x00))
    )

    b = Block()

    # メインエントリ
    b.label("start")

    # ROM HEADER の配置
    db(b, *DATA8["MSX_ROM_HEADER"])

    # LD A, INIT_VALUE
    LD.A_n8(b, CONST["INIT_VALUE"])

    # デバッグ用 HALT を差し込む(後で消したければ DEBUG=False にする)
    debug_trap(b)

    # CALL inc_a_times
    INC_A_TIMES.call(b)

    # デバッグ用 HALT
    debug_trap(b)

    # 無限ループ用ジャンプ (startに戻る)
    JP(b, "start")

    # --- 関数定義 ---
    INC_A_TIMES.define(b)

    # --- データ領域 ---
    b.label("table")
    db(b, 1, 2, 3, 4)
    dw(b, 0x1234, 0xABCD)

    # pad_pattern(b, 128, 0x00)  # 128B境界までパディング

    return b.finalize(origin=0x4000)


if __name__ == "__main__":

    code = build_example()
    print("len(code) =", len(code))
    code_with_comma = ', '.join(f'{byte:02X}' for byte in code)
    print("code =",code_with_comma)
    rom_16k = code + bytes([0x00] * (16 * 1024 - len(code)))
    # print("rom_16k =", ', '.join(f'{byte:02X}' for byte in rom_16k))
