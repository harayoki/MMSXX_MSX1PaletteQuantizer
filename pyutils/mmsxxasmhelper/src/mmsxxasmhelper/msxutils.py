"""
MSX 関連マクロ & 関数 他
"""

from __future__ import annotations

from typing import Callable, Concatenate, Literal, ParamSpec, Sequence

from mmsxxasmhelper.core import *
from mmsxxasmhelper.utils import *


__all__ = [
    # "call_subrom_macro",
    "place_msx_rom_header_macro",
    # "fill_stack_macro",
    "store_stack_pointer_macro",
    "init_stack_pointer_macro",
    "restore_stack_pointer_macro",
    "get_msxver_macro",
    "set_msx2_palette_default_macro",
    "init_screen2_macro",
    "set_screen_mode_macro",
    "set_text_cursor_macro",
    "set_screen_colors_macro",
    "enaslt_macro",
    "ldirvm_macro",
    # "set_palette_macro",

    "build_update_input_func",
    "INPUT_KEY_BIT",
    "build_beep_control_utils",
    "build_set_vram_write_func",
    "build_scroll_name_table_func",
    "INITXT",
    "VDP_CTRL",
    "VDP_DATA",
    "VDP_PAL",
]
P = ParamSpec("P")



# BIOS コールアドレス
LDIRVM = 0x005C  # メモリ→VRAMの連続書込
CHGMOD = 0x005F  # 画面モード変更
INIGRP = 0x0072  # SCREEN 初期化
CHGCLR = 0x0062  # 画面色変更
POSIT = 0x00C6  # カーソル移動
INITXT = 0x006C  # SCREEN 0 初期化
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
qqq
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


# def fill_stack_macro(b: Block, fill_value: int = 0xAA, stack_top: int = 0xEFFF, stack_size: int = 0x0200) -> None:
#     """
#     スタック領域を一定の値で塗りつぶしておく（利用範囲を見極めるため）
#     :param b: Block
#     :param fill_value: 埋める値
#     :param stack_top: stack addr
#     :param stack_size:   default 0x0200 = 512b
#     """
#     start = stack_top - stack_size
#
#     LD.HL_n16(b, start)
#     LD.BC_n16(b, stack_size)
#     LD.A_n8(b, fill_value)
#
#     fill_stack_loop = unique_label()
#     b.label(fill_stack_loop)
#     LD.mHL_A(b)
#     INC.HL(b)
#     DEC.BC(b)
#     LD.A_B(b)
#     OR.C(b)
#     JP_NZ(b, fill_stack_loop)


# def fill_stack_macro(
#     b: Block,
#     fill_value: int = 0xAA,
#     stack_top: int = 0xEFC0,  # SP_TEMP_RAM(0xEFE0)より少し下
#     stack_size: int = 0x0200,
# ) -> None:
#     """
#     [stack_top - stack_size .. stack_top - 1] を fill_value で埋める。
#     Z80の LDIR で高速に複製する版。
#     """
#     if stack_size <= 0:
#         return
#
#     start = (stack_top - stack_size) & 0xFFFF
#
#     # HL = start
#     LD.HL_n16(b, start)
#
#     # (HL) = fill_value
#     LD.A_n8(b, fill_value)
#     LD.mHL_A(b)
#
#     if stack_size == 1:
#         return
#
#     # DE = start + 1
#     LD.DE_n16(b, (start + 1) & 0xFFFF)
#
#     # BC = stack_size - 1
#     LD.BC_n16(b, (stack_size - 1) & 0xFFFF)
#
#     # LDIR (ED B0): (HL)->(DE), HL++,DE++,BC-- until BC=0
#     b.emit(0xED, 0xB0)
#
#
# def fill_stack_macro(
#     b: Block,
#     fill_value: int = 0xAA,
#     stack_top: int = 0xEFC0,
#     stack_size: int = 0x0200,
# ) -> None:
#     if stack_size <= 0 or stack_size > 0x0800:
#         raise ValueError("stack_size abnormal")
#
#     start = (stack_top - stack_size) & 0xFFFF
#
#     LD.HL_n16(b, start)
#     LD.A_n8(b, fill_value)
#     LD.mHL_A(b)
#
#     if stack_size == 1:
#         return
#
#     LD.DE_n16(b, (start + 1) & 0xFFFF)
#     LD.BC_n16(b, (stack_size - 1) & 0xFFFF)
#     b.emit(0xED, 0xB0)  # LDIR


