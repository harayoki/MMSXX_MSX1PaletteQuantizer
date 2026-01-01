from __future__ import annotations

from mmsxxasmhelper.core import (
    ADD,
    BIT,
    CALL,
    CP,
    HALT,
    INC,
    JP,
    JP_NZ,
    JP_Z,
    JR,
    JR_NZ,
    JR_Z,
    JR_C,
    LD,
    OR,
    RET,
    SUB,
    DEC,
    XOR,
    Block,
    Func,
    DEFAULT_FUNC_GROUP_NAME,
    unique_label,
)
from mmsxxasmhelper.msxutils import (
    CHPUT,
    INITXT,
    INPUT_KEY_BIT,
    set_screen_colors_macro,
    set_text_cursor_macro,
    write_text_with_cursor_macro,
)


def build_title_screen_func(
    countdown_seconds: int,
    *,
    subtitle_text: str,
    title_logo_text: str | None = None,
    logo_insert_text: str | None = None,
    input_trg_addr: int,
    title_seconds_remaining_addr: int,
    title_frame_counter_addr: int,
    title_countdown_digits_addr: int,
    update_input_func: Func,
    group: str = DEFAULT_FUNC_GROUP_NAME,
) -> Func:
    countdown_seconds = max(0, min(countdown_seconds, 255))

    default_logo_text = (
        r" __  __ __  __  ______  ____  __" + "\n"
        r"|  \/  |  \/  |/ ___\ \/ /\ \/ /" + "\n"
        r"| |\/| | |\/| |\___  \  /  \  / " + "\n"
        r"| |  | | |  | |___/  /  \  /  \ " + "\n"
        r"|_|  |_|_|  |_|_____/_/\_\/_/\_\ "
    )
    logo_insert_text = (
        logo_insert_text if logo_insert_text is not None else subtitle_text
    )
    logo_body_text = (title_logo_text or default_logo_text).rstrip("\n")
    logo_full_text = (
        f"{logo_body_text}\n\n{logo_insert_text}" if logo_body_text else logo_insert_text
    )
    logo_lines = logo_full_text.rstrip("\n").split("\n") if logo_full_text else []
    title_logo_width = max((len(line) for line in logo_lines), default=0)
    title_logo_x = (40 - title_logo_width) // 2 if logo_lines else 0
    title_logo_y = 2 if logo_lines else 0
    title_subtext_lines = [
        "PUSH SPACE to start.",
        "PUSH ESC to settings / help.",
    ]
    title_subtext_x = [(40 - len(line)) // 2 for line in title_subtext_lines]
    title_subtext_y = title_logo_y + len(logo_lines) + 1 if logo_lines else 2
    title_countdown_text = "Starting in    sec."
    title_countdown_x = (40 - len(title_countdown_text)) // 2
    title_countdown_y = title_subtext_y + len(title_subtext_lines) + 1
    title_countdown_digit_x = title_countdown_x + len("Starting in")
    title_frame_ticks = 60
    title_digit_count = 3

    chsns = 0x009C
    chget = 0x009F
    esc_code = 0x1B

    def write_countdown_digits(block: Block) -> None:
        HUND_LOOP = unique_label("COUNTDOWN_HUND_LOOP")
        TENS_LOOP = unique_label("COUNTDOWN_TENS_LOOP")
        ONES_READY = unique_label("COUNTDOWN_ONES_READY")
        HUND_DONE = unique_label("COUNTDOWN_HUND_DONE")
        TENS_DONE = unique_label("COUNTDOWN_TENS_DONE")

        set_text_cursor_macro(block, title_countdown_digit_x, title_countdown_y)

        LD.A_mn16(block, title_seconds_remaining_addr)
        LD.B_n8(block, 0)

        block.label(HUND_LOOP)
        CP.n8(block, 100)
        JR_C(block, TENS_LOOP)
        SUB.n8(block, 100)
        INC.B(block)
        JR(block, HUND_LOOP)

        block.label(TENS_LOOP)
        LD.C_n8(block, 0)

        TENS_LOOP_INNER = unique_label("COUNTDOWN_TENS_LOOP_INNER")
        block.label(TENS_LOOP_INNER)
        CP.n8(block, 10)
        JR_C(block, ONES_READY)
        SUB.n8(block, 10)
        INC.C(block)
        JR(block, TENS_LOOP_INNER)

        block.label(ONES_READY)
        LD.D_A(block)

        HUND_NON_ZERO = unique_label("COUNTDOWN_HUND_NON_ZERO")
        block.label(HUND_NON_ZERO)
        LD.A_B(block)
        OR.A(block)
        JR_NZ(block, HUND_NON_ZERO + "_VAL")
        LD.A_n8(block, ord(" "))
        JR(block, HUND_DONE)
        block.label(HUND_NON_ZERO + "_VAL")
        LD.A_B(block)
        ADD.A_n8(block, ord("0"))
        block.label(HUND_DONE)
        LD.mn16_A(block, title_countdown_digits_addr)

        TENS_NON_ZERO = unique_label("COUNTDOWN_TENS_NON_ZERO")
        block.label(TENS_NON_ZERO)
        LD.A_B(block)
        OR.A(block)
        JR_NZ(block, TENS_NON_ZERO + "_VAL")
        LD.A_C(block)
        OR.A(block)
        JR_NZ(block, TENS_NON_ZERO + "_VAL")
        LD.A_n8(block, ord(" "))
        JR(block, TENS_DONE)
        block.label(TENS_NON_ZERO + "_VAL")
        LD.A_C(block)
        ADD.A_n8(block, ord("0"))
        block.label(TENS_DONE)
        LD.mn16_A(block, title_countdown_digits_addr + 1)

        LD.A_D(block)
        ADD.A_n8(block, ord("0"))
        LD.mn16_A(block, title_countdown_digits_addr + 2)

        for idx in range(title_digit_count):
            LD.A_mn16(block, title_countdown_digits_addr + idx)
            CALL(block, CHPUT)

    def title_screen(block: Block) -> None:
        CALL(block, INITXT)
        set_screen_colors_macro(block, 15, 0, 0, current_screen_mode=0)

        if logo_lines:
            write_text_with_cursor_macro(
                block, "\n".join(logo_lines), title_logo_x, title_logo_y
            )
        for idx, line in enumerate(title_subtext_lines):
            write_text_with_cursor_macro(
                block, line, title_subtext_x[idx], title_subtext_y + idx
            )
        write_text_with_cursor_macro(
            block, title_countdown_text, title_countdown_x, title_countdown_y
        )

        if countdown_seconds > 0:
            LD.A_n8(block, countdown_seconds & 0xFF)
        else:
            XOR.A(block)
        LD.mn16_A(block, title_seconds_remaining_addr)
        LD.A_n8(block, title_frame_ticks & 0xFF)
        LD.mn16_A(block, title_frame_counter_addr)

        write_countdown_digits(block)

        EXIT_START = unique_label("TITLE_EXIT_START")
        EXIT_ESC = unique_label("TITLE_EXIT_ESC")
        LOOP_LABEL = unique_label("TITLE_LOOP")
        block.label(LOOP_LABEL)
        HALT(block)
        update_input_func.call(block)

        CALL(block, chsns)
        JR_Z(block, "TITLE_SKIP_KBD")
        CALL(block, chget)
        CP.n8(block, esc_code)
        JP_Z(block, EXIT_ESC)
        block.label("TITLE_SKIP_KBD")

        LD.A_mn16(block, input_trg_addr)
        BIT.n8_A(block, INPUT_KEY_BIT.L_BTN_A)
        JP_NZ(block, EXIT_START)

        if countdown_seconds > 0:
            LD.A_mn16(block, title_frame_counter_addr)
            DEC.A(block)
            LD.mn16_A(block, title_frame_counter_addr)
            FRAME_WAIT = unique_label("TITLE_FRAME_WAIT")
            JR_Z(block, FRAME_WAIT)
            JP(block, LOOP_LABEL)

            block.label(FRAME_WAIT)
            LD.A_n8(block, title_frame_ticks & 0xFF)
            LD.mn16_A(block, title_frame_counter_addr)
            LD.A_mn16(block, title_seconds_remaining_addr)
            DEC.A(block)
            LD.mn16_A(block, title_seconds_remaining_addr)
            CP.n8(block, 0xFF)
            JP_Z(block, EXIT_START)
            write_countdown_digits(block)

        JP(block, LOOP_LABEL)

        block.label(EXIT_ESC)
        LD.A_n8(block, 1)
        RET(block)

        block.label(EXIT_START)
        XOR.A(block)
        RET(block)

    return Func("TITLE_SCREEN", title_screen, group=group)

