"""
Z80用ミニアセンブラ v0
mmsxxasmhelper/core.py

v0で入っている機能:

- Block: コード構築用の基本クラス
  - emit(*bytes): バイト列を追加し、先頭位置を返す
  - pc: 現在のオフセット(バイト数)
  - label(name): 現在位置にラベルを張る
  - fixups: 後で埋めるアドレス情報(JP/CALL用)
  - finalize(origin=0): fixupを解決してbytesを返す

- 定数テーブル:
  - const(name, value): 定数登録
  - Const[name] で参照

- 定数データ列 (バイト列 / ワード列)
    - TBW

- 文字列 → バイト列 変換
    - TBW

- マクロ:
  - 単なる `def macro(b: Block, ...)` のPython関数として扱う

- ブロック調整
    - TBW

- 関数(Func): CALLで呼び出す用のラッパ
  - Func(name, body)
  - .define(b): ラベル + body + RET を出力
  - .call(b): CALL 命令を出力(アドレスはfixupで解決)

- 命令ラッパ:
  - JP 系: 無条件/条件付き絶対ジャンプ (JP, JP_Z, JP_NZ, JP_NC, JP_C, JP_PO, JP_PE, JP_P, JP_M, JP_mHL)
  - JR 系: 無条件/条件付き相対ジャンプ (JR, JR_Z, JR_NZ, JR_NC, JR_C) および DJNZ
  - CALL(b, label): CALL label

- データ配置:
  - DB(b, *values): 1バイト列を配置
  - DW(b, *values): 16bit値(リトルエンディアン)を配置

- DEBUGフラグ:
  - DEBUG = True/False
  - debug_trap(b): DEBUG時のみデバッグ用命令を挿入
"""

from __future__ import annotations
from collections.abc import Iterable

__all__ = [
    "Block", "Fixup", "const", "Const",
    "Data8", "Data16", "RegNames16",
    "const_bytes", "const_words",
    "db_const", "dw_const", "db_from_bytes",
    "str_bytes", "const_string",
    "pad_bytes", "const_bytes_padded",
    "pad_pattern",
    "JP", "JP_Z", "JP_NZ", "JP_NC", "JP_C", "JP_PO", "JP_PE", "JP_P", "JP_M", "JP_mHL",
    "JR", "JR_NZ", "JR_Z", "JR_NC", "JR_C", "JR_n8", "DJNZ",
    "CALL_label", "CALL",
    "RET", "RET_NZ", "RET_Z", "RET_NC", "RET_C", "RET_PO", "RET_PE", "RET_P", "RET_M",
    "Func",
    "DB", "DW",
    "LD", "ADD", "SUB", "CP", "AND", "OR", "XOR",
    "RLCA",
    "INC", "DEC",
    "OUT", "OUT_A", "OUT_C",
    "PUSH", "POP",
    "NOP", "HALT", "DI", "EI",
]

from dataclasses import dataclass
from typing import Callable, Dict, List, Literal


# ---------------------------------------------------------------------------
# Block: コード構築の基本単位
# ---------------------------------------------------------------------------

FixupKind = Literal["abs16", "rel8"]  # v0では絶対16bitアドレスと相対8bitのみ扱う


@dataclass
class Fixup:
    """後でアドレスを書き込むための情報。

    kind:   "abs16" 固定 (JP/CALL 共通)
    pos:    下位バイトを書き込む位置(コード内インデックス)
    target: ラベル名
    """

    kind: FixupKind
    pos: int
    target: str


class Block:
    """Z80コード(とそのメタ情報)を貯める箱。"""

    def __init__(self) -> None:
        self.code = bytearray()
        self.pc: int = 0
        self.labels: Dict[str, int] = {}
        self.fixups: List[Fixup] = []

    # --- 基本出力 ---

    def emit(self, *bs: int) -> int:
        """バイト列を追加し、先頭の位置(pc)を返す。"""

        pos = self.pc
        for b in bs:
            self.code.append(b & 0xFF)
            self.pc += 1
        return pos

    def label(self, name: str) -> None:
        """現在位置にラベルを張る。再定義はエラー。"""

        if name in self.labels:
            raise ValueError(f"label redefined: {name}")
        self.labels[name] = self.pc

    # --- fixup 登録 ---

    def add_abs16_fixup(self, pos: int, target: str) -> None:
        """16bitアドレスを書き込むためのfixupを登録。

        pos: 下位バイトを書き込む位置
        """

        self.fixups.append(Fixup(kind="abs16", pos=pos, target=target))

    def add_rel8_fixup(self, pos: int, target: str) -> None:
        """8bit相対オフセットを書き込むためのfixupを登録。

        pos: オフセットを書き込む位置（この1バイトの直後が基準アドレス）。
        """

        self.fixups.append(Fixup(kind="rel8", pos=pos, target=target))

    # --- 出力確定 ---

    def finalize(self, origin: int = 0) -> bytes:
        """fixupを解決してバイト列を返す。

        origin はこの Block をメモリ上のどこに配置するかのベースアドレス。
        v0 では単一ブロック前提なので任意指定でOK。
        """

        for fx in self.fixups:
            if fx.kind == "abs16":
                # fx.pos が下位バイト、fx.pos+1 が上位バイト
                addr = origin + self._get_label_addr(fx.target)
                lo = addr & 0xFF
                hi = (addr >> 8) & 0xFF
                self.code[fx.pos] = lo
                self.code[fx.pos + 1] = hi
            elif fx.kind == "rel8":
                base = origin + fx.pos + 1  # 相対オフセットの基準 (次命令のアドレス)
                target = origin + self._get_label_addr(fx.target)
                offset = target - base
                if not -128 <= offset <= 127:
                    raise ValueError(
                        f"relative jump out of range: target={fx.target}, offset={offset}")
                self.code[fx.pos] = offset & 0xFF
            else:
                raise ValueError(f"unknown fixup kind: {fx.kind}")

        return bytes(self.code)

    def _get_label_addr(self, name: str) -> int:
        try:
            return self.labels[name]
        except KeyError as exc:
            raise ValueError(f"undefined label: {name}") from exc