# 候補1
# システムスタック下限(F383H)よりは下で、RAMの後方に近いアドレス
# SP_TEMP_RAM1 = 0xF300
SP_TEMP_RAM1 = 0xF37A

# # 候補2
# # 自プログラム専用のRAM領域（C000h–EFFFh）内に確保する一時ワーク。
# # ROMブート直後のBIOSスタックはFxxxh帯に来ることが多い？？ため chatGPTの意見、
# # システムワークと衝突しないようF000h未満に置く。
# SP_TEMP_RAM2 = 0xEFE0

# 候補2 ぎりぎり ここで良いGeminiの意見
SP_TEMP_RAM3 = 0xF380


def store_stack_pointer_macro(b: Block, address: int = SP_TEMP_RAM1) -> None:
    """
    ROM起動直後、スタックポインタ(SP)の値を一時 RAM 領域に保存するマクロ。
    既存のスタック値を残す安全版。（BASICにもどる場合など）
    init_stack_pointer_macroを呼んだ方が無駄がないが、すでに動いてるものもあるので残す。
    """
    # 元のスタックポインタ(SP)の値を RAM に退避する
    LD.HL_n16(b, 0)
    ADD.HL_SP(b)  # HL = SP
    LD.mn16_HL(b, address)  # SP_TEMP_RAM にSP保存

    # 新しいスタックポインタを、RAM上の安全な場所(SP_TEMP_RAM+4)へ設定
    # (PUSH 時のデクリメントで退避した SP の領域を踏まないように 4 バイト空ける)
    LD.HL_n16(b, address + 4)
    LD.SP_HL(b)


def restore_stack_pointer_macro(b: Block, address: int = SP_TEMP_RAM1) -> None:
    """一時 RAM 領域に保存したスタックポインタ(SP)の値を復元するマクロ。"""
    LD.HL_mn16(b, address)
    LD.SP_HL(b)


def init_stack_pointer_macro(b: Block, address: int = SP_TEMP_RAM3) -> None:
    """
    ROM起動直後、スタックポインタ(SP)の値を移動するマクロ
    """
    LD.SP_n16(b, address)


# 上の物より無駄が少ないかもしれないバージョン 未検証
# def store_stack_pointer_macro(b: Block) -> None:
#     # DI
#     b.emit(0xF3)
#
#     # LD (SP_TEMP_RAM),SP  ; ED 73 ll hh
#     lo = SP_TEMP_RAM & 0xFF
#     hi = (SP_TEMP_RAM >> 8) & 0xFF
#     b.emit(0xED, 0x73, lo, hi)
#
#     # LD SP,SP_TEMP_RAM+4
#     new_sp = SP_TEMP_RAM + 4
#     b.emit(0x31, new_sp & 0xFF, (new_sp >> 8) & 0xFF)
#
#     # EI（必要なら。割り込み禁止のまま走る設計なら外す）
#     b.emit(0xFB)



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
    # r = int(r * 7 / 255)
    # g = int(g * 7 / 255)
    # b = int(b * 7 / 255)
    return ((r & 0x07) << 4) | (b & 0x07), g & 0x07


