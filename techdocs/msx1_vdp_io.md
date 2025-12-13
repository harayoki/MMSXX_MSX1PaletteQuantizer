# MSX1 VDP 読み書き操作

MSX1 の VDP（TMS9918A 系）は Z80 から I/O ポート経由で操作する。  
VRAM 読み書き、レジスタ設定、ステータス取得の最低限だけまとめる。

---

## ポート一覧

| ポート | 方向 | 内容 |
|-------|------|------|
| **#98h** | R/W | VRAM データ読み書き |
| **#99h** | W | VRAM アドレス設定、VDP レジスタ設定 |
| **#99h** | R | ステータスレジスタ S#0 |

---

## 2 バイト制御書き込みの構造（ポート #99h）

VRAM へのアクセス指定は必ず **2 バイト連続**。

```
1バイト目: A0〜A7 (下位)
2バイト目: C1 C0 A13 A12 A11 A10 A9 A8
```

- アドレスは 14bit (A0〜A13)
- C1C0 がコマンド

| C1C0 | 意味 |
|------|------|
| 00b | VRAM 読み込みアドレス設定 |
| 01b | VRAM 書き込みアドレス設定 |
| 10b | VDP レジスタ設定 |
| 11b | 未使用 |

---

## VRAM 書き込み（連続書き込みはアドレス自動インクリメント）

```asm
VDP_VRAM_WRITE:
    ld a,l
    out (#99),a
    ld a,h
    or 01000000b
    out (#99),a
WRITE_LOOP:
    ld a,(de)
    out (#98),a
    inc de
    dec bc
    ld a,b
    or c
    jr nz,WRITE_LOOP
    ret
```

---

## VRAM 読み込み（プリフェッチ 1 バイト捨て）

```asm
VDP_VRAM_READ:
    ld a,l
    out (#99),a
    ld a,h
    and 00111111b
    out (#99),a
    in a,(#98)
READ_LOOP:
    in a,(#98)
    ld (de),a
    inc de
    dec bc
    ld a,b
    or c
    jr nz,READ_LOOP
    ret
```

---

## VDP レジスタ書き込み（R0〜R7）

```asm
VDP_REG_WRITE:
    ld a,c
    out (#99),a
    ld a,b
    or 10000000b
    out (#99),a
    ret
```

---

## ステータスレジスタ読み出し（MSX1 は S#0 だけ）

```asm
VDP_STATUS_READ:
    in a,(#99)
    ret
```

---

