"""
PSGストリーム再生ユーティリティ
"""

from __future__ import annotations

from mmsxxasmhelper.core import (
    Block,
    CP,
    DEFAULT_FUNC_GROUP_NAME,
    DJNZ,
    Func,
    INC,
    JR_Z,
    LD,
    OR,
    OUT,
    RET,
    unique_label,
)

__all__ = ["build_play_vgm_frame_func"]


def build_play_vgm_frame_func(
    vgm_ptr_addr: int,
    vgm_loop_addr: int,
    *,
    group: str = DEFAULT_FUNC_GROUP_NAME,
) -> Func:
    """
    VGMフレームを1回分再生する関数を生成する。

    ※この実装は処理が重くなった際の事を考えていないので、再生がとまったりお遅くなったりします。
    参考実装で水。

    入力:
        HL = (VGM_PTR) アドレス（現在のVGMストリーム位置）
    """

    def play_vgm_frame(block: Block) -> None:
        loop_reg = unique_label("PLAY_VGM_LOOP")
        next_frame = unique_label("PLAY_VGM_NEXT")
        do_loop = unique_label("PLAY_VGM_DO_LOOP")
        psg_reg_port = 0xA0
        psg_data_port = 0xA1

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
        RET(block)

        block.label(do_loop)
        LD.HL_mn16(block, vgm_loop_addr)
        LD.mn16_HL(block, vgm_ptr_addr)
        RET(block)

    return Func("PLAY_VGM_FRAME", play_vgm_frame, no_auto_ret=True, group=group)