# MSX2 環境向け MSX1 カラーパレット (R,G,B: 0–7)
_MSX2_PALETTE_BYTES = [
    *palette_bytes(0, 0, 0),
    *palette_bytes(0, 0, 0),
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

    msx2_pal_set_end_label = unique_label("__MSX2_PAL_SET_END__")
    palette_data_label = unique_label("__PALETTE_DATA__")
    msx2_pal_loop_label = unique_label("__MSX2_PAL_LOOP__")
    msx2_pal_data_end_label = unique_label("__MSX2_PAL_DATA_END__")

    # --- MSX バージョン確認 ---
    get_msxver_macro(b)
    CP.n8(b, 0x00)
    # ゼロ(MSX1) のときはパレット処理を丸ごと飛ばす
    JP_Z(b, msx2_pal_set_end_label)

    # R#16 に color index 0 をセット
    OUT_A(b, VDP_CTRL, 0x00)
    OUT_A(b, VDP_CTRL, 0x80 + 16)

    # HL = PALETTE_DATA
    LD.HL_label(b, palette_data_label)

    # B = 32 (16色×2バイト)
    LD.B_n8(b, 32)

    b.label(msx2_pal_loop_label)
    LD.A_mHL(b)
    OUT(b, VDP_PAL)
    INC.HL(b)
    DJNZ(b, msx2_pal_loop_label)

    b.label(msx2_pal_set_end_label)
    # パレットデータ本体（実行されない領域）
    JP(b, msx2_pal_data_end_label)  # 直後のデータを実行しないようにスキップ
    b.label(palette_data_label)
    DB(b, *_MSX2_PALETTE_BYTES)
    b.label(msx2_pal_data_end_label)

    # print("-----")
    # print(_MSX2_PALETTE_BYTES)
    # print("-----")


def set_screen_mode_macro(b: Block, mode: int) -> None:
    """CHGMOD を呼び出して画面モードを設定する。
    レジスタ変更: A（CHGMOD 呼び出しにより AF なども破壊される可能性あり）。
    """
    LD.A_n8(b, mode & 0xFF)
    b.emit(0xCD, CHGMOD & 0xFF, (CHGMOD >> 8) & 0xFF)


def set_text_cursor_macro(b: Block, x: int, y: int) -> None:
    """POSIT (#00C6) を呼び出してテキストカーソルを移動するマクロ。

    H: X 座標、L: Y 座標を設定してから POSIT を呼び出す。
    レジスタ変更: AF（BIOS 呼び出しにより破壊される）。
    """

    LD.H_n8(b, x & 0xFF)
    LD.L_n8(b, y & 0xFF)
    CALL(b, POSIT)


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
    CALL(b, CHGCLR)


@with_register_preserve
def ldirvm_macro(
    b: Block,
    *,
    source_HL: int | None = None,
    dest_DE: int | None = None,
    length_BC: int | None = None,
    regs_preserve: Sequence[RegNames16] = ()
) -> None:
    """LDIRVM (#005C) を呼び出すマクロ。
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


# --- 仮想ボタン定義 (論理ビット) ---
class INPUT_KEY_BIT:
    L_UP: int = 0  # Bit 0
    L_DOWN: int = 1  # Bit 1
    L_LEFT: int = 2  # Bit 2
    L_RIGHT: int = 3  # Bit 3
    L_BTN_A: int = 4  # Bit 4 (SPACE / タップ)
    L_BTN_B: int = 5  # Bit 5 (SHIFT / ジョイスティック2)
    L_ESC: int = 6  # Bit 6
    L_EXTRA: int = 7  # Bit 7


def build_update_input_func(
    input_hold: int = 0xC100,
    input_trg: int = 0xC101,
) -> Func:
    """
    論理入力を更新する共通関数。
    キーボード、(将来的に)ジョイスティック、スマホI/O等を統合して
    INPUT_HOLD / INPUT_TRG を作成する。ワークエリアのアドレスは引数で指定する。
    """

    # --- 入力関連システム変数・BIOS ---
    SNSMAT = 0x0141  # キーマトリックス読み取り
    GTSTCK = 0x00D5  # ジョイスティック状態取得
    GTTRIG = 0x00D8  # ジョイスティックボタン取得

    def update_input(block: Block) -> None:
        skip_kbd_space = unique_label("__SKIP_KBD_SPACE__")
        skip_kbd_shift = unique_label("__SKIP_KBD_SHIFT__")

        # --- 1. 物理入力のサンプリング ---
        # 最終的に A レジスタに論理ビット(1=押下)を組み立てる
        PUSH.IX(block)
        LD.IX_n16(block, 0)  # IXL を作業用ボタンフラグにする (0でリセット)

        # Keyboard: SPACE (Matrix 8, Bit 0)
        LD.A_n8(block, 8)
        CALL(block, SNSMAT)
        # Bit 0 が 0 なら押下。反転させて論理Bit4へ
        CPL(block)
        BIT.n8_A(block, 0)
        JR_Z(block, skip_kbd_space)
        LD.A_n8(block, 1 << INPUT_KEY_BIT.L_BTN_A)
        OR.IXL(block)
        LD.IXL_A(block)
        block.label(skip_kbd_space)

        # Keyboard: SHIFT (Matrix 6, Bit 0)
        LD.A_n8(block, 6)
        CALL(block, SNSMAT)
        CPL(block)
        BIT.n8_A(block, 0)
        JR_Z(block, skip_kbd_shift)
        LD.A_n8(block, 1 << INPUT_KEY_BIT.L_BTN_B)
        OR.IXL(block)
        LD.IXL_A(block)
        block.label(skip_kbd_shift)

        # --- 2. HOLD と TRG の更新計算 ---
        # A = 今回の最新HOLD (IXL)
        LD.A_IXL(block)
        LD.HL_n16(block, input_hold)
        LD.C_mHL(block)  # C = 前回の HOLD
        LD.mHL_A(block)  # 今回の A を新しい INPUT_HOLD として保存

        # TRG = NEW_HOLD AND (NOT OLD_HOLD)
        # C = OLD_HOLD なので反転して A と AND
        LD.B_A(block)  # B = 今回の HOLD
        LD.A_C(block)  # A = 前回の HOLD
        CPL(block)  # A = NOT 前回の HOLD
        AND.B(block)  # A = NEW & (~OLD)
        LD.mn16_A(block, input_trg)

        POP.IX(block)

    return Func("update_input", update_input)


"""
使い方

# ...初期化...
    b.label("MAIN_LOOP")
    HALT(block) # V-Sync待ち（これを入れないとキー判定が速すぎる）
    UPDATE_INPUT_CALL.call(b)

    # SPACE(BTN_A)が今押されたかチェック
    LD.A_mn16(b, INPUT_TRG)
    BIT.n8_A(b, L_BTN_A)
    JR_Z(b, "MAIN_LOOP")

    # スペースが押された時、SHIFT(BTN_B)が保持されているか？
    LD.A_mn16(b, INPUT_HOLD)
    BIT.n8_A(b, L_BTN_B)
    JR_NZ(b, "PREV_IMAGE")

    # --- NEXT ---
    # (画像番号を加算して描画ルーチンへ)
    # ...
    JR(b, "MAIN_LOOP")

    # --- PREV ---
    # (画像番号を減算して描画ルーチンへ)
    # ...
    JR(b, "MAIN_LOOP")

"""



def build_beep_control_utils(
    beep_count_addr: int = 0xC110,
    beep_active_addr: int = 0xC111,
    tone_period: int = 60,  # 0-4095
    duration_frames: int = 1,  # 1/60秒単位
):
    PSG_REG = 0xA0
    PSG_DAT = 0xA1

    def psg_write(block: Block) -> None:
        OUT(block, PSG_REG)
        LD.A_E(block)
        OUT(block, PSG_DAT)
        RET(block)

    BEEP_WRITE_FUNC = Func("BEEP_WRITE", psg_write)

    def simple_beep(block: Block) -> None:
        """
        BEEP開始。
        レジスタ7への書き込み時、最上位ビット(Bit7)を必ず1にすることで、
        物理損傷のリスク(unsafe PSG port directions)を回避します。
        """
        # 状態の初期化
        LD.A_n8(block, duration_frames & 0xFF)
        LD.mn16_A(block, beep_count_addr)
        LD.A_n8(block, 1)
        LD.mn16_A(block, beep_active_addr)

        # 1. チャンネルAの周期設定 (Reg 0, 1)
        LD.A_n8(block, 0)
        LD.E_n8(block, tone_period & 0xFF)
        BEEP_WRITE_FUNC.call(block)

        LD.A_n8(block, 1)
        LD.E_n8(block, (tone_period >> 8) & 0x0F)
        BEEP_WRITE_FUNC.call(block)

        # 2. ミキサー設定 (Reg 7)
        # Bit7=1(入力), Bit6=1(入力), Bit5-3=1(Noise OFF), Bit2-0=音量ON/OFF
        # ChAのみONにする場合: 10111110b = 0xBE (安全な設定)
        LD.A_n8(block, 7)
        LD.E_n8(block, 0xBE)  # 0xFE ではなく 0xBE を使うことでハードを保護
        BEEP_WRITE_FUNC.call(block)

        # 3. 音量設定 (Reg 8)
        LD.A_n8(block, 8)
        LD.E_n8(block, 15)
        BEEP_WRITE_FUNC.call(block)

        RET(block)

    def update_beep(block: Block) -> None:
        # (update_beep の実装は変更なし)
        LD.A_mn16(block, beep_active_addr)
        OR.A(block)
        RET_Z(block)

        LD.A_mn16(block, beep_count_addr)
        DEC.A(block)
        LD.mn16_A(block, beep_count_addr)
        RET_NZ(block)

        # 消音
        XOR.A(block)
        LD.mn16_A(block, beep_active_addr)
        LD.A_n8(block, 8)
        LD.E_n8(block, 0)
        BEEP_WRITE_FUNC.call(block)
        RET(block)

    return BEEP_WRITE_FUNC, Func("SIMPLE_BEEP", simple_beep), Func("UPDATE_BEEP", update_beep)


def build_set_vram_write_func() -> Func:
    def set_vram_write(block: Block) -> None:
        # 入力: HL = 書き込み開始VRAMアドレス (0x0000 - 0x3FFF)
        # VDPレジスタの仕様: 下位8bit、次に上位6bit + 01000000b (Write mode) を送る

        LD.A_L(block)
        OUT(block, 0x99)  # 下位8bit

        LD.A_H(block)
        OR.n8(block, 0x40)  # 0x40 (Writeモードビット) を立てる
        OUT(block, 0x99)  # 上位8bit

    return Func("SET_VRAM_WRITE", set_vram_write)


def build_scroll_name_table_func(SET_VRAM_WRITE_FUNC: Func) -> Func:
    def scroll_name_table(block: Block) -> None:
        # 入力: A = CURRENT_SCROLL_ROW (0-23)
        # ※ 24行を超えると表示がループ（0に戻る）します

        PUSH.AF(block)
        # VRAM 0x1800 (名前テーブル) を書き込みモードでセット
        LD.HL_n16(block, 0x1800)
        SET_VRAM_WRITE_FUNC.call(block)
        POP.AF(block)

        # キャラクター番号の開始オフセット = A * 32
        # (1行32文字なので、A行分飛ばす)
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)  # *2
        ADD.HL_HL(block)  # *4
        ADD.HL_HL(block)  # *8
        ADD.HL_HL(block)  # *16
        ADD.HL_HL(block)  # *32 -> HL = 開始キャラクタ番号

        LD.D_n8(block, 24)  # 24行分ループ
        LD.C_n8(block, 0x98)  # VDPポート

        LINE_LOOP = unique_label()
        COLUMN_LOOP = unique_label()
        block.label(LINE_LOOP)
        LD.B_n8(block, 32)  # 1行32列

        block.label(COLUMN_LOOP)
        LD.A_L(block)  # HLの下位8bitをキャラクタ番号として使用
        OUT_C.A(block)
        INC.HL(block)  # 次のキャラクタへ
        DJNZ(block, COLUMN_LOOP)

        DEC.D(block)
        JR_NZ(block, LINE_LOOP)
        RET(block)

    return Func("SCROLL_NAME_TABLE", scroll_name_table)


