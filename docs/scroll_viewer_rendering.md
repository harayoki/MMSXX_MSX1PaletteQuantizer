# スクロールビューアー描画メモ

## 現状の画面描画処理
- `create_scroll_megarom.py` では縦長画像を 256px 幅にトリミング／パディングし、`build_row_packages_from_image` で 1 ライン 64 バイト（パターン 32 + 色 32）の RowPackage に変換して、高さぶんをそのまま積み上げています。行数として画像の実ピクセル高さをそのまま返しているため、スクロール単位も 1 ピクセル行です。【F:pyutils/sc2_viewer_rom/src/create_scroll_megarom.py†L247-L284】
- 起動時に SCREEN 2 を設定し、ネームテーブルには 0〜255 のパターン番号を 3 回繰り返して全 768 エントリを事前配置しています（`INIT_NAME_TABLE_CALL`）。【F:pyutils/sc2_viewer_rom/src/create_scroll_megarom.py†L286-L317】
- 描画ループ（`DRAW_CURRENT_IMAGE`）ではスクロールオフセットの下位 8 ビットを RowPackage の行インデックスとして使い、その行から 64 バイトを VRAM に直送します。上位 8 ビットは ASCII16 のページレジスタに足し込まれ、データバンクを切り替えています。【F:pyutils/sc2_viewer_rom/src/create_scroll_megarom.py†L358-L406】
- 1 行描画ごとにパターンジェネレータのベースアドレス（0x0000）から 32 バイト、続けてカラーテーブルのベース（0x2000）から 32 バイトを書き込み、ポインタを進めて 24 行ぶん繰り返しています。ネームテーブルは初期化後に触っていないため、表示内容はパターン／カラーの物理配置だけで決まります。【F:pyutils/sc2_viewer_rom/src/create_scroll_megarom.py†L368-L406】
- 入力処理はスペースで次画像、カーソル上下でオフセットを ±1 行ずつ変更し、`ROW_COUNT - VISIBLE_ROWS` を上限にしています。オフセットは 16bit で保持され、行数情報はテーブルから読み出しています。【F:pyutils/sc2_viewer_rom/src/create_scroll_megarom.py†L410-L485】

## 画面が乱れて見える主な要因
- SCREEN 2 のパターン／カラーテーブルは 1 パターン 8 行で構成され、ネームテーブルの同じ番号を 8 行分で共有する前提ですが、現行コードは 1 ピクセル行＝64 バイトを連続で埋めているだけで 8 行単位のレイアウトを考慮していません。結果として同じパターン番号でも 1 行ごとに別のアドレスに書き足され、縦方向でデータが噛み合わず、モードの想定と異なる並びで描画されるため画面が破綻します。【F:pyutils/sc2_viewer_rom/src/create_scroll_megarom.py†L368-L406】
- `VISIBLE_ROWS` が 24 固定のまま RowPackage を 1 ピクセル行とみなしているため、192 行（=SCREEN 2 表示領域）を書かずに 24 行で止まり、以降のパターン／カラーは初期化値や未定義領域に依存します。この高さ不足も表示ノイズの一因になります。【F:pyutils/sc2_viewer_rom/src/create_scroll_megarom.py†L247-L284】【F:pyutils/sc2_viewer_rom/src/create_scroll_megarom.py†L375-L406】
- スクロール下方向では `ROW_COUNT - VISIBLE_ROWS` を上限にしていますが、RowPackage を 1 ピクセル行と見なす設計では `VISIBLE_ROWS` を 192 に揃えないと全画面を書けず、上限計算と VRAM 更新範囲が一致しません。行単位とパターン単位のズレが積み重なって VRAM のどこが有効なのか読みづらい状態です。【F:pyutils/sc2_viewer_rom/src/create_scroll_megarom.py†L446-L485】

