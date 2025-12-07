"""Helper functions for assembling common MSX Z80 mnemonics.

The module exposes every mnemonic listed in ``techdocs/z80_assembly_byte_map.md``
as a dynamically generated callable. Placeholders such as ``n``, ``nn``, and ``e``
are converted to function arguments in the order they appear in the mnemonic.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Sequence

# Instruction specifications based on techdocs/z80_assembly_byte_map.md
# Placeholders use a leading colon and are later substituted with encoded values.
_INSTRUCTION_SET: Dict[str, Sequence[str]] = {
    # Single byte instructions
    "NOP": ["00"],
    "HALT": ["76"],
    "RLCA": ["07"],
    "RRCA": ["0F"],
    "RLA": ["17"],
    "RRA": ["1F"],
    "DAA": ["27"],
    "CPL": ["2F"],
    "SCF": ["37"],
    "CCF": ["3F"],
    "EX DE,HL": ["EB"],
    "DI": ["F3"],
    "EI": ["FB"],
    # 8-bit load
    "LD A,n": ["3E", ":n"],
    "LD B,n": ["06", ":n"],
    "LD C,n": ["0E", ":n"],
    "LD D,n": ["16", ":n"],
    "LD E,n": ["1E", ":n"],
    "LD H,n": ["26", ":n"],
    "LD L,n": ["2E", ":n"],
    "LD (HL),n": ["36", ":n"],
    "LD A,(HL)": ["7E"],
    "LD (HL),A": ["77"],
    "LD A,(BC)": ["0A"],
    "LD A,(DE)": ["1A"],
    "LD (BC),A": ["02"],
    "LD (DE),A": ["12"],
    # 16-bit load
    "LD BC,nn": ["01", ":nn"],
    "LD DE,nn": ["11", ":nn"],
    "LD HL,nn": ["21", ":nn"],
    "LD SP,nn": ["31", ":nn"],
    "LD HL,(nn)": ["2A", ":nn"],
    "LD (nn),HL": ["22", ":nn"],
    "LD SP,HL": ["F9"],
    "LD HL,SP+e": ["F8", ":e"],
    "PUSH BC": ["C5"],
    "PUSH DE": ["D5"],
    "PUSH HL": ["E5"],
    "PUSH AF": ["F5"],
    "POP BC": ["C1"],
    "POP DE": ["D1"],
    "POP HL": ["E1"],
    "POP AF": ["F1"],
    # Arithmetic immediate
    "ADD A,n": ["C6", ":n"],
    "ADC A,n": ["CE", ":n"],
    "SUB n": ["D6", ":n"],
    "SBC A,n": ["DE", ":n"],
    "AND n": ["E6", ":n"],
    "XOR n": ["EE", ":n"],
    "OR n": ["F6", ":n"],
    "CP n": ["FE", ":n"],
    # 16-bit arithmetic
    "ADD HL,BC": ["09"],
    "ADD HL,DE": ["19"],
    "ADD HL,HL": ["29"],
    "ADD HL,SP": ["39"],
    "INC BC": ["03"],
    "DEC BC": ["0B"],
    "INC DE": ["13"],
    "DEC DE": ["1B"],
    "INC HL": ["23"],
    "DEC HL": ["2B"],
    "INC SP": ["33"],
    "DEC SP": ["3B"],
    # Branch
    "DJNZ e": ["10", ":e"],
    "JR e": ["18", ":e"],
    "JR NZ,e": ["20", ":e"],
    "JR Z,e": ["28", ":e"],
    "JR NC,e": ["30", ":e"],
    "JR C,e": ["38", ":e"],
    "JP nn": ["C3", ":nn"],
    "JP NZ,nn": ["C2", ":nn"],
    "JP Z,nn": ["CA", ":nn"],
    "JP NC,nn": ["D2", ":nn"],
    "JP C,nn": ["DA", ":nn"],
    "JP PO,nn": ["E2", ":nn"],
    "JP PE,nn": ["EA", ":nn"],
    "JP P,nn": ["F2", ":nn"],
    "JP M,nn": ["FA", ":nn"],
    "JP (HL)": ["E9"],
    "CALL nn": ["CD", ":nn"],
    "CALL NZ,nn": ["C4", ":nn"],
    "CALL Z,nn": ["CC", ":nn"],
    "CALL NC,nn": ["D4", ":nn"],
    "CALL C,nn": ["DC", ":nn"],
    "CALL PO,nn": ["E4", ":nn"],
    "CALL PE,nn": ["EC", ":nn"],
    "CALL P,nn": ["F4", ":nn"],
    "CALL M,nn": ["FC", ":nn"],
    "RET": ["C9"],
    "RET NZ": ["C0"],
    "RET Z": ["C8"],
    "RET NC": ["D0"],
    "RET C": ["D8"],
    "RET PO": ["E0"],
    "RET PE": ["E8"],
    "RET P": ["F0"],
    "RET M": ["F8"],
    "RST 00H": ["C7"],
    "RST 08H": ["CF"],
    "RST 10H": ["D7"],
    "RST 18H": ["DF"],
    "RST 20H": ["E7"],
    "RST 28H": ["EF"],
    "RST 30H": ["F7"],
    "RST 38H": ["FF"],
    # Bit operations
    "RL B": ["CB", "10"],
    "RR B": ["CB", "18"],
    "SLA B": ["CB", "20"],
    "SRA B": ["CB", "28"],
    "SRL B": ["CB", "38"],
    "BIT 0,B": ["CB", "40"],
    "BIT 7,A": ["CB", "7F"],
    "RES 0,(HL)": ["CB", "86"],
    "SET 7,(HL)": ["CB", "FE"],
    # Block transfer / compare
    "LDI": ["ED", "A0"],
    "LDD": ["ED", "A8"],
    "LDIR": ["ED", "B0"],
    "LDDR": ["ED", "B8"],
    "CPI": ["ED", "A1"],
    "CPIR": ["ED", "B1"],
    "CPD": ["ED", "A9"],
    "CPDR": ["ED", "B9"],
}

_PLACEHOLDER_ENCODERS = {
    "n": lambda value: _encode_unsigned(value, 0xFF, "n"),
    "nn": lambda value: _encode_unsigned(value, 0xFFFF, "nn", width=2),
    "e": lambda value: _encode_signed_offset(value),
}


def _encode_unsigned(value: int, max_value: int, name: str, width: int = 1) -> List[int]:
    integer = int(value)
    if integer < 0 or integer > max_value:
        raise ValueError(f"Operand '{name}' must be between 0 and {max_value}")
    bytes_out = []
    for _ in range(width):
        bytes_out.append(integer & 0xFF)
        integer >>= 8
    return bytes_out


def _encode_signed_offset(value: int) -> List[int]:
    integer = int(value)
    if integer < -128 or integer > 127:
        raise ValueError("Operand 'e' must be a signed 8-bit value (-128..127)")
    return [(integer + 256) % 256]


def _placeholders_for(mnemonic: str) -> List[str]:
    return [token[1:] for token in _INSTRUCTION_SET[mnemonic] if token.startswith(":")]


def assemble(mnemonic: str, /, **operands: int) -> bytes:
    """Assemble a mnemonic into machine bytes.

    Parameters
    ----------
    mnemonic:
        The assembly mnemonic string such as ``"LD A,n"``.
    operands:
        Keyword arguments for any placeholders (``n``, ``nn``, or ``e``).

    Returns
    -------
    bytes
        The assembled machine code.
    """

    if mnemonic not in _INSTRUCTION_SET:
        raise KeyError(f"Unsupported mnemonic: {mnemonic}")

    spec = _INSTRUCTION_SET[mnemonic]
    placeholders = _placeholders_for(mnemonic)

    missing = [name for name in placeholders if name not in operands]
    if missing:
        raise KeyError(f"Missing operands for mnemonic '{mnemonic}': {', '.join(missing)}")

    unexpected = set(operands) - set(placeholders)
    if unexpected:
        raise KeyError(f"Unexpected operands for mnemonic '{mnemonic}': {', '.join(sorted(unexpected))}")

    assembled: List[int] = []
    for token in spec:
        if token.startswith(":"):
            name = token[1:]
            encoder = _PLACEHOLDER_ENCODERS[name]
            assembled.extend(encoder(operands[name]))
        else:
            assembled.append(int(token, 16))

    return bytes(assembled)


def available_mnemonics() -> List[str]:
    """Return a sorted list of supported mnemonics."""

    return sorted(_INSTRUCTION_SET.keys())


def _mnemonic_to_identifier(mnemonic: str) -> str:
    identifier = "".join(ch if ch.isalnum() else "_" for ch in mnemonic)
    return identifier.strip("_")


_IDENTIFIER_TO_MNEMONIC = {
    _mnemonic_to_identifier(mnemonic): mnemonic for mnemonic in _INSTRUCTION_SET
}
__all__ = ["assemble", "available_mnemonics"] + sorted(_IDENTIFIER_TO_MNEMONIC.keys())


def __getattr__(name: str) -> Callable[..., bytes]:
    if name not in _IDENTIFIER_TO_MNEMONIC:
        raise AttributeError(name)

    mnemonic = _IDENTIFIER_TO_MNEMONIC[name]
    placeholder_order = _placeholders_for(mnemonic)

    def assembler(*args: int, **kwargs: int) -> bytes:
        if args and len(args) > len(placeholder_order):
            raise TypeError(
                f"'{name}' accepts at most {len(placeholder_order)} positional operands"
            )

        merged = dict(zip(placeholder_order, args))
        merged.update(kwargs)
        return assemble(mnemonic, **merged)

    assembler.__name__ = name
    assembler.__doc__ = (
        f"Assemble '{mnemonic}'.\n"
        f"Positional arguments map to operands: {', '.join(placeholder_order) if placeholder_order else 'none'}."
    )
    return assembler
