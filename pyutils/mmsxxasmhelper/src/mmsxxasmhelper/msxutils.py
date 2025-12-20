"""
MSX 関連マクロ & 関数 他
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, Concatenate, Literal, ParamSpec, Sequence

from mmsxxasmhelper.core import *
from mmsxxasmhelper.utils import *


__all__ = [
    # "call_subrom_macro",
    "place_msx_rom_header_macro",
    "store_stack_pointer_macro",
    "restore_stack_pointer_macro",
    "get_msxver_macro",
    "set_msx2_palette_default_macro",
    "init_screen2_macro",
    "set_screen_mode_macro",
    "set_screen_colors_macro",
    "enaslt_macro",
    "ldirvm_macro",
    # "set_palette_macro",

    "VDP_CTRL",
    "VDP_DATA",
    "VDP_PAL",
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


# システムスタック下限(F383H)よりは下で、RAMの後方に近いアドレス
SP_TEMP_RAM = 0xF300


# BIOS コールアドレス
LDIRVM = 0x005C  # メモリ→VRAMの連続書込
CHGMOD = 0x005F  # 画面モード変更
INIGRP = 0x0072  # SCREEN 初期化
CHGCLR = 0x0062  # 画面色変更
ENASLT = 0x0024  # スロット切り替え
RSLREG = 0x0138  # 現在のスロット情報取得
# EXPTBL = 0xFCC1  # 拡張スロット情報
# EXPTBL_MINUS_1 = EXPTBL -1
# CALSLT = 0x001C  # インタースロットCALL（任意スロットの任意アドレスを呼ぶ）
# SUBROM = 0x015C  # SUB-ROM内ルーチンCALL（IX指定・IYにSUB-ROMスロット必須）

# サブROM内 コールアドレス
SETPLET = 0x014D

# カラー関連システム変数 (MSX1/2 共通)
FORCLR = 0xF3E9  # 前景色
BAKCLR = 0xF3EA  # 背景色
BDRCLR = 0xF3EB  # 枠色
MSXVER = 0x002D  # 0=MSX1, 1=MSX2, 2=2+, 3=turboR

VDP_DATA = 0x98   # VDPデータポート
VDP_CTRL = 0x99   # VDPコントロールポート
VDP_PAL  = 0x9A   # パレットデータポート（MSX2以降）


# def call_subrom_macro(b: Block, address: int) -> None:
# 上手くいかないのでいったんつぶす
#     """
#     SUB-ROM内ルーチン呼び出し
#     - 入力: IX=呼び先アドレス（SUB-ROM内）
#     - 備考: スロット指定はBIOS側が処理する想定（IYは予約=保持）
#     """
#     # LD.IY_mn16(b, EXPTBL_MINUS_1)  # IY = SUB-ROMスロット系情報
#     LD.IX_n16(b, address)
#     CALL(b, SUBROM)


def place_msx_rom_header_macro(b: Block, entry_point: int = 0x4010) -> None:
    """MSX ROM ヘッダ (16 バイト) を配置するマクロ。

    "AB" に続けてエントリアドレス（リトルエンディアン）を書き、残りは 0 で
    パディングする。エントリポイントは 0x4010 をデフォルトとし、必要に応じて
    引数で変更できる。

    レジスタ変更: なし（ヘッダデータのみを配置する）。

    """

    header = [
        ord("A"),
        ord("B"),
        entry_point & 0xFF,
        (entry_point >> 8) & 0xFF,
        *([0x00] * (16 - 4)),
    ]
    DB(b, *header)


def store_stack_pointer_macro(b: Block) -> None:
    """スタックポインタ(SP)の値を一時 RAM 領域に保存するマクロ。"""

    # 元のスタックポインタ(SP)の値を RAM に退避する
    LD.HL_n16(b, 0)
    ADD.HL_SP(b)  # HL = SP
    LD.mn16_HL(b, SP_TEMP_RAM)  # SP_TEMP_RAM にSP保存

    # 新しいスタックポインタを、RAM上の安全な場所(SP_TEMP_RAM+4)へ設定
    # (PUSH 時のデクリメントで退避した SP の領域を踏まないように 4 バイト空ける)
    LD.HL_n16(b, SP_TEMP_RAM + 4)
    LD.SP_HL(b)


