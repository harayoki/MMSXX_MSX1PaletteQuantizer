# スクロールビューアー描画メモ

## 現状の画面描画処理
`create_scroll_megarom.py` では縦長画像を 256px 幅にトリミング／パディングし、`build_row_packages_from_image` で
8x8ピクセルパターンの 32文字 1行 64 バイト（パターン 32 + 色 32）の RowPackage に変換して、高さぶんをそのまま積み上げています。
行数として画像の実ピクセル高さをそのまま返しているため、スクロール単位は8ピクセル行です。

起動時に SCREEN 2 を設定し、ネームテーブルには 0〜255 のパターン番号を
3回繰り返して全 768 エントリを事前配置しています （`INIT_NAME_TABLE_CALL`）。
描画ループ（`DRAW_CURRENT_IMAGE`）ではスクロールオフセットの下位 8 ビットを RowPackage の行インデックスとして使い、その行から 64 バイトを VRAM に直送します。
上位 8 ビットは ASCII16 のページレジスタに足し込まれ、データバンクを切り替えています。
1 行描画ごとにパターンジェネレータのベースアドレス（0x0000）から 32 バイト、続けてカラーテーブルのベース（0x2000）から 32 バイトを書き込み、ポインタを進めて 24 行ぶん繰り返しています。ネームテーブルは初期化後に触っていないため、表示内容はパターン／カラーの物理配置だけで決まります。
入力処理はスペースで次画像、カーソル上下でオフセットを ±1 行ずつ変更し、`ROW_COUNT - VISIBLE_ROWS` を上限にしています。オフセットは 16bit で保持され、行数情報はテーブルから読み出しています。

## 画面が乱れて見える主な要因
SCREEN 2 のパターン／カラーテーブルは 1 パターン 8 行で構成され、ネームテーブルの同じ番号を 8 行分で共有する前提ですが、現行コードは 1 ピクセル行＝64 バイトを連続で埋めているだけで 8 行単位のレイアウトを考慮していません。結果として同じパターン番号でも 1 行ごとに別のアドレスに書き足され、縦方向でデータが噛み合わず、モードの想定と異なる並びで描画されるため画面が破綻します。
`VISIBLE_ROWS` が 24 固定のまま RowPackage を 1 ピクセル行とみなしているため、192 行（=SCREEN 2 表示領域）を書かずに 24 行で止まり、以降のパターン／カラーは初期化値や未定義領域に依存します。この高さ不足も表示ノイズの一因になります。【F:pyutils/sc2_viewer_rom/src/create_scroll_megarom.py†L247-L284】【F:pyutils/sc2_viewer_rom/src/create_scroll_megarom.py†L375-L406】
スクロール下方向では `ROW_COUNT - VISIBLE_ROWS` を上限にしていますが、RowPackage を 1 ピクセル行と見なす設計では `VISIBLE_ROWS` を 192 に揃えないと全画面を書けず、上限計算と VRAM 更新範囲が一致しません。行単位とパターン単位のズレが積み重なって VRAM のどこが有効なのか読みづらい状態です。【F:pyutils/sc2_viewer_rom/src/create_scroll_megarom.py†L446-L485】

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


python pyutils/sc2_viewer_rom/src/create_scroll_megarom.py -i pyutils/sc2_viewer_rom/test_png/palette1.png --workdir work/ -o pyutils/sc2_viewer_rom/dist/a.rom --msx1pq-cli platform/Win/x64/msx1pq_cli.exe