# ---------------------------------------------------------------------------
# 定数テーブル
# ---------------------------------------------------------------------------

Const: Dict[str, int] = {}


def const(name: str, value: int) -> None:
    """定数を登録する。再定義はエラー。"""

    if name in Const:
        raise ValueError(f"const redefined: {name}")
    Const[name] = value

# ---------------------------------------------------------------------------
# 定数データ列 (バイト列 / ワード列)
# ---------------------------------------------------------------------------


Data8: Dict[str, List[int]] = {}
Data16: Dict[str, List[int]] = {}


def const_bytes(name: str, *values: int) -> None:
    """
    名前付きバイト列を登録する。

    例:
        const_bytes("LOGO", 0x01, 0x02, 0x03)
    """
    if name in Data8:
        raise ValueError(f"byte data redefined: {name}")
    Data8[name] = [v & 0xFF for v in values]


def const_words(name: str, *values: int) -> None:
    """
    名前付きワード列(16bit)を登録する。

    例:
        const_words("PALETTE", 0x1234, 0xABCD)
    """
    if name in Data16:
        raise ValueError(f"word data redefined: {name}")
    Data16[name] = [v & 0xFFFF for v in values]


def db_const(b: Block, name: str) -> None:
    """
    const_bytes で登録したデータをそのまま db で吐く。
    """
    try:
        data = Data8[name]
    except KeyError as exc:
        raise ValueError(f"unknown byte data name: {name}") from exc
    DB(b, *data)


def dw_const(b: Block, name: str) -> None:
    """
    const_words で登録したデータをそのまま dw で吐く。
    """
    try:
        data = Data16[name]
    except KeyError as exc:
        raise ValueError(f"unknown word data name: {name}") from exc
    DW(b, *data)


def db_from_bytes(b: Block, data):
    """
    Block に大量のバイト列を突っ込むユーティリティ。

    data:
        - bytes / bytearray
        - list[int] / tuple[int, ...]
        - str なら Data8[name] を引く
    """
    # 名前で指定された場合は Data8 から探す
    if isinstance(data, str):
        if data not in Data8:
            raise KeyError(f"db_from_bytes: const '{data}' not found in Data8")
        DB(b, *Data8[data])
        return

    # 素のバイト列
    if isinstance(data, (bytes, bytearray)):
        DB(b, *data)
        return

    # int の並び（list, tuple 等）
    if isinstance(data, Iterable):
        vals = list(data)
        if not all(isinstance(v, int) for v in vals):
            raise TypeError("db_from_bytes: iterable must contain ints")
        DB(b, *vals)
        return

    raise TypeError("db_from_bytes: unsupported data type")


# ---------------------------------------------------------------------------
# 文字列 → バイト列 変換
# ---------------------------------------------------------------------------

def str_bytes(text: str, encoding: str = "ascii") -> List[int]:
    """
    文字列をバイト列に変換して List[int] で返す。
    MSX の SCREEN2/BIOS 文字コードは ASCII と同じなので encoding="ascii" のままでOK。

    例:
        str_bytes("HELLO") → [0x48, 0x45, 0x4C, 0x4C, 0x4F]
    """
    raw = text.encode(encoding, errors="strict")
    return [b for b in raw]


def const_string(name: str, text: str, encoding: str = "ascii") -> None:
    """
    文字列をそのまま const_bytes に登録する便利関数。
    例:
        const_string("TITLE", "HELLO!")
    """
    bs = str_bytes(text, encoding)
    const_bytes(name, *bs)


def pad_bytes(values: List[int], size: int, fill: int = 0x00) -> List[int]:
    """
    バイト列 values を size バイトになるまで fill で後ろに埋める。

    例:
        pad_bytes([1,2,3], 8) → [1,2,3,0,0,0,0,0]
        pad_bytes([0x41], 4, 0x20) → [0x41,0x20,0x20,0x20]
    """
    if len(values) > size:
        raise ValueError(f"pad_bytes: input length {len(values)} > size {size}")
    return values + [fill & 0xFF] * (size - len(values))


def const_bytes_padded(name: str, size: int, fill: int = 0x00, *values: int) -> None:
    """
    const_bytes の固定長版。

    例:
        const_bytes_padded("NAME16", 16, 0x20, *str_bytes("MSX"))
        → 'MSX' の後をスペースで16バイトまで埋める
    """
    padded = pad_bytes(list(values), size, fill)
    const_bytes(name, *padded)


# ---------------------------------------------------------------------------
# 命令ラッパ (v0: ジャンプ / コール)
# ---------------------------------------------------------------------------


def _jp_abs16(b: Block, opcode: int, target: str) -> None:
    pos = b.emit(opcode, 0x00, 0x00)
    b.add_abs16_fixup(pos + 1, target)


def _jr_rel8(b: Block, opcode: int, target: str) -> None:
    pos = b.emit(opcode, 0x00)
    b.add_rel8_fixup(pos + 1, target)


def JP(b: Block, target: str) -> None:
    """JP target (無条件絶対ジャンプ)。"""

    _jp_abs16(b, 0xC3, target)


def JP_NZ(b: Block, target: str) -> None:
    """JP NZ,target (Z=0)。"""

    _jp_abs16(b, 0xC2, target)


def JP_Z(b: Block, target: str) -> None:
    """JP Z,target (Z=1)。"""

    _jp_abs16(b, 0xCA, target)


def JP_NC(b: Block, target: str) -> None:
    """JP NC,target (C=0)。"""

    _jp_abs16(b, 0xD2, target)


def JP_C(b: Block, target: str) -> None:
    """JP C,target (C=1)。"""

    _jp_abs16(b, 0xDA, target)