def restore_stack_pointer_macro(b: Block) -> None:
    """一時 RAM 領域に保存したスタックポインタ(SP)の値を復元するマクロ。"""
    LD.HL_mn16(b, SP_TEMP_RAM)
    LD.SP_HL(b)


def enaslt_macro(b: Block) -> None:
    """ENASLT (#0024) を呼び出してスロットを有効化するマクロ。

    現在のスロット情報を ``RSLREG`` で取得し、ページ 2 (0x8000–0xBFFF)
    を対象に ENASLT を実行する。レジスタ変更: A, HL。
    """

    b.emit(
        0xCD,
        RSLREG & 0xFF,
        (RSLREG >> 8) & 0xFF,  # CALL 0138h
        0x0F,  # RRCA
        0x0F,  # RRCA
        0xE6,
        0x03,  # AND 03h
        0x21,
        0x00,
        0x80,  # LD HL,8000h
        0xCD,
        ENASLT & 0xFF,
        (ENASLT >> 8) & 0xFF,  # CALL 0024h
    )


def palette_bytes(r: int, g: int, b: int) -> tuple[int, int]:
    """MSX2 パレットの 2 バイト表現を作る。

    - 1 バイト目: 0R2 R1 R0 B2 B1 B0 0 (R/B はビット 4–6 / 1–3)
    - 2 バイト目: 0000 G2 G1 G0
    """

    return ((r & 0b111) << 4) | ((b & 0b111) << 1), g & 0b111


# MSX2 環境向け MSX1 カラーパレット (R,G,B: 0–7)
_MSX2_PALETTE_BYTES = [
    *palette_bytes(0, 0, 0),
    # *palette_bytes(0, 0, 0),
    *palette_bytes(4, 4, 4),  # temp test
    *palette_bytes(2, 5, 2),
    *palette_bytes(3, 5, 3),
    *palette_bytes(2, 2, 6),
    *palette_bytes(3, 3, 6),
    *palette_bytes(5, 2, 2),
    *palette_bytes(2, 6, 6),
    *palette_bytes(6, 2, 2),
    *palette_bytes(7, 3, 3),
    *palette_bytes(5, 5, 2),
    *palette_bytes(6, 5, 3),
    *palette_bytes(1, 4, 1),
    *palette_bytes(5, 3, 5),
    *palette_bytes(5, 5, 5),
    *palette_bytes(7, 7, 7),
]


def get_msxver_macro(b: Block) -> None:
    """MSX バージョンを A レジスタに読み出す。
    レジスタ変更: A
    """
    LD.A_mn16(b, MSXVER)


def set_msx2_palette_default_macro(b: Block) -> None:
    """MSX2 以上でデフォルトパレットを設定するマクロ。
    レジスタ変更: A, B, HL（MSX2 判定とループ処理で使用）。

    """

    # --- MSX バージョン確認 ---
    get_msxver_macro(b)
    CP.n8(b, 0x00)
    # ゼロ(MSX1) のときはパレット処理を丸ごと飛ばす
    JP_Z(b, "__MSX2_PAL_SET_END__")

    # R#16 に color index 0 をセット
    OUT_A(b, VDP_CTRL, 0x00)
    OUT_A(b, VDP_CTRL, 0x80 + 16)

    # HL = PALETTE_DATA
    LD.HL_label(b, "__PALETTE_DATA__")

    # B = 32 (16色×2バイト)
    LD.B_n8(b, 32)

    b.label("__MSX2_PAL_LOOP__")
    LD.A_mHL(b)
    OUT(b, VDP_PAL)
    INC.HL(b)
    DJNZ(b, "__MSX2_PAL_LOOP__")

    b.label("__MSX2_PAL_SET_END__")
    # パレットデータ本体（実行されない領域）
    JP(b, "__MSX2_PAL_DATA_END__")  # 直後のデータを実行しないようにスキップ
    b.label("__PALETTE_DATA__")
    DB(b, *_MSX2_PALETTE_BYTES)
    b.label("__MSX2_PAL_DATA_END__")


def set_screen_mode_macro(b: Block, mode: int) -> None:
    """CHGMOD を呼び出して画面モードを設定する。
    レジスタ変更: A（CHGMOD 呼び出しにより AF なども破壊される可能性あり）。
    """
    LD.A_n8(b, mode & 0xFF)
    b.emit(0xCD, CHGMOD & 0xFF, (CHGMOD >> 8) & 0xFF)


