# VDPパレットレジスタ操作メ

※ 以下はAIに色々な情報を元にまとめてもらったものだが、正確性が不明なので正確な情報として扱わない事。Screen4のパレットアドレスと内容が正しい事は確認済み。

MSX2/2+/turboR の VDP (V9938/V9958) は 16 色分のパレットレジスタを持ち、
各色は 3bit ずつの R/G/B で構成されます。1 色あたり 2 バイトのデータを
パレットポート (I/O ポート `&H9A`) に書き込みます。

- 1 バイト目: 下位 3bit に Blue、上位 3bit に Red (`0R2R1R0B2B1B0`).
- 2 バイト目: 下位 3bit に Green (`0000G2G1G0`).
- それぞれのバイトの bit3 と bit7 は常に 0 です。
- 値の範囲は各チャンネル 0–7 (0: 最低輝度、7: 最高輝度) です。

パレットレジスタ番号の設定は VDP レジスタ #16 を使います。ビット構成は
以下の通りです。

| ビット | 意味                             |
| ------ | -------------------------------- |
| 0–4    | 書き込み先パレット番号 (0–15)    |
| 5      | 未使用 (0 固定)                  |
| 6      | 1=書き込み後に番号を自動インクリメント |
| 7      | 未使用 (0 固定)                  |

書き込み手順の概要:

1. `OUT (&H99), A` で VDP レジスタに設定したい値を出力。
2. 続けて `OUT (&H99), &H80 + レジスタ番号` で設定するレジスタを指定。
3. パレットを書き込む場合はレジスタ #16 を設定し、パレットデータを
   `OUT (&H9A),` で 2 バイトずつ送る。

## SCREEN4 VRAM の BLOAD データからパレットを適用する

SCREEN4 の VRAM を `BLOAD "FILE.SCR",S` で読み込むと、
パレットデータは VRAM アドレス `&H1B80` (32 バイト) に格納されています。
ここから直接パレットレジスタへ転送する手順を BASIC とマシン語で示します。

### BASIC で簡易に適用する

```basic
' パレットレジスタの開始を設定 (パレット0、オートインクリメント有効)
OUT &H99,&H40 : OUT &H99,&H90  ' &H90 = &H80 + 16

' VRAM &H1B80 から 32 バイトを順次読み、パレットへ書き込む
FOR I=0 TO 31
  OUT &H9A,VPEEK(&H1B80+I)
NEXT I
```

- `VPEEK` は VRAM を直接参照するので、BLOAD 直後に即座にパレットを書き換えられます。
- オートインクリメントを使っているため、色番号を意識せず 32 バイトを
  そのままストリームで出力するだけで完了します。

### マシン語で高速に適用する(間違い？)

```asm
; IN  : なし (BLOAD 済みで VRAM &H1B80 に 32 バイトのパレットデータがある)
; DEST: パレットレジスタ 0-15 を上書き

    ld   a,&H80               ; VDP 読み取り先を VRAM &H1B80 に設定
    out  (&H99),a
    ld   a,&H5B + &H40        ; 上位アドレス (&H1B00 >> 8) に読み取りビット(6)を立てる
    out  (&H99),a             ; これで以降の IN (&H98) で連続読み出し可能

    ld   a,&H40               ; パレット番号=0, オートインクリメント=1 を R#16 に設定
    out  (&H99),a
    ld   a,&H90               ; &H80 + 16 で R#16 指定
    out  (&H99),a

    ld   b,32                 ; 16 色 x 2 バイト
CopyLoop:
    in   a,(&H98)             ; VRAM から 1 バイト取得
    out  (&H9A),a             ; パレットデータポートへ書き込み
    djnz CopyLoop
    ret
```

- VRAM 読み出しアドレスはポート `&H99` へ下位→上位(+&H40)の順で設定します。
- パレットデータポート `&H9A` へ 32 バイトを流し込むだけで全色が更新されます。
- ループは Z80 の `DJNZ` を用いて最短で回しているので、BASIC 版より高速です。

参照 Example https://www.msx.org/wiki/VDP_Color_Palette_Registers

```
; Routine to set color palette to MSX1 like
 
VDP_DW	equ	00007h
RG16SAV	equ	0FFEFh
 
MSX1palette:
	ld	a,(VDP_DW)	; A= CPU writing port connected to the VDP writing port #0
	inc	a
	ld	c,a		; C= CPU writing port connected to the VDP writing port #1
 
	xor	a		; Set color 0 ...
	di
	out	(c),a
	ld	(RG16SAV),a
	ld	a,80h+16	; ...into register 16 (+80h)
	out	(c),a
	ei
 
	inc	c		; C= CPU port connected to the VDP writing port #2
	ld	b,31
	ld	hl,MSX1paletteData
	otir
	ret
 
MSX1paletteData:
	db	00h,0	; Color 0
	db	00h,0	; Color 1
	db	11h,5	; Color 2
	db	33h,6	; Color 3
	db	26h,2	; Color 4
	db	37h,3	; Color 5
	db	52h,2	; Color 6
	db	27h,6	; Color 7
	db	62h,2	; Color 8
	db	63h,3	; Color 9
	db	52h,5	; Color A
	db	63h,6	; Color B
	db	11h,4	; Color C
	db	55h,2	; Color D
	db	55h,5	; Color E
	db	77h,7	; Color F
```



## 応用メモ

- 任意のパレット番号から書き換えたい場合は、R#16 の下位 5bit を変更し、
  オートインクリメントビット (bit6) を 1 にしておけば連続書き込みできます。
- `BLOAD` 以外のデータソース (RAM 上の配列など) でも同じ手順で
  ポート `&H9A` へ 32 バイトを送れば即座にパレットが反映されます。