## 8 行単位のレイアウトを考慮した実装方針
- SCREEN 2 では「パターン番号 × 8 行」が 1 キャラクタに相当し、ネームテーブルの 1 マス（8x8）を構成する 8 行分のパターンデータは **同じパターン番号の +0〜+7 バイト** に積み上がります。そのため、RowPackage も 1 ピクセル行ではなく **8 行まとめ（32 文字幅）** のブロックに再編しておき、1 ブロック = パターン 256 バイト + カラー 256 バイト（計 512 バイト）で tile_y ごとに切り出して格納するのが安全です。
- 変換側（`build_row_packages_from_image` 相当）で、画像の先頭から 8 行ごとに 32 文字ぶんのパターン／カラーを束ねて RowPackage を作り、`row_count` も「タイル行数 = 画像高さ / 8」に変更します。こうすると描画時は「tile_y を何ブロック目か」で単純にアドレス計算できます。
- 描画ループでは `VISIBLE_ROWS` を 24 キャラクタ行＝192 ドットに揃えつつ、`tile_y` を `SCROLL_OFFSET / 8`、`line_in_tile` を `SCROLL_OFFSET % 8` として、ページレジスタ（`ASCII16_PAGE2_REG`）を `tile_y` の上位 8 ビットで切り替え、ベースアドレスを `PATTERN_BASE + (tile_y_low * 256 + tile_x) * 8 + line_in_tile` で決定します。カラーも同式で `COLOR_BASE` を使います。

### 8 行整列させた書き込みの擬似コード（概念）
```asm
; row = SCROLL_OFFSET + visible_y
    LD      HL,(SCROLL_OFFSET_ADDR)
    ADD     HL,visible_y         ; HL = row
    LD      A,L
    AND     7
    LD      line_in_tile,A       ; 0..7
    SRL     H
    RR      L
    SRL     H
    RR      L
    SRL     H
    RR      L                    ; HL = tile_y = row / 8

; bank 切り替え（tile_y 上位 8 ビットぶん）
    LD      A,H
    ADD     A,D                  ; D=DATA_BANK_BASE/ASCII16 page基底
    LD      (ASCII16_PAGE2_REG),A

; tile_y 下位 8 ビットをオフセットとして、パターンの書き込み先を計算
    LD      A,L
    LD      dest_base_hi,A       ; (tile_y_low * 256) * 8 = tile_y_low << 3
    ; 以降 dest = PATTERN_BASE + (tile_y_low<<3)*32 + tile_x*8 + line_in_tile
```
（実際には `tile_y_low<<3` と `tile_x<<3` を加算し、最後に `line_in_tile` を足す。カラーも同じ式で `COLOR_BASE` に切り替える。）

## 1 枚目をスクロール位置 0 で固定表示するコード例
1 枚目だけスクロールを許可しない場合は、描画前に画像番号を 0 に固定し、オフセットをゼロクリアしたうえでキー入力のスクロール処理をスキップするガードを入れるだけで足ります。以下は `build_boot_bank` 内に追記するイメージの擬似コードです。

```asm
; 起動直後に 1 枚目の先頭行を強制表示
    XOR     A
    LD      (CURRENT_IMAGE_ADDR),A
    LD      HL,0
    LD      (SCROLL_OFFSET_ADDR),HL
    CALL    DRAW_CURRENT_IMAGE

; スクロールキーを押しても 1 枚目では何もしない
HANDLE_SCROLL_UP:
    LD      A,(CURRENT_IMAGE_ADDR)
    OR      A
    JR      Z,MAIN_LOOP      ; 1枚目は無視
    ; 以降は既存のスクロールアップ処理

HANDLE_SCROLL_DOWN:
    LD      A,(CURRENT_IMAGE_ADDR)
    OR      A
    JR      Z,MAIN_LOOP      ; 1枚目は無視
    ; 以降は既存のスクロールダウン処理
```

この形なら 1 枚目は常にオフセット 0 のまま描かれ、スペースキーで 2 枚目以降に進んだときだけスクロールが効く挙動にできます。
