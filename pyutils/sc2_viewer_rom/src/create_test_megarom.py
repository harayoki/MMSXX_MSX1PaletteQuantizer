import sys

if len(sys.argv) < 2:
    print("set out.rom"); sys.exit(1)

out = sys.argv[1]
if "[ASCII16]" not in out:
    out = out.replace(".rom","[ASCII16].rom")
rom = bytearray(0x10000)

boot = [
    0x41,0x42,0x10,0x40,0,0,0,0,0,0,0,0,0,0,0,0,
    0xF3,0x31,0x80,0xF3,

    # バンク切り替え設定
    0x3E,1,  # LD A, 01H         ; Aレジスタにバンク番号「0」をセット
    0x21,0x00,0x70,  # LD   (7000H), A     ; 7000Hへ書き込み -> ページ2がバンク1に切り替わる

    # ページ1自身も明示的にバンク0に設定しておく
    0x3E,0,  # LD A, 00H         ; Aレジスタを0にする
    0x21, 0x00, 0x60,  # LD   (6000H), A     ; 6000Hへ書き込み -> ページ1をバンク0に固定

    # スロット有効化
    # 起動時、BIOSは4000H(ページ1)のみをカートリッジに割り当てます。
    # 8000H(ページ2)を使うには、BIOSコール ENASLT (0024H) を使い、
    # ページ1と同じスロットIDをページ2にも適用する必要があります。
    #
    # CALL 0138H          ; RSLREG: 現在の基本スロット選択状況を読み込む
    # RRCA                ; ページ1 (4000H) の情報を...
    # RRCA                ; ...ビット0-1 (ページ0の位置) へ移動
    # AND  03H            ; 基本スロット番号のみ抽出
    # LD   C, A           ; Cレジスタに保存
    #
    # LD   HL, 0FCC1H     ; ページ1の拡張スロット管理テーブルのアドレス
    # ADD  A, L           ; テーブルのオフセットを計算
    # LD   L, A
    # LD   A, (HL)        ; 拡張スロットフラグを読み込む
    # AND  80H            ; 拡張スロットか判定 (Bit 7)
    # OR   C              ; 基本スロット番号と合成
    # LD   C, A           ; C = ページ2に設定すべき「自分のスロットID」
    #
    # LD   H, 80H         ; H = 80H (ページ2を示すビットフラグ: Bit 7)[5]
    # CALL 0024H          ; ENASLT: スロットCをページH (8000H) に切り替え

    0xCD,0x38,0x01,  # CALL RSLREG
    0x0F,  # RRCA
    0x0F,  # RRCA
    0xE6,0x03,  # AND 3
    0x4F,  # LD C,A
    0x21,0xC1,0x0F,  # LD HL,0FCC1H
    0x09,  # ADD A,L
    0x6F,  # LD L,A
    0x7E,  # LD A,(HL)
    0xE6,0x80,  # AND 80H
    0xB1,  # OR C
    0x4F,  # LD C,A
    0x3E,0x80,  # LD A,80H
    0xCD,0x24,0x00,  # CALL ENASLT

    0x3E,0,0xCD,0x5F,0x00,  # SCREEN0

    0x3A,0,0x80,  # A=(8000h)
    0xFE,1,  # CP 1
    0x20,4,  # NZ jump
    0x3E, ord('1'),
    0x18,2,  # JR
    0x3E, ord('0'),
    0xCD,0xA2,0x00,  # CHPUT

    0x18,  # infinite loop
    0xFE,
]

# 0000h in rom -> 4000h in machine
rom[0x0000:0x0000+len(boot)] = boot
# 4000h in rom -> 8000h in machine
rom[0x4000] = 1
rom[0xc000] = 1

with open(out,"wb") as f:
    f.write(rom)
print(out)
