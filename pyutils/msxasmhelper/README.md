# msxasmhelper

`msxasmhelper` is a tiny utility library that exposes MSX Z80 mnemonics as Python callables. It focuses on the instructions listed in [`techdocs/z80_assembly_byte_map.md`](../../techdocs/z80_assembly_byte_map.md) and returns the corresponding machine bytes so you can quickly build small programs or ROM snippets.

## Installation

```
pip install msxasmhelper
```

For local development inside this repository:

```
pip install -e pyutils/msxasmhelper
```

## Usage

Each supported mnemonic is available as a function that emits the bytes for that instruction. Placeholders such as `n`, `nn`, and `e` become function arguments in the order they appear in the mnemonic.

```python
from msxasmhelper import LD_A_n, JP_nn, JR_e

LD_A_n(0x55)          # b"\x3E\x55"
JP_nn(0x1234)         # b"\xC3\x34\x12"
JR_e(-2)              # b"\x18\xFE"
```

You can also assemble directly from the mnemonic string when you want explicit control over the placeholder names:

```python
from msxasmhelper import assemble

assemble("LD HL,nn", nn=0xC000)
assemble("CALL NZ,nn", nn=0x1234)
```

## Notes

- Immediate 16-bit values are encoded in little endian order.
- Relative offsets (`e`) are validated to fit the signed 8-bit range `[-128, 127]`.
- If a mnemonic has no operands, its callable accepts no arguments and raises a `TypeError` otherwise.
