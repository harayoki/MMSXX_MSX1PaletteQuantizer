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
    "ldir_macro",
    "loop_infinite_macro",
    "set_debug",
    "debug_trap",
    "debug_print_labels",
    "print_bytes",
    "with_register_preserve",
]

P = ParamSpec("P")



def with_register_preserve(
    macro: Callable[Concatenate[Block, P], None]
) -> Callable[Concatenate[Block, P], None]:
    """マクロ呼び出しの前後に PUSH/POP を挿入するデコレータ。
    ``regs_preserve`` キーワード引数で退避するレジスタを指定できる。
    何も指定しなければ PUSH/POP は行われない。

    @with_register_preserveの記述をマクロ関数に記述すると有効になるが
    どのレジスタを保護するのあユーザーに細かくゆだねたい場合以外は使わない方針
    各マクロでPUSH POP対応を行う 理由は呼び出し元でどのレジスタを保護すべきか考えさせたくないため

    """

    @wraps(macro)
    def wrapper(
        b: Block,
        *args: P.args,
        regs_preserve: Sequence[RegNames16] = (),
        **kwargs: P.kwargs,
    ) -> None:
        regs = tuple(regs_preserve)
        for reg in regs:
            PUSH.r(b, reg)

        macro(b, *args, **kwargs)

        for reg in reversed(regs):
            POP.r(b, reg)

    return wrapper


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
    JR_n8(b, -1)


@with_register_preserve
def ldir_macro(
    b: Block,
    *,
    source_HL: int | None = None,
    dest_DE: int | None = None,
    length_BC: int | None = None,
    regs_preserve: Sequence[RegNames16] = ()
) -> None:
    """LDIR を呼び出すマクロ。
    HL:元アドレス, DE:VRAM先頭, BC:バイト数 を引数で上書きできる。
    いずれも ``None`` の場合は呼び出し元でレジスタが適切にセットされて
    いる前提で、そのまま BIOS コールだけを行う。
    レジスタ変更: HL, DE, BC（引数指定時に上書き）。BIOS 呼び出しによって
    AF/BC/DE/HL が破壊される前提で使用する。
    """

    if source_HL is not None:
        LD.HL_n16(b, source_HL & 0xFFFF)

    if dest_DE is not None:
        LD.DE_n16(b, dest_DE & 0xFFFF)

    if length_BC is not None:
        LD.BC_n16(b, length_BC & 0xFFFF)

    LDIR(b)


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


#
# finalize 後に決定したラベルアドレスを表示するデバッグ用ヘルパー
#

def debug_print_labels(b: Block, origin: int = 0, *, stream=None, no_print: bool = False) -> str:
    """
    finalize 後に決定したラベルアドレスをダンプする。
    :param b: Block
    :param origin:
    :param stream:
    :param no_print: print しない（でテキストだけ得る）
    """

    if not DEBUG:
        return ""

    if stream is None:
        import sys

        stream = sys.stdout

    messages = []
    for name, offset in sorted(b.labels.items(), key=lambda item: item[1]):
        message = f"{origin + offset:04x}: {name}"
        messages.append(message)
        if not no_print:
            print(message, file=stream)

    return "\n".join(messages)


#
# ---------------------------------------------------------------------------
# 便利python関数
# ---------------------------------------------------------------------------

def print_bytes(data: bytes, step: int = 16, address: int | None = 0) -> None:
    for i in range(0, len(data), step):
        chunk = data[i:i + step]
        chunk = ' '.join(f'{b:02x}' for b in chunk)
        if address is not None:
            chunk = f"{address: 05x}: {chunk}"
            address += step
        print(chunk)