def JP_PO(b: Block, target: str) -> None:
    """JP PO,target (パリティオーバーフロー=0)。"""

    _jp_abs16(b, 0xE2, target)


def JP_PE(b: Block, target: str) -> None:
    """JP PE,target (パリティオーバーフロー=1)。"""

    _jp_abs16(b, 0xEA, target)


def JP_P(b: Block, target: str) -> None:
    """JP P,target (符号フラグ=0)。"""

    _jp_abs16(b, 0xF2, target)


def JP_M(b: Block, target: str) -> None:
    """JP M,target (符号フラグ=1)。"""

    _jp_abs16(b, 0xFA, target)


def JP_mHL(b: Block) -> None:
    """JP (HL) (HLが指すアドレスへジャンプ)。"""
    b.emit(0xE9)


def JR(b: Block, target: str) -> None:
    """JR target (無条件相対ジャンプ)。"""

    _jr_rel8(b, 0x18, target)


def JR_NZ(b: Block, target: str) -> None:
    """JR NZ,target (Z=0)。"""

    _jr_rel8(b, 0x20, target)


def JR_Z(b: Block, target: str) -> None:
    """JR Z,target (Z=1)。"""

    _jr_rel8(b, 0x28, target)


def JR_NC(b: Block, target: str) -> None:
    """JR NC,target (C=0)。"""

    _jr_rel8(b, 0x30, target)


def JR_C(b: Block, target: str) -> None:
    """JR C,target (C=1)。"""

    _jr_rel8(b, 0x38, target)


def JR_n8(b: Block, offset: int) -> None:
    """JRの相対ジャンプ"""
    if offset < 0:
        offset = 0xFF + offset
    b.emit(0x18, offset)


def DJNZ(b: Block, target: str) -> None:
    """DJNZ target (Bをデクリメントし非ゼロなら相対ジャンプ)。"""

    _jr_rel8(b, 0x10, target)


def CALL_label(b: Block, target: str) -> None:
    """
    CALL（ラベル指定版）
    """
    # CALL nn (opcode 0xCD, nn = 16bit)
    pos = b.emit(0xCD, 0x00, 0x00)
    b.add_abs16_fixup(pos + 1, target)


def CALL(b: Block, address: int) -> None:
    """
    CALL nn (即値アドレス指定版)
    """
    b.emit(0xCD, address & 0xFF, (address >> 8) & 0xFF)


def RET(b: Block) -> None:
    b.emit(0xC9)


def RET_NZ(b: Block) -> None:
    b.emit(0xC0)


def RET_Z(b: Block) -> None:
    b.emit(0xC8)


def RET_NC(b: Block) -> None:
    b.emit(0xD0)


def RET_C(b: Block) -> None:
    b.emit(0xD8)


def RET_PO(b: Block) -> None:
    b.emit(0xE0)


def RET_PE(b: Block) -> None:
    b.emit(0xE8)


def RET_P(b: Block) -> None:
    b.emit(0xF0)


def RET_M(b: Block) -> None:
    b.emit(0x0F8)


# ---------------------------------------------------------------------------
# ブロック調整
# ---------------------------------------------------------------------------

def pad_pattern(b: Block, to_size: int, pattern: int):
    """
    パターン埋め
    ROMサイズに合わせるなどの用途の場合はfinalize後に手動でやる事を推奨
    """
    cur = b.pc
    need = to_size - cur
    if need > 0:
        for _ in range(need):
            b.emit(pattern & 0xFF)


# ---------------------------------------------------------------------------
# Func: CALLで呼ぶサブルーチン表現
# ---------------------------------------------------------------------------

Body = Callable[[Block], None]


class Func:
    """CALL可能な関数を表す薄いラッパ。"""

    def __init__(self, name: str, body: Body) -> None:
        self.name = name
        self.body = body

    def define(self, b: Block) -> None:
        """関数本体を配置する (label + body + RET)。"""

        b.label(self.name)
        self.body(b)
        # RET
        b.emit(0xC9)

    def call(self, b: Block) -> None:
        """CALL命令を発行。"""

        CALL_label(b, self.name)


# ---------------------------------------------------------------------------
# LD 命令（大文字=レジスタ，mXX=メモリアドレス，n8/n16=即値）
# ---------------------------------------------------------------------------

