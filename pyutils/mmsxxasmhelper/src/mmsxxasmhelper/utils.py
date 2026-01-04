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
    "embed_debug_string_macro",
    "debug_print_pc",
    "print_bytes",
    "MemAddrAllocator",
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


def create_rng_seed_func(
    rng_state_addr: int,
    preserve_reg_bc: bool = True,
    *,
    group: str = DEFAULT_FUNC_GROUP_NAME,
):
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

    return Func("create_rng_seed", _create_rng_seed, group=group)


def rng_next_func(
    rng_state_addr: int,
    preserve_reg_bc: bool = True,
    *,
    group: str = DEFAULT_FUNC_GROUP_NAME,
) -> Func:
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

    return Func("rng_next", _rng_next, group=group)


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
# デバッグ用に任意の文字列を埋め込む
#

def embed_debug_string_macro(b: Block, text: str, *, with_nops: bool = True, encoding: str = "ascii") -> None:
    """任意の文字列をコードに埋め込むデバッグマクロ。

    文字列の直前に文字列終端へのジャンプを挿入するため、
    任意の位置に配置しても実行フローへ影響を与えない。
    デバッグ時のメモリダンプで位置を把握しやすくする用途を想定している。
    """

    end_label = unique_label("debugstr_end")
    JP(b, end_label)
    if with_nops:
        NOP(b)
    string_pos = b.pc
    string_bytes = str_bytes(text, encoding)
    DB(b, *string_bytes)
    if with_nops:
        NOP(b)
    b.label(end_label)
    break_pos = b.pc

    _register_debug_string(b, text, break_pos, string_pos, len(string_bytes))


def _register_debug_string(b: Block, text: str, break_pos: int, offset: int, length: int) -> None:
    entries = getattr(b, "_embedded_debug_strings", None)
    if entries is None:
        entries = []
        setattr(b, "_embedded_debug_strings", entries)

    entries.append((text, break_pos, offset, length))

    if getattr(b, "_embedded_debug_strings_registered", False):
        return

    def _print_debug_strings(block: Block, origin: int) -> None:
        if not DEBUG:
            return

        embedded = getattr(block, "_embedded_debug_strings", ())
        if not embedded:
            return

        print("Embedded debug strings:")
        for string, break_pos_addr, relative_offset, length in embedded:
            break_pos_addr = origin + break_pos_addr
            relative_end = relative_offset + max(length - 1, 0)
            absolute_start = origin + relative_offset
            absolute_end = origin + relative_end
            print(
                f"BP:{break_pos_addr:04X} {absolute_start:04X} ~ {absolute_end:04X}"
                f"(+{relative_offset:04X} ~ +{relative_end:04X} ): {string}"
            )

    b._finalize_callbacks.append(_print_debug_strings)
    setattr(b, "_embedded_debug_strings_registered", True)


def debug_print_pc(b: Block, name: str) -> None:
    """finalize 後に呼び出し位置のアドレスを名前付きで表示するデバッグヘルパー。

    ブレークポイント設定の目印として使用することを想定している。
    """

    pos = b.pc

    def _print_pc(block: Block, origin: int) -> None:
        if not DEBUG:
            return

        absolute = origin + pos
        print(f"BP {name}: {absolute:04X} (+{pos:04X})")

    b._finalize_callbacks.append(_print_pc)


#
# finalize 後に決定したラベルアドレスを表示するデバッグ用ヘルパー
#

def debug_print_labels(
    b: Block,
    origin: int = 0,
    *,
    stream=None,
    no_print: bool = False,
    include_offset: bool = False,
) -> str:
    """
    finalize 後に決定したラベルアドレスをダンプする。
    :param b: Block
    :param origin: アドレスの基点
    :param stream:
    :param no_print: print しない（でテキストだけ得る）
    :param include_offset: オフセットも併記する
    """

    if not DEBUG:
        return ""

    if stream is None:
        import sys

        stream = sys.stdout

    messages = []
    for name, offset in sorted(b.labels.items(), key=lambda item: item[1]):
        absolute = origin + offset
        if include_offset:
            message = f"{absolute:04X} (+{offset:04X}): {name}"
        else:
            message = f"{absolute:04X}: {name}"
        messages.append(message)
        if not no_print:
            print(message, file=stream)

    return "\n".join(messages)