def init_screen2_macro(b: Block) -> None:
    """SCREEN 2 初期化マクロ。
    レジスタ変更: A（INIGRP 呼び出しにより AF なども破壊される可能性あり）。
    """
    b.emit(0xCD, INIGRP & 0xFF, (INIGRP >> 8) & 0xFF)


def set_screen_colors_macro(
    b: Block, foreground: int, background: int, border: int,
        current_screen_mode: int) -> None:
    """MSX1/2 共通の画面色設定マクロ。

    FORCLR/BAKCLR/BDRCLR を指定した値に設定して CHGCLR を呼び出す。
    色は 0–15 の範囲に丸めて書き込む。

    レジスタ変更: A（CHGCLR 呼び出しにより AF なども破壊される可能性あり）。

    """

    # 直前に VDP を操作する場合のコード？
    # OUT_A(b, VDP_CTRL, 0)   # VRAMアドレスの下位バイト
    # OUT_A(b, VDP_CTRL, 40)  # VRAMアドレスの上位バイト + VRAM書き込みフラグ(C=1)
    # OUT_A(b, VDP_DATA, background & 0x0F)  # 背景色指定

    # DI(b)

    # vdpを初期化するコード？
    # OUT_A(b, VDP_CTRL, 0x02)
    # OUT_A(b, VDP_CTRL, 0x80)
    # LD.A_n8(b, 0xE0)
    # AND.n8(b, 0xFD)
    # OUT(b, VDP_CTRL)
    # OUT_A(b, VDP_CTRL, 0x81)

    # FORCLR
    LD.A_n8(b, foreground & 0x0F)
    LD.mn16_A(b, FORCLR)

    # BAKCLR
    LD.A_n8(b, background & 0x0F)
    LD.mn16_A(b, BAKCLR)

    # BDRCLR
    LD.A_n8(b, border & 0x0F)
    LD.mn16_A(b, BDRCLR)

    # set current screen mode in A
    LD.A_n8(b, current_screen_mode)

    # CALL CHGCLR
    # CALL(b, CHGCLR)  # コールすると固まってしまうのでいったんコメントアウトしておく

    # EI(b)


def ldirvm_macro(
    b: Block,
    *,
    source: int | None = None,
    dest: int | None = None,
    length: int | None = None,
) -> None:
    """LDIRVM (#005C) を呼び出すマクロ。

    HL:元アドレス, DE:VRAM先頭, BC:バイト数 を引数で上書きできる。
    いずれも ``None`` の場合は呼び出し元でレジスタが適切にセットされて
    いる前提で、そのまま BIOS コールだけを行う。

    レジスタ変更: HL, DE, BC（引数指定時に上書き）。BIOS 呼び出しによって
    AF/BC/DE/HL が破壊される前提で使用する。

    """

    if source is not None:
        LD.HL_n16(b, source & 0xFFFF)

    if dest is not None:
        LD.DE_n16(b, dest & 0xFFFF)

    if length is not None:
        LD.BC_n16(b, length & 0xFFFF)

    b.emit(0xCD, LDIRVM & 0xFF, (LDIRVM >> 8) & 0xFF)


# def set_palette_macro(
#         block: Block,
#         color: int, r: int, g: int, b: int,
#         msx1_safe: bool = True,
#         preserve_regs_de: bool = False,
# ) -> None:
#     """
#     SETPLET サブロムコールでパレットを設定（MSX2以降）
#     ※ 動作未確認
#     :param block: Block
#     :param color: color 1 ~ 15
#     :param r: red 1 ~ 7
#     :param g: green 1 ~ 7
#     :param b: blue 1 ~ 7
#     :param msx1_safe: msx1では処理を実行しないコードを挿入するか
#     :param preserve_regs_de: DEレジスタを保護
#     """
#     color = color & 0x0F
#     r = r & 0x07
#     g = g & 0x07
#     b = b & 0x07
#     if msx1_safe:
#         get_msxver_macro(block)
#         CP.n8(block, 0x00)
#         RET_Z(block)
#     if preserve_regs_de:
#         PUSH.DE(block)
#     LD.D_n8(block, color)
#     LD.A_n8(block, (r << 4) + b)
#     LD.E_n8(block, g)
#     if preserve_regs_de:
#         POP.DE(block)
#     # call_subrom_macro(block, SETPLET)