class LD:
    """LD 系命令。

    命名規則:
        - 大文字: レジスタ（A, B, C, D, E, H, L, HL, BC, DE, SP, IX, IY など）
        - m + レジスタ名: そのレジスタを使ったメモリアクセス
            - mHL  = (HL)
            - mBC  = (BC)
            - mDE  = (DE)
            - mIXd = (IX+d)
            - mIYd = (IY+d)
        - n8 / n16: 即値8bit / 即値16bit
    """

    # 8bitレジスタインデックス (LD r,r' 用)
    _REG8_INDEX = {
        "B": 0,
        "C": 1,
        "D": 2,
        "E": 3,
        "H": 4,
        "L": 5,
        "mHL": 6,  # (HL)
        "A": 7,
    }

    @staticmethod
    def rr(b: Block, dst: str, src: str) -> None:
        """8bitレジスタ間 LD r,r' / LD r,(HL) / LD (HL),r。

        dst, src は "A","B","C","D","E","H","L","mHL" のいずれか。
        """

        try:
            d = LD._REG8_INDEX[dst]
            s = LD._REG8_INDEX[src]
        except KeyError as exc:
            raise ValueError(f"invalid LD rr operands: {dst}, {src}") from exc
        opcode = 0x40 | (d << 3) | s
        b.emit(opcode)

    # ---- A レジスタへのロード（レジスタ版） ----

    @staticmethod
    def A_B(b: Block) -> None:
        """LD A,B"""
        LD.rr(b, "A", "B")

    @staticmethod
    def A_C(b: Block) -> None:
        """LD A,C"""
        LD.rr(b, "A", "C")

    @staticmethod
    def A_D(b: Block) -> None:
        """LD A,D"""

        LD.rr(b, "A", "D")

    @staticmethod
    def A_E(b: Block) -> None:
        """LD A,E"""
        LD.rr(b, "A", "E")

    @staticmethod
    def A_H(b: Block) -> None:
        """LD A,H"""
        LD.rr(b, "A", "H")

    @staticmethod
    def A_L(b: Block) -> None:
        """LD A,L"""
        LD.rr(b, "A", "L")

    @staticmethod
    def A_A(b: Block) -> None:
        """LD A,A"""
        LD.rr(b, "A", "A")

    @staticmethod
    def B_A(b: Block) -> None:
        """LD B,A"""
        LD.rr(b, "B", "A")

    @staticmethod
    def C_A(b: Block) -> None:
        """LD C,A"""
        LD.rr(b, "C", "A")

    @staticmethod
    def D_A(b: Block) -> None:
        """LD D,A"""
        LD.rr(b, "D", "A")

    @staticmethod
    def D_B(b: Block) -> None:
        """LD D,A"""
        LD.rr(b, "D", "B")

    @staticmethod
    def D_H(b: Block) -> None:
        """LD D,H"""
        LD.rr(b, "D", "H")

    @staticmethod
    def E_A(b: Block) -> None:
        """LD E,A"""
        LD.rr(b, "E", "A")

    @staticmethod
    def E_L(b: Block) -> None:
        """LD E,L"""
        LD.rr(b, "E", "L")

    @staticmethod
    def H_A(b: Block) -> None:
        """LD H,A"""
        LD.rr(b, "H", "A")

    @staticmethod
    def H_B(b: Block) -> None:
        """LD H,B"""
        LD.rr(b, "H", "B")

    @staticmethod
    def L_C(b: Block) -> None:
        """LD L,C"""
        LD.rr(b, "L", "C")


    # TODO その他 レジスタ間のLDは必要時に増やしていく

    # ---- 8bit 即値ロード ----

    @staticmethod
    def A_n8(b: Block, value: int) -> None:
        """LD A,n8"""
        b.emit(0x3E, value & 0xFF)

    @staticmethod
    def B_n8(b: Block, value: int) -> None:
        """LD B,n8"""
        b.emit(0x06, value & 0xFF)

    @staticmethod
    def C_n8(b: Block, value: int) -> None:
        """LD C,n8"""
        b.emit(0x0E, value & 0xFF)

    @staticmethod
    def D_n8(b: Block, value: int) -> None:
        """LD D,n8"""
        b.emit(0x16, value & 0xFF)

    @staticmethod
    def E_n8(b: Block, value: int) -> None:
        """LD E,n8"""
        b.emit(0x1E, value & 0xFF)

    @staticmethod
    def H_n8(b: Block, value: int) -> None:
        """LD H,n8"""
        b.emit(0x26, value & 0xFF)

    @staticmethod
    def L_n8(b: Block, value: int) -> None:
        """LD L,n8"""
        b.emit(0x2E, value & 0xFF)

    # (HL),n8
    @staticmethod
    def mHL_n8(b: Block, value: int) -> None:
        """LD (HL),n8"""
        b.emit(0x36, value & 0xFF)

    # ---- 16bit 即値ロード (レジスタペア / インデックスレジスタ) ----

    @staticmethod
    def BC_n16(b: Block, value: int) -> None:
        """LD BC,n16"""
        lo = value & 0xFF
        hi = (value >> 8) & 0xFF
        b.emit(0x01, lo, hi)

    @staticmethod
    def DE_n16(b: Block, value: int) -> None:
        """LD DE,n16"""
        lo = value & 0xFF
        hi = (value >> 8) & 0xFF
        b.emit(0x11, lo, hi)

    @staticmethod
    def HL_n16(b: Block, value: int) -> None:
        """LD HL,n16"""
        lo = value & 0xFF
        hi = (value >> 8) & 0xFF
        b.emit(0x21, lo, hi)

    @staticmethod
    def SP_n16(b: Block, value: int) -> None:
        """LD SP,n16"""
        lo = value & 0xFF
        hi = (value >> 8) & 0xFF
        b.emit(0x31, lo, hi)

    @staticmethod
    def IX_n16(b: Block, value: int) -> None:
        """LD IX,n16"""
        lo = value & 0xFF
        hi = (value >> 8) & 0xFF
        b.emit(0xDD, 0x21, lo, hi)

    @staticmethod
    def IY_n16(b: Block, value: int) -> None:
        """LD IY,n16"""
        lo = value & 0xFF
        hi = (value >> 8) & 0xFF
        b.emit(0xFD, 0x21, lo, hi)

    # ---- (HL)・(BC)・(DE) 系 ----

    @staticmethod
    def mHL_A(b: Block) -> None:
        """LD (HL),A"""
        b.emit(0x77)

    @staticmethod
    def A_mHL(b: Block) -> None:
        """LD A,(HL)"""
        b.emit(0x7E)

    @staticmethod
    def B_mHL(b: Block) -> None:
        """LD B,(HL)"""
        b.emit(0x46)
    @staticmethod
    def C_mHL(b: Block) -> None:
        """LD C,(HL)"""
        b.emit(0x4E)
    @staticmethod
    def D_mHL(b: Block) -> None:
        """LD D,(HL)"""
        b.emit(0x56)
    @staticmethod
    def E_mHL(b: Block) -> None:
        """LD E,(HL)"""
        b.emit(0x5E)
    @staticmethod
    def H_mHL(b: Block) -> None:
        """LD H,(HL)"""
        b.emit(0x66)
    @staticmethod
    def L_mHL(b: Block) -> None:
        """LD L,(HL)"""
        b.emit(0x6E)

    @staticmethod
    def mBC_A(b: Block) -> None:
        """LD (BC),A"""
        b.emit(0x02)

    @staticmethod
    def mDE_A(b: Block) -> None:
        """LD (DE),A"""
        b.emit(0x12)

    @staticmethod
    def A_mBC(b: Block) -> None:
        """LD A,(BC)"""
        b.emit(0x0A)

    @staticmethod
    def A_mDE(b: Block) -> None:
        """LD A,(DE)"""
        b.emit(0x1A)

    # ---- (nn) とのロード ----

    @staticmethod
    def A_mn16(b: Block, addr: int) -> None:
        """LD A,(nn)"""
        lo = addr & 0xFF
        hi = (addr >> 8) & 0xFF
        b.emit(0x3A, lo, hi)

    @staticmethod
    def mn16_A(b: Block, addr: int) -> None:
        """LD (nn),A"""
        lo = addr & 0xFF
        hi = (addr >> 8) & 0xFF
        b.emit(0x32, lo, hi)

    @staticmethod
    def HL_mn16(b: Block, addr: int) -> None:
        """LD HL,(nn)"""
        lo = addr & 0xFF
        hi = (addr >> 8) & 0xFF
        b.emit(0x2A, lo, hi)

    @staticmethod
    def mn16_HL(b: Block, addr: int) -> None:
        """LD (nn),HL"""
        lo = addr & 0xFF
        hi = (addr >> 8) & 0xFF
        b.emit(0x22, lo, hi)

    @staticmethod
    def IX_mn16(b: Block, addr: int) -> None:
        """LD IX,(nn)"""
        lo = addr & 0xFF
        hi = (addr >> 8) & 0xFF
        b.emit(0xDD, 0x2A, lo, hi)

    @staticmethod
    def mn16_IX(b: Block, addr: int) -> None:
        """LD (nn),IX"""
        lo = addr & 0xFF
        hi = (addr >> 8) & 0xFF
        b.emit(0xDD, 0x22, lo, hi)

    @staticmethod
    def IY_mn16(b: Block, addr: int) -> None:
        """LD IY,(nn)"""
        lo = addr & 0xFF
        hi = (addr >> 8) & 0xFF
        b.emit(0xFD, 0x2A, lo, hi)

    @staticmethod
    def mn16_IY(b: Block, addr: int) -> None:
        """LD (nn),IY"""
        lo = addr & 0xFF
        hi = (addr >> 8) & 0xFF
        b.emit(0xFD, 0x22, lo, hi)

    # ---- SP 関連 ----

    @staticmethod
    def SP_HL(b: Block) -> None:
        """LD SP,HL"""
        b.emit(0xF9)

    @staticmethod
    def SP_IX(b: Block) -> None:
        """LD SP,IX"""
        b.emit(0xDD, 0xF9)

    @staticmethod
    def SP_IY(b: Block) -> None:
        """LD SP,IY"""
        b.emit(0xFD, 0xF9)


    # ---------------------------------------------------------
    # IX / IY + d 版 LD
    # ---------------------------------------------------------

    @staticmethod
    def r_mIXd(b: Block, dst: str, disp: int) -> None:
        """
        LD dst,(IX+d)

        dst: "A","B","C","D","E","H","L" のいずれか
        """
        if dst == "mHL":
            raise ValueError("r_mIXd で mHL は使えない")
        try:
            idx = LD._REG8_INDEX[dst]
        except KeyError as exc:
            raise ValueError(f"invalid dst for LD r,(IX+d): {dst}") from exc
        opcode = 0x46 + (idx << 3)  # 0x46,4E,56,5E,66,6E,7E
        b.emit(0xDD, opcode, disp & 0xFF)

    @staticmethod
    def r_mIYd(b: Block, dst: str, disp: int) -> None:
        """
        LD dst,(IY+d)
        """
        if dst == "mHL":
            raise ValueError("r_mIYd で mHL は使えない")
        try:
            idx = LD._REG8_INDEX[dst]
        except KeyError as exc:
            raise ValueError(f"invalid dst for LD r,(IY+d): {dst}") from exc
        opcode = 0x46 + (idx << 3)
        b.emit(0xFD, opcode, disp & 0xFF)

    @staticmethod
    def mIXd_r(b: Block, disp: int, src: str) -> None:
        """
        LD (IX+d),src

        src: "A","B","C","D","E","H","L" のいずれか
        """
        if src == "mHL":
            raise ValueError("mIXd_r で mHL は使えない")
        try:
            idx = LD._REG8_INDEX[src]
        except KeyError as exc:
            raise ValueError(f"invalid src for LD (IX+d),r: {src}") from exc
        opcode = 0x70 + idx  # 0x70〜0x77 （idx=6 は mHL なので弾いている）
        b.emit(0xDD, opcode, disp & 0xFF)

    @staticmethod
    def mIYd_r(b: Block, disp: int, src: str) -> None:
        """
        LD (IY+d),src
        """
        if src == "mHL":
            raise ValueError("mIYd_r で mHL は使えない")
        try:
            idx = LD._REG8_INDEX[src]
        except KeyError as exc:
            raise ValueError(f"invalid src for LD (IY+d),r: {src}") from exc
        opcode = 0x70 + idx
        b.emit(0xFD, opcode, disp & 0xFF)

    @staticmethod
    def mIXd_n8(b: Block, disp: int, value: int) -> None:
        """
        LD (IX+d),n8
        """
        b.emit(0xDD, 0x36, disp & 0xFF, value & 0xFF)

    @staticmethod
    def mIYd_n8(b: Block, disp: int, value: int) -> None:
        """
        LD (IY+d),n8
        """
        b.emit(0xFD, 0x36, disp & 0xFF, value & 0xFF)

    @staticmethod
    def HL_label(b: Block, label: str) -> None:
        pos = b.emit(0x21, 0x00, 0x00)
        b.add_abs16_fixup(pos + 1, label)