#
# ---------------------------------------------------------------------------
# 便利python関数
# ---------------------------------------------------------------------------

def print_bytes(data: bytes, step: int = 16, address: int | None = 0, title: str = "") -> None:
    if title:
        print(title)
    for i in range(0, len(data), step):
        chunk = data[i:i + step]
        chunk = ' '.join(f'{b:02x}' for b in chunk)
        if address is not None:
            chunk = f"{address: 05x}: {chunk}"
            address += step
        print(chunk)


class MemAddrAllocator:
    """メモリアドレスを順次管理するユーティリティ。"""

    def __init__(self, base_address: int) -> None:
        self._base_address = base_address
        self._current_address = base_address
        self._allocated: list[str] = []
        self._lookup: dict[str, dict[str, object]] = {}

        self._initial_bytes = bytearray()

    def _ensure_capacity(self, address: int, size: int) -> int:
        offset = address - self._base_address
        required = offset + size
        if len(self._initial_bytes) < required:
            self._initial_bytes.extend([0x00] * (required - len(self._initial_bytes)))
        return offset

    def _normalize_initial_value(self, value: object) -> list[int]:
        if isinstance(value, (bytes, bytearray)):
            return list(value)

        msg = "initial value must be bytes or bytearray"
        raise TypeError(msg)

    def add(
        self,
        name: str,
        size: int | None = None,
        initial_value: bytes | bytearray | None = None,
        description: str = "",
    ) -> int:
        """名前とサイズを登録し、割り当て先アドレスを返す。

        例: ``allocator.add("BUFFER", 4, initial_value=b"\x01\x02\x03\x04", description="作業領域")``
        """

        if name in self._lookup:
            msg = f"{name!r} is already allocated"
            raise ValueError(msg)

        raw: list[int] | None = None
        value_length: int | None = None
        if initial_value is not None:
            raw = self._normalize_initial_value(initial_value)
            value_length = len(raw)

        if size is None and value_length is None:
            msg = "size or initial_value is required"
            raise ValueError(msg)

        if size is None:
            size = value_length
        elif value_length is not None and size != value_length:
            msg = (f"size ({size}) does not match initial value length ({value_length}),"
                   f" name: {name} value:{initial_value} raw:{raw})")
            raise ValueError(msg)

        assert size is not None

        if raw is None:
            raw = []
            value_length = 0

        address = self._current_address
        self._allocated.append(name)
        raw_initial_value = raw if raw else [0x00] * size
        self._lookup[name] = {
            "address": address,
            "size": size,
            "description": description,
            "initial_value": bytes(raw_initial_value),
        }
        self._current_address += size

        offset = self._ensure_capacity(address, size)
        if raw is not None:
            self._initial_bytes[offset : offset + len(raw)] = raw

        return address

    def get(self, name: str) -> int:
        """登録済みの名前を指定してアドレスを取得する。"""

        try:
            return self._lookup[name]["address"]  # type: ignore[index]
        except KeyError as exc:  # pragma: no cover - simple passthrough
            raise KeyError(name) from exc

    def debug_print(self) -> None:
        """登録済みの名前とアドレスを出力する。"""
        print(self.as_str())

    def as_str(self) -> str:
        s = ""
        for index, name in enumerate(self._allocated):
            entry = self._lookup[name]
            address = entry["address"]
            size = entry["size"]
            desc = entry["description"]
            initial = entry["initial_value"]

            desc_text = f" # {desc}" if desc else ""
            initial_hex = " ".join(f"{byte:02X}" for byte in initial)
            s += (
                f"[{index:02d}] {address:05X}h: {name} (size={size}, initial=[{initial_hex}])"
                f"{desc_text}\n"
            )
        return s

    @property
    def initial_bytes(self) -> bytes:
        """初期値が設定されたバイト列（未設定は 0 埋め）を返す。"""

        return bytes(self._initial_bytes)

    @property
    def total_size(self) -> int:
        """割り当て済み領域の全サイズを返す。"""

        return self._current_address - self._base_address

    def write_initial_values(self, target: bytearray) -> None:
        """保持している初期値を ``target`` に書き込む。"""

        if len(target) < self.total_size:
            msg = "target buffer is too small to receive initial values"
            raise ValueError(msg)

        target[: self.total_size] = self._initial_bytes[: self.total_size]