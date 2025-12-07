# Basic Sc2 Viewer

The image (sc2 file) provided as an argument is stored in a disk image and can be displayed using an auto-start BASIC program.
The disk image can be opened with an emulator. To write it to a 2DD disk, additional tools are required.

Note: SCREEN5 output is planned for deprecation. Future builds are expected to support SCREEN4 instead.

---
 
引数で与えられた画像（sc2ファイル）をdiskイメージに格納し、自動起動するBASICプログラムで画像を表示できるようにします。
diskイメージはエミュレータで開くことができます。実際に2DDディスクに書き込むには、別途ツールが必要です。

注記: 現在はSCREEN5出力にも対応していますが、これは廃止予定です。今後は SCREEN4 対応の追加を予定しています。


usage:

```
python basic_sc2_viewer.py -i image_folder_path -o image.dsk
```

## Build an EXE with Nuitka

You can bundle the script into a standalone executable (useful for Windows) with Nuitka.

1. Install the Python dependencies from the repository root (Python 3.11+).

   ```
   pip install -r requirements.txt
   ```

2. Run the helper script to invoke Nuitka.

   ```
   python pyutils/basic_sc2_viewer/make_exe.py
   ```

   The resulting executable is written to `pyutils/basic_sc2_viewer/dist/basic_sc2_viewer.exe` by default. Use `--output-dir` to change the destination.