# ---------------------------------------------------------------------------
# ADD 命令
# ---------------------------------------------------------------------------


class ADD:
    """ADD 系命令。"""

    @staticmethod
    def A_B(b: Block) -> None:
        """ADD A,B"""

        b.emit(0x80)

    @staticmethod
    def A_C(b: Block) -> None:
        """ADD A,C"""

        b.emit(0x81)

    @staticmethod
    def A_D(b: Block) -> None:
        """ADD A,D"""

        b.emit(0x82)

    @staticmethod
    def A_E(b: Block) -> None:
        """ADD A,E"""

        b.emit(0x83)

    @staticmethod
    def A_H(b: Block) -> None:
        """ADD A,H"""

        b.emit(0x84)

    @staticmethod
    def A_L(b: Block) -> None:
        """ADD A,L"""

        b.emit(0x85)

    @staticmethod
    def A_mHL(b: Block) -> None:
        """ADD A,(HL)"""

        b.emit(0x86)

    @staticmethod
    def A_A(b: Block) -> None:
        """ADD A,A"""

        b.emit(0x87)

    @staticmethod
    def A_mIXd(b: Block, disp: int) -> None:
        """ADD A,(IX+d)"""

        b.emit(0xDD, 0x86, disp & 0xFF)

    @staticmethod
    def A_mIYd(b: Block, disp: int) -> None:
        """ADD A,(IY+d)"""

        b.emit(0xFD, 0x86, disp & 0xFF)

    @staticmethod
    def A_n8(b: Block, value: int) -> None:
        """ADD A,n8"""

        b.emit(0xC6, value & 0xFF)

    @staticmethod
    def HL_BC(b: Block) -> None:
        """ADD HL,BC"""

        b.emit(0x09)

    @staticmethod
    def HL_DE(b: Block) -> None:
        """ADD HL,DE"""

        b.emit(0x19)

    @staticmethod
    def HL_HL(b: Block) -> None:
        """ADD HL,HL"""

        b.emit(0x29)

    @staticmethod
    def HL_SP(b: Block) -> None:
        """ADD HL,SP"""

        b.emit(0x39)

    @staticmethod
    def IX_BC(b: Block) -> None:
        """ADD IX,BC"""

        b.emit(0xDD, 0x09)

    @staticmethod
    def IX_DE(b: Block) -> None:
        """ADD IX,DE"""

        b.emit(0xDD, 0x19)

    @staticmethod
    def IX_IX(b: Block) -> None:
        """ADD IX,IX"""

        b.emit(0xDD, 0x29)

    @staticmethod
    def IX_SP(b: Block) -> None:
        """ADD IX,SP"""

        b.emit(0xDD, 0x39)

    @staticmethod
    def IY_BC(b: Block) -> None:
        """ADD IY,BC"""

        b.emit(0xFD, 0x09)

    @staticmethod
    def IY_DE(b: Block) -> None:
        """ADD IY,DE"""

        b.emit(0xFD, 0x19)

    @staticmethod
    def IY_IY(b: Block) -> None:
        """ADD IY,IY"""

        b.emit(0xFD, 0x29)

    @staticmethod
    def IY_SP(b: Block) -> None:
        """ADD IY,SP"""

        b.emit(0xFD, 0x39)


