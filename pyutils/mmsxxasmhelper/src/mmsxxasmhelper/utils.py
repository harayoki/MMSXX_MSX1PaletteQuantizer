"""
一般用途 マクロ & 関数 他
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, Concatenate, Literal, ParamSpec, Sequence

from mmsxxasmhelper.core import *

__all__ = [
    "loop_infinite_macro",
    "set_debug",
    "debug_trap",
]


def loop_infinite_macro(b: Block) -> None:
    """無限ループを作成するマクロ。"""

    # 同じアドレスに相対ジャンプする
    b.label("__LOOP_INFINITE__")
    JR(b, "__LOOP_INFINITE__")

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
