# MSX Disk Utilities / MSXディスクユーティリティ

English | This package builds 2DD (720 KiB) FAT12 disk images for MSX. It
generates a blank image at runtime and can pack files or folders into the
image.

* Uses an embedded minimal FAT12 helper inspired by pyfatfs to stay compatible
  with MSX-style media.
* Supports optional extension filters (e.g., `--ignore-ext .tmp .bak`).
* Accepts files or directories; directories are recursively expanded.
* Requires an output filename even when no inputs are given (blank image use).
* When space runs out, fails by default or truncates with warnings when
  `--allow-partial` is set.

日本語 | このパッケージは MSX 用の 2DD(720KiB) FAT12 ディスクイメージを作成します。
ブランクイメージは実行時に生成し、指定したファイルやフォルダーをまとめて格納できま
す。

* pyfatfs 互換の最小 FAT12 ヘルパーを同梱し、MSX 形式で動作します。
* `--ignore-ext .tmp .bak` のように無視する拡張子を指定可能。
* ファイルとフォルダーを受け付け、フォルダーは再帰的に展開します。
* 入力が無くても出力ファイル名は必須で、空のディスクを生成できます。
* 容量不足時はデフォルトでエラー、`--allow-partial` を付ければ入るところまで格納し
  警告を出します。

## CLI

```
python -m msxdisk.cli output.dsk data/extra.bin assets/ --ignore-ext .bak --allow-partial
```
