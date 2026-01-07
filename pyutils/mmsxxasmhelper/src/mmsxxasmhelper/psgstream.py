"""
PSGストリーム再生ユーティリティ
"""

from __future__ import annotations

from typing import Callable

from mmsxxasmhelper.core import (
    Block,
    CP,
    DEFAULT_FUNC_GROUP_NAME,
    DI,
    DJNZ,
    EI,
    Func,
    INC,
    JR,
    JR_Z,
    JP_NZ,
    LD,
    OR,
    OUT,
    POP,
    PUSH,
    RET_Z,
    RET,
    XOR,
    unique_label,
)

from mmsxxasmhelper.utils import debug_print_pc

__all__ = ["build_play_vgm_frame_func"]


def build_play_vgm_frame_func(
    vgm_ptr_addr: int,
    vgm_loop_addr: int,
    init_music_addr: int,
    vgm_timer_flag_addr: int,
    bgm_enabled_addr: int,
    vgm_bank_addr: int | None = None,
    current_bank_addr: int | None = None,
    page2_bank_reg_addr: int = 0x7000,
    volume: int | None = None,
    *,
    group: str = DEFAULT_FUNC_GROUP_NAME,
) -> tuple[Func, Func]:
    """
    VGMフレーム再生と割り込みフック用関数を生成する。

    返却値:
        (INIT_MUSIC, MUSIC_ISR, PLAY_VGM_FRAME_MACRO) の3つ

    PLAY_VGM_FRAME_MACRO の入力:
        HL = (VGM_PTR) アドレス（現在のVGMストリーム位置）

    MUSIC_ISR の動作:
        bgm_enabled_addr が 0 のときは即時リターンする。
        vgm_timer_flag_addr の 0/1 を反転し、0のとき再生処理をスキップする。
        vgm_bank_addr が指定されている場合、再生時にページ2バンクを切り替える。
    """
    if volume is not None and not 0 <= volume <= 15:
        raise ValueError("volume must be between 0 and 15")

    psg_reg_port = 0xA0
    psg_data_port = 0xA1

    def play_vgm_frame_macro(block: Block) -> None:
        loop_reg = unique_label("PLAY_VGM_LOOP")
        next_frame = unique_label("PLAY_VGM_NEXT")
        do_loop = unique_label("PLAY_VGM_DO_LOOP")
        end_label = unique_label("PLAY_VGM_END")

        LD.A_mHL(block)
        INC.HL(block)

        CP.n8(block, 0xFF)
        JR_Z(block, do_loop)

        OR.A(block)
        JR_Z(block, next_frame)

        LD.B_A(block)
        block.label(loop_reg)
        LD.A_mHL(block)
        OUT(block, psg_reg_port)
        INC.HL(block)
        LD.A_mHL(block)
        OUT(block, psg_data_port)
        INC.HL(block)
        DJNZ(block, loop_reg)

        block.label(next_frame)
        LD.mn16_HL(block, vgm_ptr_addr)
        JR(block, end_label)

        block.label(do_loop)
        LD.HL_mn16(block, vgm_loop_addr)
        LD.mn16_HL(block, vgm_ptr_addr)
        block.label(end_label)

    def music_isr(block: Block) -> None:
        process_play = unique_label("PROCESS_PLAY")
        skip_play = unique_label("MUSIC_ISR_SKIP_PLAY")

        LD.A_mn16(block, bgm_enabled_addr)
        OR.A(block)
        JP_NZ(block, process_play)

        # PSGを停止（ミキサー無効化 + 各チャンネル音量0）
        LD.A_n8(block, 0x07)
        OUT(block, psg_reg_port)
        LD.A_n8(block, 0b10111111)
        OUT(block, psg_data_port)

        for reg in (8, 9, 10):
            LD.A_n8(block, reg)
            OUT(block, psg_reg_port)
            LD.A_n8(block, 0)
            OUT(block, psg_data_port)

        RET(block)

        block.label(process_play)
        PUSH.AF(block)
        PUSH.BC(block)
        PUSH.DE(block)
        PUSH.HL(block)
        PUSH.IX(block)
        PUSH.IY(block)
        debug_print_pc(block, "MUSIC_ISR")

        LD.A_mn16(block, vgm_timer_flag_addr)
        XOR.n8(block, 1)
        LD.mn16_A(block, vgm_timer_flag_addr)
        JR_Z(block, skip_play)
        if vgm_bank_addr is not None:
            LD.A_mn16(block, vgm_bank_addr)
            LD.mn16_A(block, page2_bank_reg_addr)
        play_vgm_frame_macro(block)
        if current_bank_addr is not None:
            LD.A_mn16(block, current_bank_addr)
            LD.mn16_A(block, page2_bank_reg_addr)
        block.label(skip_play)

        POP.IY(block)
        POP.IX(block)
        POP.HL(block)
        POP.DE(block)
        POP.BC(block)
        POP.AF(block)

    music_isr_func = Func("MUSIC_ISR", music_isr, group=group)

    def init_music(block: Block) -> None:
        DI(block)
        LD.A_n8(block, 0xC3)
        LD.mn16_A(block, init_music_addr)
        LD.HL_label(block, "MUSIC_ISR")
        LD.mn16_HL(block, (init_music_addr + 1) & 0xFFFF)
        if volume is not None:
            psg_reg_port = 0xA0
            psg_data_port = 0xA1
            for reg in (8, 9, 10):
                LD.A_n8(block, reg)
                OUT(block, psg_reg_port)
                LD.A_n8(block, volume)
                OUT(block, psg_data_port)
        EI(block)

    init_music_func = Func("INIT_MUSIC", init_music, group=group)

    return init_music_func, music_isr_func