class SUB:

    @staticmethod
    def B(b: Block):
        b.emit(0x90)

    @staticmethod
    def C(b: Block):
        b.emit(0x91)

    @staticmethod
    def D(b: Block):
        b.emit(0x92)

    @staticmethod
    def E(b: Block):
        b.emit(0x93)

    @staticmethod
    def H(b: Block):
        b.emit(0x94)

    @staticmethod
    def L(b: Block):
        b.emit(0x95)

    @staticmethod
    def mHL(b: Block):
        b.emit(0x96)

    @staticmethod
    def A(b: Block):
        b.emit(0x97)


class CP:
    """CP 系命令。"""

    @staticmethod
    def B(b: Block) -> None:
        """CP B"""

        b.emit(0xB8)

    @staticmethod
    def C(b: Block) -> None:
        """CP C"""

        b.emit(0xB9)

    @staticmethod
    def D(b: Block) -> None:
        """CP D"""

        b.emit(0xBA)

    @staticmethod
    def E(b: Block) -> None:
        """CP E"""

        b.emit(0xBB)

    @staticmethod
    def H(b: Block) -> None:
        """CP H"""

        b.emit(0xBC)

    @staticmethod
    def L(b: Block) -> None:
        """CP L"""

        b.emit(0xBD)

    @staticmethod
    def mHL(b: Block) -> None:
        """CP (HL)"""

        b.emit(0xBE)

    @staticmethod
    def A(b: Block) -> None:
        """CP A"""

        b.emit(0xBF)

    @staticmethod
    def mIXd(b: Block, disp: int) -> None:
        """CP (IX+d)"""

        b.emit(0xDD, 0xBE, disp & 0xFF)

    @staticmethod
    def mIYd(b: Block, disp: int) -> None:
        """CP (IY+d)"""

        b.emit(0xFD, 0xBE, disp & 0xFF)

    @staticmethod
    def n8(b: Block, value: int) -> None:
        """CP n8"""

        b.emit(0xFE, value & 0xFF)


class AND:
    """AND 系命令。"""

    @staticmethod
    def B(b: Block) -> None:
        """AND B"""

        b.emit(0xA0)

    @staticmethod
    def C(b: Block) -> None:
        """AND C"""

        b.emit(0xA1)

    @staticmethod
    def D(b: Block) -> None:
        """AND D"""

        b.emit(0xA2)

    @staticmethod
    def E(b: Block) -> None:
        """AND E"""

        b.emit(0xA3)

    @staticmethod
    def H(b: Block) -> None:
        """AND H"""

        b.emit(0xA4)

    @staticmethod
    def L(b: Block) -> None:
        """AND L"""

        b.emit(0xA5)

    @staticmethod
    def mHL(b: Block) -> None:
        """AND (HL)"""

        b.emit(0xA6)

    @staticmethod
    def A(b: Block) -> None:
        """AND A"""

        b.emit(0xA7)

    @staticmethod
    def mIXd(b: Block, disp: int) -> None:
        """AND (IX+d)"""

        b.emit(0xDD, 0xA6, disp & 0xFF)

    @staticmethod
    def mIYd(b: Block, disp: int) -> None:
        """AND (IY+d)"""

        b.emit(0xFD, 0xA6, disp & 0xFF)

    @staticmethod
    def n8(b: Block, value: int) -> None:
        """AND n8"""

        b.emit(0xE6, value & 0xFF)


