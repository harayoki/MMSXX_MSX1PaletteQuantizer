English version is available after the Japanese section.

# MMSXX_MSX1PaletteQuantizer
このツールは、独自の量子化アルゴリズムを使って、画像・動画をMSX1(TMS9918)ルールの15色パレットに変換します。

## AfterEffects / Premiere PRO プラグイン
AE/ Premiere 両対応の aexプラグインを同梱しています。 `MSX1PaletteQuantizer.aex`
インストールの仕方・使い方は
https://github.com/harayoki/MMSXX_MSX1PaletteQuantizer/blob/main/docs/AE_guide_ja.md
を確認して下さい。

## CLIについて

画像変換を行うコマンドラインツールを同梱しています。 `msx1pq_cli.exe`
対応画像フォーマットはpngのみです。詳しいインストールの仕方・使い方は
https://github.com/harayoki/MMSXX_MSX1PaletteQuantizer/blob/main/docs/CLI_guide_ja.md
を確認して下さい。

## CLIバッチランナー

ファイルまたはフォルダーを `run_batch_pipeline.bat` にドラッグ＆ドロップすると、入力ファイル（フォルダ）に対して
様々なパラメータ設定で 10回の 画像変換を適用します。
10番目の呼び出しでは、同梱した LUT ファイル（`ContrastAndSaturationBoos.cube`）だけを読み込みます。
出力は入力の隣の `out` フォルダーに生成され、番号付きプレフィックスで結果が分けられます。

バッチファイル内の各行は直接コマンドを実行する際の参考としても利用できます。


# ドキュメント
詳しくは以下のURLを確認してください。
https://github.com/harayoki/MMSXX_MSX1PaletteQuantizer

---

# MMSXX_MSX1PaletteQuantizer
This tool converts images and videos into a 15-color MSX1 (TMS9918) palette using a custom quantization algorithm.

## After Effects / Premiere Pro plugin
The package includes an `aex` plugin that works in both AE and Premiere: `MSX1PaletteQuantizer.aex`.
See the installation and usage guide at
https://github.com/harayoki/MMSXX_MSX1PaletteQuantizer/blob/main/docs/AE_guide_en.md

## About the CLI
A command-line tool for image conversion is included: `msx1pq_cli.exe`.
Supported image format is PNG only. See the installation and usage guide at
https://github.com/harayoki/MMSXX_MSX1PaletteQuantizer/blob/main/docs/CLI_guide_en.md

## CLI batch runner
Drag and drop a file or folder onto `run_batch_pipeline.bat` to apply 10 image conversions with different parameters to the
input file (or folder) with many parameter sets. The 10th invocation applies only the bundled LUT file
(`ContrastAndSaturationBoos.cube`). The output is written
to an `out` folder next to the input, with numbered prefixes to distinguish each result.

Each line in the batch file can also serve as a reference if you want to run the commands directly.


# Documentation
For more details, see the repository below.
https://github.com/harayoki/MMSXX_MSX1PaletteQuantizer
