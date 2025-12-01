# MSX Disk / MSXディスクユーティリティ

This package creates 2DD (720KiB) FAT12 disk images for MSX.
The disk image can store specified files and folders together.

* Includes a minimal FAT12 helper to generate disk images that work in MSX format.
* Files and folders to be stored can be specified as arguments. Folders are expanded recursively.
* If there is insufficient space, an error is raised by default. Adding `--allow-partial` will store as much as possible and issue a warning.

---
 
このパッケージは MSX 用の 2DD(720KiB) FAT12 ディスクイメージを作成します。
ディスクイメージには指定したファイルやフォルダーをまとめて格納できます。

* 最小 FAT12 ヘルパーを同梱し、MSX 形式で動作するディスクイメージを生成します。
* 格納するファイルとフォルダーを引数指定できます。フォルダーは再帰的に展開します。
* 容量不足時はデフォルトでエラー、`--allow-partial` を付ければ入るところまで格納し警告を出します。

## CLI (WIP)

command example:

```
python -m msxdisk.cli output.dsk data/extra.bin assets/ --ignore-ext .bak --allow-partial
```