class OR:
    """OR 系命令。"""

    @staticmethod
    def B(b: Block) -> None:
        """OR B"""

        b.emit(0xB0)

    @staticmethod
    def C(b: Block) -> None:
        """OR C"""

        b.emit(0xB1)

    @staticmethod
    def D(b: Block) -> None:
        """OR D"""

        b.emit(0xB2)

    @staticmethod
    def E(b: Block) -> None:
        """OR E"""

        b.emit(0xB3)

    @staticmethod
    def H(b: Block) -> None:
        """OR H"""

        b.emit(0xB4)

    @staticmethod
    def L(b: Block) -> None:
        """OR L"""

        b.emit(0xB5)

    @staticmethod
    def mHL(b: Block) -> None:
        """OR (HL)"""

        b.emit(0xB6)

    @staticmethod
    def A(b: Block) -> None:
        """OR A"""

        b.emit(0xB7)

    @staticmethod
    def mIXd(b: Block, disp: int) -> None:
        """OR (IX+d)"""

        b.emit(0xDD, 0xB6, disp & 0xFF)

    @staticmethod
    def mIYd(b: Block, disp: int) -> None:
        """OR (IY+d)"""

        b.emit(0xFD, 0xB6, disp & 0xFF)

    @staticmethod
    def n8(b: Block, value: int) -> None:
        """OR n8"""

        b.emit(0xF6, value & 0xFF)


class XOR:
    """XOR 系命令。"""

    @staticmethod
    def B(b: Block) -> None:
        """XOR B"""

        b.emit(0xA8)

    @staticmethod
    def C(b: Block) -> None:
        """XOR C"""

        b.emit(0xA9)

    @staticmethod
    def D(b: Block) -> None:
        """XOR D"""

        b.emit(0xAA)

    @staticmethod
    def E(b: Block) -> None:
        """XOR E"""

        b.emit(0xAB)

    @staticmethod
    def H(b: Block) -> None:
        """XOR H"""

        b.emit(0xAC)

    @staticmethod
    def L(b: Block) -> None:
        """XOR L"""

        b.emit(0xAD)

    @staticmethod
    def mHL(b: Block) -> None:
        """XOR (HL)"""

        b.emit(0xAE)

    @staticmethod
    def A(b: Block) -> None:
        """XOR A"""

        b.emit(0xAF)

    @staticmethod
    def mIXd(b: Block, disp: int) -> None:
        """XOR (IX+d)"""

        b.emit(0xDD, 0xAE, disp & 0xFF)

    @staticmethod
    def mIYd(b: Block, disp: int) -> None:
        """XOR (IY+d)"""

        b.emit(0xFD, 0xAE, disp & 0xFF)

    @staticmethod
    def n8(b: Block, value: int) -> None:
        """XOR n8"""

        b.emit(0xEE, value & 0xFF)

# ---------------------------------------------------------------------------
# ビット操作
# ---------------------------------------------------------------------------


def RLCA(b: Block) -> None:
    b.emit(0x07)


def RRCA(b: Block) -> None:
    b.emit(0x0F)


def RLA(b: Block) -> None:
    b.emit(0x17)


def RRA(b: Block) -> None:
    b.emit(0x1F)


def DAA(b: Block) -> None:
    b.emit(0x27)


def CPL(b: Block) -> None:
    b.emit(0x2F)


def SCF(b: Block) -> None:
    b.emit(0x37)


def CCF(b: Block) -> None:
    b.emit(0x3F)


# ---------------------------------------------------------------------------
# INC / DEC 命令
# ---------------------------------------------------------------------------


class INC:
    """INC 系命令。"""

    # 8bit
    @staticmethod
    def A(b: Block) -> None:
        b.emit(0x3C)

    @staticmethod
    def B(b: Block) -> None:
        b.emit(0x04)

    @staticmethod
    def C(b: Block) -> None:
        b.emit(0x0C)

    @staticmethod
    def D(b: Block) -> None:
        b.emit(0x14)

    @staticmethod
    def E(b: Block) -> None:
        b.emit(0x1C)

    @staticmethod
    def H(b: Block) -> None:
        b.emit(0x24)

    @staticmethod
    def L(b: Block) -> None:
        b.emit(0x2C)

    @staticmethod
    def mHL(b: Block) -> None:
        """INC (HL)"""
        b.emit(0x34)

    # 16bit
    @staticmethod
    def BC(b: Block) -> None:
        b.emit(0x03)

    @staticmethod
    def DE(b: Block) -> None:
        b.emit(0x13)

    @staticmethod
    def HL(b: Block) -> None:
        b.emit(0x23)

    @staticmethod
    def SP(b: Block) -> None:
        b.emit(0x33)

    @staticmethod
    def IX(b: Block) -> None:
        b.emit(0xDD, 0x23)

    @staticmethod
    def IY(b: Block) -> None:
        b.emit(0xFD, 0x23)

    # (IX+d) / (IY+d)
    @staticmethod
    def mIXd(b: Block, disp: int) -> None:
        """INC (IX+d)"""
        b.emit(0xDD, 0x34, disp & 0xFF)

    @staticmethod
    def mIYd(b: Block, disp: int) -> None:
        """INC (IY+d)"""
        b.emit(0xFD, 0x34, disp & 0xFF)


