"""SCREEN 0 汎用コンフィグ画面の生成ユーティリティ。

`build_screen0_config_menu` の呼び出し例::

    from mmsxxasmhelper.core import Block
    from mmsxxasmhelper.msxutils import build_update_input_func
    from mmsxxasmhelper.config_scene import (
        Screen0ConfigEntry,
        build_screen0_config_menu,
    )

    block = Block()
    update_input = build_update_input_func()
    init_func, loop_func, table_func = build_screen0_config_menu(
        [
            Screen0ConfigEntry("MODE", ["MSX1", "MSX2"], 0xC200),
            Screen0ConfigEntry("SPEED", ["SLOW", "FAST"], 0xC201),
        ],
        update_input_func=update_input,
    )

    # 必要な順序でコードを配置する
    init_func.emit(block)
    loop_func.emit(block)
    table_func.emit(block)

ゲーム側では `init_func` で VRAM へ UI を構築し、
メインループから `loop_func` を呼び続けるだけで
カーソル移動と左右選択、ESC 抜けが機能する。
オプション値は各項目の ``store_addr`` に 0 起点のインデックスが保持される。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Sequence

from mmsxxasmhelper.core import *
from mmsxxasmhelper.utils import *

from .msxutils import (
    INITXT,
    INPUT_KEY_BIT,
    build_set_vram_write_func,
    set_screen_colors_macro,
    set_text_cursor_macro,
    write_text_with_cursor_macro,
)

__all__ = ["Screen0ConfigEntry", "build_screen0_config_menu"]


@dataclass(frozen=True)
class Screen0ConfigEntry:
    """SCREEN 0 用のコンフィグ項目定義。"""

    name: str
    options: Sequence[str]
    store_addr: int


def get_work_byte_length_for_screen0_config_menu() -> int:
    """SCREEN 0 コンフィグ画面で使用するワークエリアのバイト数を取得する。"""
    return 5  # CURRENT_ENTRY_ADDR, BLINK_STATE_ADDR, PREV_ENTRY_ADDR


def build_screen0_config_menu(
    entries: Sequence[Screen0ConfigEntry] | dict[str, dict[str, object]],
    *,
    update_input_func: Func,
    group: str = DEFAULT_FUNC_GROUP_NAME,
    input_trg_addr: int = 0xC100,
    work_base_addr: int = 0xC101,
    screen0_name_base: int = 0x0000,  # 0 で正しい 替えるとカーソルが消える
    title_lines: Sequence[str] | None = None,
    title_row: int = 0,
    title_centered: bool = True,
    header_lines: Sequence[str] | None = None,
    header_row: int | None = None,
    header_col: int = 2,
    top_row: int = 4,
    label_col: int = 2,
    option_col: int = -1,
    option_field_padding: int = 1,
) -> tuple[Func, Func, Sequence[Func]]:
    """辞書定義から SCREEN 0 のコンフィグ画面を生成する。"""

    def _normalize_entries(
        raw_entries: Sequence[Screen0ConfigEntry] | dict[str, dict[str, object]]
    ) -> list[Screen0ConfigEntry]:
        if isinstance(raw_entries, dict):
            normalized: list[Screen0ConfigEntry] = []
            for key, value in raw_entries.items():
                options = value.get("options") if isinstance(value, dict) else None
                addr = value.get("addr") if isinstance(value, dict) else None
                if options is None or addr is None:
                    raise ValueError(
                        "dict 定義は {'<name>': {'options': [...], 'addr': 0xC200}} の形式にしてください"
                    )
                normalized.append(
                    Screen0ConfigEntry(
                        name=str(key),
                        options=[str(opt) for opt in options],
                        store_addr=int(addr),
                    )
                )
            return normalized
        return list(raw_entries)

    config_entries = _normalize_entries(entries)
    if not config_entries:
        raise ValueError("entries が空です")

    entry_count = len(config_entries)
    option_field_widths = [
        (max(len(opt) for opt in entry.options)) + (option_field_padding * 2)
        for entry in config_entries
    ]

    title_lines = title_lines or ["", "HELP & SETTING", ""]
    title_height = len(title_lines)
    if header_row is None:
        header_row = title_row + title_height

    header_height = len(header_lines or [])
    if header_height:
        header_bottom_row = header_row + header_height - 1
        if top_row <= header_bottom_row:
            top_row = header_bottom_row + 2  # 1 行空けて <SETTING> を表示
    elif title_height:
        title_bottom_row = title_row + title_height - 1
        if top_row <= title_bottom_row:
            top_row = title_bottom_row + 2

    entry_row_base = top_row + 3
    if entry_row_base + entry_count > 24:
        raise ValueError(
            "表示行が SCREEN 0 の 24 行を超えています。top_row や項目数を調整してください"
        )

    if option_col < 0:
        # ラベル列 + 最大ラベル幅 + 2 文字分の余裕
        max_label_width = max(len(entry.name) for entry in config_entries)
        option_col = label_col + max_label_width + 4

    CURRENT_ENTRY_ADDR = work_base_addr
    BLINK_STATE_ADDR = work_base_addr + 1
    PREV_ENTRY_ADDR = work_base_addr + 2
    DRAW_OPT_JT_LABEL = unique_label("__DRAW_OPT_JT__")
    ENTRY_VALUE_ADDR_LABEL = unique_label("__ENTRY_VALUE_ADDR__")
    ENTRY_OPTION_COUNT_LABEL = unique_label("__ENTRY_OPTION_COUNT__")
    ENTRY_OPTION_WIDTH_LABEL = unique_label("__ENTRY_OPTION_WIDTH__")
    ENTRY_ROW_ADDR_LABEL = unique_label("__ENTRY_ROW_ADDR__")
    OPTION_POINTER_LABELS = [unique_label("__OPT_PTR__") for _ in config_entries]

    SET_VRAM_WRITE_FUNC = build_set_vram_write_func(group=group)

    def _emit_write_text(block: Block, col: int, row: int, text: str) -> None:
        print("Emitting write text:", repr(text), f"at ({col},{row})")
        write_text_with_cursor_macro(block, text, col, row)

    def _emit_draw_option(
        block: Block, entry: Screen0ConfigEntry, entry_index: int, option_width_: int
    ) -> None:

        # VRAM のオプション欄に現在値を描画する。
        # 前提: entry.store_addr に項目選択インデックスが格納されている事
        # 破壊: ポインタ計算と VRAM 書き込みのため A/B/C/D/E/H/L を使用し、戻り時も内容は保証しない。
        row = entry_row_base + entry_index
        vram_addr = screen0_name_base + (row * 40) + option_col

        print("Emitting draw option for entry"
              f" {entry.name} index {entry_index} row={row}"
              f" vram:{vram_addr:04X}h store:{entry.store_addr} options={entry.options} width={option_width_}")

        embed_debug_string_macro(
            block,
            f"Draw opt '{entry.name}' v:{vram_addr:04X}h s:{entry.store_addr:04X}h",)

        # [ブロック1] 選択インデックス取得とポインタ解決。
        #   * entry.store_addr から現在値を A に読み出し
        #   * エントリ固有のオプションポインタテーブルまで 2byte ポインタオフセットを求める
        #   * HL をテーブルの該当要素に合わせ、実際の文字列先頭アドレスを DE として退避
        LD.HL_n16(block, entry.store_addr)
        LD.A_mHL(block)
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)  # selection_index * 2
        LD.DE_label(block, OPTION_POINTER_LABELS[entry_index])  # オプション文字列のポインタテーブル
        ADD.HL_DE(block)
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)  # DE = ポインタテーブルから取得した文字列先頭アドレス
        PUSH.DE(block)  # 文字列ポインタを退避

        # [ブロック2] VRAM 書き込みの準備。
        #   * 行・列位置から VRAM アドレスを算出し HL にセット
        #   * 可変長の文字列 + パディングを書き込むため、事前に set_vram_write を呼んでポート 0x98 を開く
        LD.HL_n16(block, vram_addr)
        SET_VRAM_WRITE_FUNC.call(block)

        # [ブロック3] 文字列ポインタ復帰とレジスタ初期化。
        #   * HL を描画対象文字列先頭に戻す
        #   * B に欄幅を設定し、C は VRAM ポート番号を固定して OUT_C 用に備える
        POP.HL(block)  # 文字列ポインタを復帰
        LD.B_n8(block, option_width_)
        LD.C_n8(block, 0x98)  # ★ Cレジスタにポート番号を固定しておく

        LABEL_OPT_WRITE_LOOP = unique_label("__OPT_WRITE_LOOP__")
        LABEL_OPT_PADDING_LOOP = unique_label("__OPT_PADDING_LOOP__")
        LABEL_OPT_PADDING_EXEC = unique_label("__OPT_PADDING_EXEC__")

        if option_field_padding:
            # [ブロック4] 左パディング: 指定されたパディング幅だけ空白を吐き、B(残り幅)を減算。
            LABEL_OPT_LEFT_PADDING = unique_label("__OPT_LEFT_PADDING__")
            LD.D_n8(block, option_field_padding)
            block.label(LABEL_OPT_LEFT_PADDING)  # __OPT_LEFT_PADDING__
            LD.A_n8(block, ord(" "))
            OUT(block, 0x98)
            DEC.B(block)
            DEC.D(block)
            JR_NZ(block, LABEL_OPT_LEFT_PADDING)

        # [ブロック5] 文字列出力ループ: 0 終端まで文字を送り、欄幅カウンタ B を減らす。
        #   * OR A で終端判定し、0 に達したらパディング処理へ
        block.label(LABEL_OPT_WRITE_LOOP)  # __OPT_WRITE_LOOP__
        LD.A_mHL(block)
        OR.A(block)  # 終端判定
        JR_Z(block, LABEL_OPT_PADDING_LOOP)
        OUT_C.A(block)
        INC.HL(block)
        DJNZ(block, LABEL_OPT_WRITE_LOOP) # b-- > 0 まで繰り返し
        RET(block)  # 文字列が欄幅を超えた場合はここで終了

        # b に全体の残り欄幅が入っているので、空白で埋める。
        block.label(LABEL_OPT_PADDING_LOOP)  # __OPT_PADDING_LOOP__
        LD.A_n8(block, ord(" "))
        block.label(LABEL_OPT_PADDING_EXEC)  # __OPT_PADDING_EXEC__
        OUT(block, 0x98)
        DJNZ(block, LABEL_OPT_PADDING_EXEC)  # b-- > 0 まで繰り返し
        RET(block)

    def _emit_option_pointer_table(
        block: Block, entry: Screen0ConfigEntry, label_name: str
    ) -> None:
        # オプション文字列へのポインタテーブルを組み立てる。(定数データの配置のみ）
        # print(f"Emitting option pointer table for entry {entry.name} {label_name}")
        block.label(label_name)  # __OPT_PTR__
        for opt in entry.options:
            LABEL_OPT_STR = unique_label("__OPT_STR__")
            pos = block.emit(0, 0)
            block.add_abs16_fixup(pos, LABEL_OPT_STR)
            block.label(LABEL_OPT_STR)  # __OPT_STR__
            encoded = [ord(ch) & 0xFF for ch in opt]
            encoded.append(0x00)
            DB(block, *encoded)
        """
        ex) AUTO SPD: 0 ~ 7
        [48, 0] /[49, 0] / [50, 0] / [51, 0] / [52, 0] / [53, 0] / [54, 0] / [55, 0]
        ex) BEEP: ON / OFF
        [79, 78, 0] / [79, 70, 70, 0]
        """

    # 各エントリに対応する描画ルーチンをリスト化し、後続のジャンプテーブルや
    # ディスパッチ処理で参照できるようにする。エントリ情報を束縛し、
    # 個々の描画コード生成を遅延実行する設計。
    draw_option_funcs: list[Func] = []
    def _create_draw_option_func(
        func_name: str, entry: Screen0ConfigEntry, entry_index: int, option_width: int
    ) -> Func:
        def draw_option(block: Block) -> None:
            # オプション値の描画ルーチン本体
            _emit_draw_option(block, entry, entry_index, option_width)

        return Func(func_name, draw_option, group=group)

    for idx, entry in enumerate(config_entries):
        option_width = option_field_widths[idx]
        func_name = f"DRAW_OPTION_{idx}"
        draw_option_funcs.append(
            _create_draw_option_func(func_name, entry, idx, option_width)
        )

    def draw_option_dispatch(block: Block) -> None:
        # 選択中の項目インデックス (A) を元に該当する draw_option_funcs(DRAW_OPTION_xx) へ JP する。
        # JP を使うのは、各描画処理がエントリ固有の幅や VRAM 位置をハードコーディングしているため、
        # 呼び出し先でそのまま返らず単純に処理を委譲したい（CALL/RET のオーバーヘッドを避ける）ため。
        # 入力: A に項目インデックス、ジャンプテーブルは DRAW_OPT_JT_LABEL を参照。
        # 破壊: HL/DE/A を使用してエントリを解決し、そのまま JP するためレジスタは復元されない。
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)
        LD.DE_label(block, DRAW_OPT_JT_LABEL)
        ADD.HL_DE(block)  # HL = (index * 2) + DRAW_OPT_JT_LABEL ジャンプ先アドレス計算
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)
        PUSH.DE(block)
        POP.HL(block)  # HL = DE = ジャンプ先アドレス
        JP_mHL(block)  # 実際にジャンプ

    DRAW_OPTION_DISPATCH = Func(
        "DRAW_OPTION_FOR_CURRENT", draw_option_dispatch, group=group
    )

    def update_triangles(block: Block) -> None:
        # 選択中項目の左右インジケータ(< >)を描画し点滅状態を更新する。
        # 入力: CURRENT_ENTRY_ADDR と BLINK_STATE_ADDR に現在の項目と点滅状態が格納されている。
        # 破壊: A/B/C/D/E/H/L を用いて VRAM アドレス計算と描画を行い、戻り時にこれらは保証されない。
        # 追加仕様: 項目が切り替わったときは旧行からインジケータを消してカーソルを移動する。

        # [ブロック0] 現在の項目 (C) と前回描画した項目 (B) を取得し、
        #            変化があれば旧行のインジケータを消去する。
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.C_A(block)
        LD.A_mn16(block, PREV_ENTRY_ADDR)
        LD.B_A(block)

        LABEL_SKIP_CLEAR = unique_label("__SKIP_CLEAR__")
        CP.C(block)
        JR_Z(block, LABEL_SKIP_CLEAR)

        # 旧行のオプション幅を取得して退避。
        LD.L_B(block)
        LD.H_n8(block, 0)
        LD.DE_label(block, ENTRY_OPTION_WIDTH_LABEL)
        ADD.HL_DE(block)
        LD.A_mHL(block)
        PUSH.AF(block)

        # 旧行の VRAM 行先頭アドレスを解決し、左右のインジケータ位置を空白で上書きする。
        LD.L_B(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)
        LD.DE_label(block, ENTRY_ROW_ADDR_LABEL)
        ADD.HL_DE(block)
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)

        PUSH.DE(block)
        PUSH.DE(block)
        POP.HL(block)
        LD.BC_n16(block, option_col - 1)
        ADD.HL_BC(block)
        SET_VRAM_WRITE_FUNC.call(block)
        LD.A_n8(block, ord(" "))
        OUT(block, 0x98)

        POP.DE(block)
        POP.AF(block)
        PUSH.DE(block)
        POP.HL(block)
        LD.BC_n16(block, option_col)
        ADD.HL_BC(block)
        LD.B_n8(block, 0)
        LD.C_A(block)
        ADD.HL_BC(block)
        SET_VRAM_WRITE_FUNC.call(block)
        LD.A_n8(block, ord(" "))
        OUT(block, 0x98)

        block.label(LABEL_SKIP_CLEAR)  # __SKIP_CLEAR__

        # [ブロック1] 現在の項目メタデータ: 項目インデックスからオプション数を取得し、
        # 左右インジケータを描く際の端判定で使う。
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)
        LD.DE_label(block, ENTRY_OPTION_COUNT_LABEL)
        ADD.HL_DE(block)
        LD.B_mHL(block)

        # [ブロック2] 項目の現在値: エントリ値のアドレスを解決し、
        # 現在の選択インデックスを C に保持して後段の描画条件に使う。
        # PUSH/POP で HL を退避復帰し、OUT で直接 VRAM に書けるようレジスタを並べ直す。
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)
        LD.DE_label(block, ENTRY_VALUE_ADDR_LABEL)
        ADD.HL_DE(block)
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)
        PUSH.DE(block)
        POP.HL(block)
        LD.A_mHL(block)
        LD.C_A(block)

        # [ブロック3] 描画対象行: VRAM 上の行アドレスを取得し、左右インジケータ描画で共有する。
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)
        LD.DE_label(block, ENTRY_ROW_ADDR_LABEL)
        ADD.HL_DE(block)
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)

        # [ブロック4] 左インジケータ描画: 行アドレスを復元し、オプション列の直前にカーソルを置く。
        # 「オプション値が 0 ではない（左に進める）」かつ「点滅フラグが 0」の場合だけ "<" を出し、
        # それ以外は空白で消す。
        PUSH.DE(block)
        POP.HL(block)
        PUSH.HL(block)
        LD.BC_n16(block, option_col - 1)
        ADD.HL_BC(block)
        SET_VRAM_WRITE_FUNC.call(block)
        LD.C_n8(block, 0x98)

        # LEFT_VISIBLE = unique_label("__LEFT_VISIBLE__")
        LABEL_LEFT_HIDDEN = unique_label("__LEFT_HIDDEN__")
        LABEL_LEFT_END = unique_label("__LEFT_END__")
        LD.A_C(block)
        OR.A(block)
        JR_Z(block, LABEL_LEFT_HIDDEN)
        LD.A_mn16(block, BLINK_STATE_ADDR)
        BIT.n8_A(block, 0)
        JR_NZ(block, LABEL_LEFT_HIDDEN)
        # block.label(LEFT_VISIBLE)
        LD.A_n8(block, ord("<"))
        OUT_C.A(block)
        JR(block, LABEL_LEFT_END)

        block.label(LABEL_LEFT_HIDDEN)  # __LEFT_HIDDEN__
        LD.A_n8(block, ord("{"))
        OUT_C.A(block)

        block.label(LABEL_LEFT_END)  # __LEFT_END__

        # [ブロック5] オプション欄幅: 文字数を取得し、右側インジケータの列位置計算に使用する。
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.L_A(block)
        LD.H_n8(block, 0)
        LD.DE_label(block, ENTRY_OPTION_WIDTH_LABEL)
        ADD.HL_DE(block)
        LD.A_mHL(block)
        LD.E_A(block)

        # [ブロック6] 右インジケータ描画: 退避した行アドレスにオプション欄の幅を足し、
        # 「最終オプションではない（まだ右がある）」かつ「点滅フラグが 1」の場合だけ ">" を出す。
        # 右に進めない場合や点滅条件外では空白を出して消す。

        POP.HL(block)
        LD.BC_n16(block, option_col)
        ADD.HL_BC(block)
        LD.A_E(block)
        LD.B_n8(block, 0)
        LD.C_A(block)
        ADD.HL_BC(block)
        SET_VRAM_WRITE_FUNC.call(block)
        LD.C_n8(block, 0x98)

        # RIGHT_VISIBLE = unique_label("__RIGHT_VISIBLE__")
        LABEL_RIGHT_HIDDEN = unique_label("__RIGHT_HIDDEN__")
        LABEL_RIGHT_END = unique_label("__RIGHT_END__")

        LD.A_B(block)
        DEC.A(block)
        CP.C(block)
        JR_Z(block, LABEL_RIGHT_HIDDEN)
        JP_M(block, LABEL_RIGHT_HIDDEN)
        LD.A_mn16(block, BLINK_STATE_ADDR)
        BIT.n8_A(block, 0)
        JR_Z(block, LABEL_RIGHT_HIDDEN)
        # block.label(RIGHT_VISIBLE)
        LD.A_n8(block, ord(">"))
        OUT_C.A(block)
        JR(block, LABEL_RIGHT_END)

        block.label(LABEL_RIGHT_HIDDEN)  # __RIGHT_HIDDEN__
        LD.A_n8(block, ord("}"))
        OUT_C.A(block)

        block.label(LABEL_RIGHT_END)  # __RIGHT_END__
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.mn16_A(block, PREV_ENTRY_ADDR)
        RET(block)

    UPDATE_TRIANGLE_FUNC = Func(
        "UPDATE_TRIANGLES", update_triangles, group=group
    )

    def adjust_option(block: Block, delta: int) -> None:
        # 現在の項目値を +/-1 し、表示とインジケータを更新する。
        # 入力: CURRENT_ENTRY_ADDR から項目インデックスを取得し、ENTRY_VALUE_ADDR_LABEL の値を書き換える。
        # 破壊: A/B/C/D/E/H/L を使用して範囲チェック・書き込み・再描画を行うため、戻り時に内容は保持されない。
        LABEL_ADJUST_END = unique_label("__ADJUST_END__")
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.C_A(block)

        # 現在の項目インデックスを DE に退避しつつ、後のテーブル参照に備える。
        LD.E_A(block)
        LD.D_n8(block, 0)

        # 値テーブルの 16bit ポインタ位置を算出 (インデックス * 2)。
        LD.A_E(block)
        ADD.A_A(block)
        LD.E_A(block)
        LD.HL_label(block, ENTRY_VALUE_ADDR_LABEL)
        ADD.HL_DE(block)

        # HL が指す現在値のワードを DE に読み出す。
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)

        # 選択肢数テーブルのアドレスを HL に準備 (インデックスオフセット)。
        LD.A_C(block)
        LD.L_A(block)
        LD.H_n8(block, 0)
        LD.DE_label(block, ENTRY_OPTION_COUNT_LABEL)
        ADD.HL_DE(block)
        LD.B_mHL(block)

        # 現在値 A と上限 B を比較し、増減処理を行う。
        LD.A_mDE(block)
        if delta > 0:
            DEC.B(block)  # 最大インデックス
            CP.B(block)
            JR_NC(block, LABEL_ADJUST_END)
            INC.A(block)
        else:
            OR.A(block)
            JR_Z(block, LABEL_ADJUST_END)
            DEC.A(block)

        # 更新した値をテーブルへ書き戻し、現在値インデックスも保存する。
        LD.mDE_A(block)
        LD.A_C(block)
        LD.mn16_A(block, CURRENT_ENTRY_ADDR)

        # 値の描画とカーソル形状を再描画する。
        LD.A_C(block)
        DRAW_OPTION_DISPATCH.call(block)  # JP DRAW_OPTION_{index=a}
        UPDATE_TRIANGLE_FUNC.call(block)
        block.label(LABEL_ADJUST_END)  # __ADJUST_END__
        RET(block)

    ADJUST_OPTION_PLUS = Func(
        "ADJUST_OPTION_PLUS", lambda b: adjust_option(b, +1), group=group
    )
    ADJUST_OPTION_MINUS = Func(
        "ADJUST_OPTION_MINUS", lambda b: adjust_option(b, -1), group=group
    )

    def init_config_screen(block: Block) -> None:
        # SCREEN0 に初期 UI を構築し、内部ワークも初期化する初期化ルーチン。
        # 入力: 特定のレジスタ前提はなく、定数とエントリ定義を参照する。
        # 破壊: 描画のため A/B/C/D/E/H/L を広範に使用し、戻り時の内容は保証しない。
        CALL(block, INITXT)
        set_screen_colors_macro(block, 15, 0, 0, current_screen_mode=0)

        if title_lines:
            for idx, line in enumerate(title_lines):
                if not line:
                    continue
                if title_centered:
                    col = max((40 - len(line)) // 2, 0)
                else:
                    col = header_col
                _emit_write_text(block, col, title_row + idx, line)

        for idx, line in enumerate(header_lines or []):
            _emit_write_text(block, header_col, header_row + idx, line)

        _emit_write_text(block, label_col, top_row, "<SETTING>")
        _emit_write_text(block, label_col, top_row + 1, "UP/DOWN/LEFT/RIGHT: CHANGE SETTINGS")

        # 入力が届く前に、保持されている設定値が有効範囲内かを確認する。
        # 想定外の値が入っていると描画や増減が正しく動かないため、
        # 範囲外なら 0 に初期化してから描画する。
        for idx, entry in enumerate(config_entries):
            block.label(unique_label("__SANITIZE_ENTRY__"))
            LD.HL_n16(block, entry.store_addr)
            LD.A_mHL(block)
            CP.n8(block, len(entry.options))

            LABEL_VALUE_VALID = unique_label("__VALUE_VALID__")
            JR_C(block, LABEL_VALUE_VALID)

            XOR.A(block)
            LD.mHL_A(block)

            block.label(LABEL_VALUE_VALID)

        for idx, entry in enumerate(config_entries):
            _emit_write_text(block, label_col, entry_row_base + idx, f"{entry.name}:")
            draw_option_funcs[idx].call(block)

        LD.A_n8(block, 0)
        LD.mn16_A(block, CURRENT_ENTRY_ADDR)
        LD.mn16_A(block, BLINK_STATE_ADDR)
        LD.mn16_A(block, PREV_ENTRY_ADDR)
        UPDATE_TRIANGLE_FUNC.call(block)
        RET(block)

    def run_config_loop(block: Block) -> None:
        # 入力状態をポーリングしてカーソル移動・値変更・終了判定を行うメインループ。
        # 入力: update_input_func が input_hold_addr/input_trg_addr を更新していることを前提に動作。
        # 破壊: A/B/C/D/E/H/L を用いて入力判定と描画を行い、ループ継続時も内容は保持されない。
        LABEL_CONFIG_LOOP = unique_label("__CONFIG_LOOP__")
        block.label(LABEL_CONFIG_LOOP)  # __CONFIG_LOOP__
        # 1) フレーム待ちして入力状態を更新。
        HALT(block)
        update_input_func.call(block)

        # 2) ESC キーが押されたらループを抜けて呼び出し元に戻る。
        LD.A_mn16(block, input_trg_addr)
        BIT.n8_A(block, INPUT_KEY_BIT.L_ESC)
        RET_NZ(block)

        # 3) UP キーで項目をひとつ上に移動し、表示と三角マーカーを更新。
        LD.A_mn16(block, input_trg_addr)
        BIT.n8_A(block, INPUT_KEY_BIT.L_UP)
        LABEL_SKIP_UP = unique_label("__SKIP_UP__")
        JR_Z(block, LABEL_SKIP_UP)
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        OR.A(block)  # 現在位置が 0 なら移動しない
        JR_Z(block, LABEL_SKIP_UP)
        DEC.A(block)
        LD.mn16_A(block, CURRENT_ENTRY_ADDR)
        DRAW_OPTION_DISPATCH.call(block)  # JP DRAW_OPTION_{index=a}
        UPDATE_TRIANGLE_FUNC.call(block)  # インジケータ更新
        block.label(LABEL_SKIP_UP)  # __SKIP_UP__

        # 4) DOWN キーで項目をひとつ下に移動し、表示と三角マーカーを更新。
        LD.A_mn16(block, input_trg_addr)
        BIT.n8_A(block, INPUT_KEY_BIT.L_DOWN)
        LABEL_SKIP_DOWN = unique_label("__SKIP_DOWN__")
        JR_Z(block, LABEL_SKIP_DOWN)
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        INC.A(block)
        CP.n8(block, entry_count)  # 範囲チェック
        JR_NC(block, LABEL_SKIP_DOWN)
        LD.mn16_A(block, CURRENT_ENTRY_ADDR)
        DRAW_OPTION_DISPATCH.call(block)  # JP DRAW_OPTION_{index=a}
        UPDATE_TRIANGLE_FUNC.call(block)  # インジケータ更新
        block.label(LABEL_SKIP_DOWN)  # __SKIP_DOWN__

        # 5) LEFT キーで現在項目の値を減少させる。
        LD.A_mn16(block, input_trg_addr)
        BIT.n8_A(block, INPUT_KEY_BIT.L_LEFT)
        LABEL_SKIP_LEFT = unique_label("__SKIP_LEFT__")
        JR_Z(block, LABEL_SKIP_LEFT)
        ADJUST_OPTION_MINUS.call(block)
        block.label(LABEL_SKIP_LEFT)  # __SKIP_LEFT__

        # 6) RIGHT キーで現在項目の値を増加させる。
        LD.A_mn16(block, input_trg_addr)
        BIT.n8_A(block, INPUT_KEY_BIT.L_RIGHT)
        LABEL_SKIP_RIGHT = unique_label("__SKIP_RIGHT__")
        JR_Z(block, LABEL_SKIP_RIGHT)
        ADJUST_OPTION_PLUS.call(block)
        block.label(LABEL_SKIP_RIGHT)  # __SKIP_RIGHT__

        # 7) ブリンク状態をトグルし、インジケータ描画を更新。
        LD.A_mn16(block, BLINK_STATE_ADDR)
        LD.B_n8(block, 1)
        XOR.B(block)
        LD.mn16_A(block, BLINK_STATE_ADDR)
        UPDATE_TRIANGLE_FUNC.call(block)

        # 8) ループの先頭に戻って次の入力を待つ。
        JP(block, LABEL_CONFIG_LOOP)

    def emit_tables1(block: Block) -> None:
        # 各種ジャンプテーブルや定数テーブルを ROM/RAM に配置するデータ出力ルーチン。
        # 入力: レジスタ前提はなく、定義済みのエントリ配列からテーブルを生成する。
        # 破壊: データ出力のみで CPU レジスタへの影響は想定しない (Block への emit のみ)。

        # 1) オプション描画関数へのジャンプテーブルを生成し、描画ディスパッチ用のエントリ点をまとめる。
        block.label(DRAW_OPT_JT_LABEL)  # __DRAW_OPT_JT__
        for func in draw_option_funcs:  # 2 x エントリ bytes
            pos = block.emit(0, 0)
            block.add_abs16_fixup(pos, func.name)

    def emit_tables2(block: Block) -> None:

        # 2) 各設定項目の現在値が格納されるワードアドレスを並べたテーブルを出力する。
        block.label(ENTRY_VALUE_ADDR_LABEL)  # __ENTRY_VALUE_ADDR__
        for entry in config_entries:  # 2 x エントリ bytes
            DW(block, entry.store_addr & 0xFFFF)

    def emit_tables3(block: Block) -> None:

        # 3) 各設定項目に用意されている選択肢の数をバイトで出力し、範囲チェックに利用する。
        block.label(ENTRY_OPTION_COUNT_LABEL)  # __ENTRY_OPTION_COUNT__
        for entry in config_entries:   # 1 x エントリ bytes
            DB(block, len(entry.options) & 0xFF)

    def emit_tables4(block: Block) -> None:

        # 4) 表示時に利用するオプション欄の幅 (文字数) を並べておき、描画幅を決定する。
        block.label(ENTRY_OPTION_WIDTH_LABEL)  # __ENTRY_OPTION_WIDTH__
        for width in option_field_widths:
            DB(block, width & 0xFF)  # 2 x エントリ bytes

    def emit_tables5(block: Block) -> None:

        # 5) 各設定項目が配置される画面上の行先頭 VRAM アドレスを計算してテーブル化する。
        block.label(ENTRY_ROW_ADDR_LABEL)  # __ENTRY_ROW_ADDR__
        for idx in range(entry_count):
            row_addr = screen0_name_base + ((entry_row_base + idx) * 40)
            DW(block, row_addr & 0xFFFF)  # 2 x エントリ bytes
            print(f"Entry {idx} row addr: {row_addr:04X}h")

    def emit_tables6(block: Block) -> None:

        # 6) オプション文字列のポインタテーブルを生成し、選択肢描画時に参照できるようにする。
        for idx, entry in enumerate(config_entries):
            # アドレス2文字 + 選択肢文字数 + 終端文字(0h)
            _emit_option_pointer_table(block, entry, OPTION_POINTER_LABELS[idx])

    # print(f"len(draw_option_funcs) = {len(draw_option_funcs)}")
    # print(f"len(entries) = {len(config_entries)}")
    # print(f"len(option_field_widths) = {len(option_field_widths)}")
    # print(f"len(config_entries) = {len(config_entries)}")
    # print(f"entry_count = {entry_count}")

    # 各 Func の外部からの呼び出し規約と推奨配置順。
    # * INIT_FUNC (CONFIG_SCREEN0_INIT)
    #   - 役割: VRAM へ UI を構築し、ワーク領域を初期化する。
    #   - 呼び出し順: CONFIG 画面を開く直前に 1 度だけ CALL する。
    #   - レジスタ前提: 事前条件なし。描画のため A/B/C/D/E/H/L を破壊する。
    # * RUN_LOOP_FUNC (CONFIG_SCREEN0_LOOP)
    #   - 役割: 入力を監視し、カーソル移動・値変更・ESC 脱出を処理するメインループ。
    #   - 呼び出し順: INIT_FUNC の後、画面を表示している間はフレーム毎など適宜 CALL する。
    #   - レジスタ前提: update_input_func が input_hold_addr/input_trg_addr を更新していること。
    #                     A/B/C/D/E/H/L を破壊する前提で、呼び出し元で必要なら退避する。
    # * TABLE_FUNC (CONFIG_SCREEN0_TABLES)
    #   - 役割: ジャンプテーブルやオプション文字列などの定数データを出力する。
    #   - 呼び出し順: INIT_FUNC と RUN_LOOP_FUNC が参照するため、同一 ROM/BANK 内に配置し、
    #                 これらのコードと併せて emit(block) する。配置順は INIT → LOOP → TABLES が目安。
    #   - レジスタ前提: データ出力のみでレジスタへの副作用なし。

    INIT_FUNC = Func("CONFIG_SCREEN0_INIT", init_config_screen, group=group)
    RUN_LOOP_FUNC = Func("CONFIG_SCREEN0_LOOP", run_config_loop, group=group)
    TABLE_FUNC1 = Func(
        "OPTION_JP_TABLES",
        emit_tables1,
        no_auto_ret=True,
        group=group,
    )
    TABLE_FUNC2 = Func(
        "OPTION_VALUE_ADDR_TABLES",
        emit_tables2,
        no_auto_ret=True,
        group=group,
    )
    TABLE_FUNC3 = Func(
        "OPTION_SELECTION_COUNT_TABLES",
        emit_tables3,
        no_auto_ret=True,
        group=group,
    )
    TABLE_FUNC4 = Func(
        "OPTION_MAX_WIDTH_TABLES",
        emit_tables4,
        no_auto_ret=True,
        group=group,
    )
    TABLE_FUNC5 = Func(
        "OPTION_VRAM_ADDR_TABLES",
        emit_tables5,
        no_auto_ret=True,
        group=group,
    )
    TABLE_FUNC6 = Func(
        "OPTION_STRING_POINTER_TABLES",
        emit_tables6,
        no_auto_ret=True,
        group=group,
    )

    return INIT_FUNC, RUN_LOOP_FUNC, [TABLE_FUNC1, TABLE_FUNC2, TABLE_FUNC3, TABLE_FUNC4, TABLE_FUNC5, TABLE_FUNC6]
