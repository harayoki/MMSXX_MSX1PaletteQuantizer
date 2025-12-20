"""
一般用途 マクロ & 関数 他
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, Concatenate, Literal, ParamSpec, Sequence

from mmsxxasmhelper.core import *

__all__ = [
    "create_rng_seed_func",
    "rng_next_func",
    "loop_infinite_macro",
    "set_debug",
    "debug_trap",
]

JIFFY_ADDR = 0xFC9E


# ---------------------------------------------------------------------------
# 関数
# ---------------------------------------------------------------------------


def create_rng_seed_func(rng_state_addr: int, preserve_reg_bc: bool = True):
    """
    ランダムシードの値を指定アドレスに描きこむ
    :param rng_state_addr: 読み書きするアドレス
    :param preserve_reg_bc: bcレジスタを保護するか
    """
    def _create_rng_seed(b: Block):
        if preserve_reg_bc:
            PUSH.BC(b)
        LD.A_mn16(b, JIFFY_ADDR)
        LD.B_A(b)
        LD.A_mn16(b, JIFFY_ADDR + 1)
        XOR.B(b)
        if preserve_reg_bc:
            POP.BC(b)
        LD.mn16_A(b, rng_state_addr)

    return Func("create_rng_seed", _create_rng_seed)


def rng_next_func(rng_state_addr: int, preserve_reg_bc: bool = True) -> Func:
    """
    古典的簡易ランダムアルゴリズム
    あるアドレスの値を次のランダム値に更新する Aレジスタに更新後の値を返す
    :param rng_state_addr: 読み書きするアドレス
    :param preserve_reg_bc: bcレジスタを保護するか
    """
    def _rng_next(b: Block) -> None:
        """
        8bit LCG: state = state * 5 + 1.
        """
        if preserve_reg_bc:
            PUSH.BC(b)
        LD.A_mn16(b, rng_state_addr)
        LD.B_A(b)
        ADD.A_A(b)
        ADD.A_A(b)
        ADD.A_B(b)
        INC.A(b)
        LD.mn16_A(b, rng_state_addr)
        if preserve_reg_bc:
            POP.BC(b)
        RET(b)

    return Func("rng_next", _rng_next)


# ---------------------------------------------------------------------------
# マクロ
# ---------------------------------------------------------------------------


def loop_infinite_macro(b: Block) -> None:
    """無限ループを作成するマクロ。"""
    # 同じアドレスに相対ジャンプする
    JR_n8(b, -2)

# ---------------------------------------------------------------------------
# DEBUG 用フラグと簡易トラップ
# ---------------------------------------------------------------------------


DEBUG: bool = True


def set_debug(flag: bool) -> None:
    """DEBUG フラグを設定する。"""
    global DEBUG
    DEBUG = flag


def debug_trap(b: Block) -> None:
    """DEBUG が True のときだけデバッグ用命令を挿入する。"""
    if not DEBUG:
        return
    HALT(b)
