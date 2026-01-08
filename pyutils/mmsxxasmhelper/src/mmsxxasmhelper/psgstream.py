"""
PSGストリーム再生ユーティリティ
"""

from __future__ import annotations

from typing import Callable

from mmsxxasmhelper.core import (
    Block,
    CP,
    DJNZ,
    INC,
    JR,
    JR_NZ,
    JR_Z,
    LD,
    OR,
    OUT,
    XOR,
    unique_label,
)

__all__ = ["build_play_vgm_frame_func"]


def build_play_vgm_frame_func(
    vgm_ptr_addr: int,
    vgm_loop_addr: int,
    vgm_timer_flag_addr: int,
    bgm_enabled_addr: int,
    vgm_bank_num: int | None = None,
    vgm_bank_addr: int | None = None,
    vgm_loop_bank_addr: int | None = None,
    current_bank_addr: int | None = None,
    page2_bank_reg_addr: int = 0x7000,
    fps30: bool = False,
) -> tuple[Callable[[Block], None], Callable[[Block], None], Callable[[Block], None]]:
    """
    VGMフレーム再生と割り込みフック用関数を生成する。

    返却値:
        (PLAY_VGM_FRAME_MACRO, PSG_ISR_MACRO, MUTE_PSG_MACRO) の3つ

    PLAY_VGM_FRAME_MACRO の入力:
        HL = (VGM_PTR) アドレス（現在のVGMストリーム位置）

    PSG_ISR_MACRO の動作:
        bgm_enabled_addr が 0 のときは即時リターンする。
        vgm_timer_flag_addr の 0/1 を反転し、0のとき再生処理をスキップする。
        vgm_bank_addr が指定されている場合、再生時にページ2バンクを切り替える。
        vgm_bank_addr 指定時は、VGMポインタがバンク末尾を超えたら次バンクへ移行する。
    """

    psg_reg_port = 0xA0
    psg_data_port = 0xA1
    page2_bank_base_addr = 0x8000

    def play_vgm_frame_macro(block: Block) -> None:
        loop_reg = unique_label("PLAY_VGM_LOOP")
        next_frame = unique_label("PLAY_VGM_NEXT")
        do_loop = unique_label("PLAY_VGM_DO_LOOP")
        end_label = unique_label("PLAY_VGM_END")

        def maybe_switch_bank() -> None:
            if vgm_bank_addr is None:
                return
            bank_ok = unique_label("PLAY_VGM_BANK_OK")
            LD.A_H(block)
            CP.n8(block, 0xC0)
            JR_NZ(block, bank_ok)
            LD.HL_n16(block, page2_bank_base_addr)
            LD.A_mn16(block, vgm_bank_addr)
            INC.A(block)
            LD.mn16_A(block, vgm_bank_addr)
            LD.mn16_A(block, page2_bank_reg_addr)
            block.label(bank_ok)

        LD.HL_mn16(block, vgm_ptr_addr)
        LD.A_mHL(block)
        INC.HL(block)
        maybe_switch_bank()

        CP.n8(block, 0xFF)
        JR_Z(block, do_loop)

        OR.A(block)
        JR_Z(block, next_frame)

        LD.B_A(block)
        block.label(loop_reg)
        LD.A_mHL(block)
        OUT(block, psg_reg_port)
        INC.HL(block)
        maybe_switch_bank()
        LD.A_mHL(block)
        OUT(block, psg_data_port)
        INC.HL(block)
        maybe_switch_bank()
        DJNZ(block, loop_reg)

        block.label(next_frame)
        LD.mn16_HL(block, vgm_ptr_addr)
        JR(block, end_label)

        block.label(do_loop)
        LD.HL_mn16(block, vgm_loop_addr)
        if vgm_loop_bank_addr is not None and vgm_bank_addr is not None:
            LD.A_mn16(block, vgm_loop_bank_addr)
            LD.mn16_A(block, vgm_bank_addr)
            LD.mn16_A(block, page2_bank_reg_addr)
        LD.mn16_HL(block, vgm_ptr_addr)
        block.label(end_label)

    def mute_psg_macro(block: Block) -> None:
        # PSGを停止（ミキサー無効化 + 各チャンネル音量0）
        # 毎フレーム対応したくないならコンフィグ側で音量ＯＦＦにすべき
        LD.A_n8(block, 0x07)
        OUT(block, psg_reg_port)
        LD.A_n8(block, 0b10111111)
        OUT(block, psg_data_port)
        for reg in (8, 9, 10):
            LD.A_n8(block, reg)
            OUT(block, psg_reg_port)
            LD.A_n8(block, 0)
            OUT(block, psg_data_port)

    def psg_isr_macro(block: Block) -> None:
        process_play = unique_label("PROCESS_PLAY")
        skip_play = unique_label("PSG_ISR_SKIP_PLAY")
        end_isr = unique_label("PSG_ISR_END")

        LD.A_mn16(block, bgm_enabled_addr)
        OR.A(block)
        JR_Z(block, end_isr)

        block.label(process_play)

        if fps30:
            LD.A_mn16(block, vgm_timer_flag_addr)
            XOR.n8(block, 1)
            LD.mn16_A(block, vgm_timer_flag_addr)
            JR_Z(block, skip_play)

        if vgm_bank_addr is not None:
            LD.A_mn16(block, vgm_bank_addr)
            LD.mn16_A(block, page2_bank_reg_addr)
        elif vgm_bank_num is not None:
            LD.A_n8(block, vgm_bank_num)
            LD.mn16_A(block, page2_bank_reg_addr)
        play_vgm_frame_macro(block)
        if current_bank_addr is not None:
            LD.A_mn16(block, current_bank_addr)
            LD.mn16_A(block, page2_bank_reg_addr)

        block.label(skip_play)

        block.label(end_isr)

    return play_vgm_frame_macro, psg_isr_macro, mute_psg_macro