class DEC:
    """DEC 系命令。"""

    # 8bit
    @staticmethod
    def A(b: Block) -> None:
        b.emit(0x3D)

    @staticmethod
    def B(b: Block) -> None:
        b.emit(0x05)

    @staticmethod
    def C(b: Block) -> None:
        b.emit(0x0D)

    @staticmethod
    def D(b: Block) -> None:
        b.emit(0x15)

    @staticmethod
    def E(b: Block) -> None:
        b.emit(0x1D)

    @staticmethod
    def H(b: Block) -> None:
        b.emit(0x25)

    @staticmethod
    def L(b: Block) -> None:
        b.emit(0x2D)

    @staticmethod
    def mHL(b: Block) -> None:
        """DEC (HL)"""
        b.emit(0x35)

    # 16bit
    @staticmethod
    def BC(b: Block) -> None:
        b.emit(0x0B)

    @staticmethod
    def DE(b: Block) -> None:
        b.emit(0x1B)

    @staticmethod
    def HL(b: Block) -> None:
        b.emit(0x2B)

    @staticmethod
    def SP(b: Block) -> None:
        b.emit(0x3B)

    @staticmethod
    def IX(b: Block) -> None:
        b.emit(0xDD, 0x2B)

    @staticmethod
    def IY(b: Block) -> None:
        b.emit(0xFD, 0x2B)

    # (IX+d) / (IY+d)
    @staticmethod
    def mIXd(b: Block, disp: int) -> None:
        """DEC (IX+d)"""
        b.emit(0xDD, 0x35, disp & 0xFF)

    @staticmethod
    def mIYd(b: Block, disp: int) -> None:
        """DEC (IY+d)"""
        b.emit(0xFD, 0x35, disp & 0xFF)


# ---------------------------------------------------------------------------
# データ配置ヘルパ: DB / DW
# ---------------------------------------------------------------------------

def DB(b: Block, *values: int) -> None:
    """1バイト値を順に配置する。"""

    for v in values:
        b.emit(v & 0xFF)


def DW(b: Block, *values: int) -> None:
    """16bit値(リトルエンディアン)を順に配置する。"""

    for v in values:
        lo = v & 0xFF
        hi = (v >> 8) & 0xFF
        b.emit(lo, hi)

# ---------------------------------------------------------------------------
# OUT 命令
# ---------------------------------------------------------------------------


def OUT(b: Block, port: int) -> None:
    """
    OUT (port),A
    """
    b.emit(0xD3, port & 0xFF)


def OUT_A(b: Block, port: int, a: int) -> None:
    """
    LD　A, a
    OUT (port),A
    A レジスタの値を設定してOUT
    """
    LD.A_n8(b, a & 0xFF)
    b.emit(0xD3, port & 0xFF)


class OUT_C:
    """OUT 系命令。"""

    _R_OPCODES = {
        "B": 0x41,
        "C": 0x49,
        "D": 0x51,
        "E": 0x59,
        "H": 0x61,
        "L": 0x69,
        "A": 0x79,
    }

    @staticmethod
    def r(b: Block, src: str) -> None:
        """OUT (C),r"""

        try:
            opcode = OUT_C._R_OPCODES[src]
        except KeyError as exc:
            raise ValueError(f"invalid src for OUT (C),r: {src}") from exc
        b.emit(0xED, opcode)

# ---------------------------------------------------------------------------
# push / pop
# ---------------------------------------------------------------------------


RegNames16 = Literal["AF", "BC", "DE", "HL", "IX", "IY"]


class PUSH:

    @staticmethod
    def AF(b: Block) -> None:
        b.emit(0xF5)

    @staticmethod
    def BC(b: Block) -> None:
        b.emit(0xC5)

    @staticmethod
    def DE(b: Block) -> None:
        b.emit(0xD5)

    @staticmethod
    def HL(b: Block) -> None:
        b.emit(0xE5)

    @staticmethod
    def IX(b: Block) -> None:
        b.emit(0xDD, 0xE5)

    @staticmethod
    def IY(b: Block) -> None:
        b.emit(0xFD, 0xE5)

    @classmethod
    def r(cls, b: Block, dst: RegNames16) -> None:
        if dst == "AF":
            cls.AF(b)
        elif dst == "BC":
            cls.BC(b)
        elif dst == "DE":
            cls.DE(b)
        elif dst == "HL":
            cls.HL(b)
        elif dst == "IX":
            cls.IX(b)
        elif dst == "IY":
            cls.IY(b)


class POP:

    @staticmethod
    def AF(b: Block) -> None:
        b.emit(0xF1)

    @staticmethod
    def BC(b: Block) -> None:
        b.emit(0xC1)

    @staticmethod
    def DE(b: Block) -> None:
        b.emit(0xD1)

    @staticmethod
    def HL(b: Block) -> None:
        b.emit(0xE1)

    @staticmethod
    def IX(b: Block) -> None:
        b.emit(0xDD, 0xE1)

    @staticmethod
    def IY(b: Block) -> None:
        b.emit(0xFD, 0xE1)

    @classmethod
    def r(cls, b: Block, dst: RegNames16) -> None:
        if dst == "AF":
            cls.AF(b)
        elif dst == "BC":
            cls.BC(b)
        elif dst == "DE":
            cls.DE(b)
        elif dst == "HL":
            cls.HL(b)
        elif dst == "IX":
            cls.IX(b)
        elif dst == "IY":
            cls.IY(b)


# ---------------------------------------------------------------------------
# misc
# ---------------------------------------------------------------------------


def NOP(b: Block, times: int = 1) -> None:
    """NOP 命令を挿入する。"""
    for _ in range(times):
        b.emit(0x00)


def HALT(b: Block) -> None:
    """HALT 命令を挿入する。"""
    b.emit(0x76)


def DI(b: Block) -> None:
    """DI (割り込み禁止) 命令を挿入する。"""
    b.emit(0xF3)


def EI(b: Block) -> None:
    """EI (割り込み許可) 命令を挿入する。"""
    b.emit(0xFB)

