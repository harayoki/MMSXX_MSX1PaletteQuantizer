English version is available after the Japanese section.

# MMSXX_MSX1PaletteQuantizer（日本語）
このツールは、メディアンカット法による量子化アルゴリズムを使って、画像をMSX1の16色パレットに変換します。

## バッチランナー（run_batch_pipeline.bat）
ファイルまたはフォルダーを `run_batch_pipeline.bat` にドラッグ＆ドロップすると、入力ファイル（フォルダ）に対して異なるパラメーターで 10回の msxエフェクトを適用します。5番目の呼び出しでは、隣にある LUT ファイル（`ContrastAndSaturationBoos.cube`）を読み込みます。出力は入力の隣にある `out` フォルダーに生成され、番号付きプレフィックスで結果が分けられます。
バッチ内の各行は直接コマンドを実行する際の参考としても利用できます。

## AEのプラグインについて
After Effects プラグイン版も同梱されており、同じアルゴリズムでエフェクトを適用できます。

## CLIについて
`msx1pq_cli.exe` を使って、単一ファイルに対してコマンドラインから直接処理を実行できます。

# ドキュメント
詳しくは以下のURLを確認してください。
https://github.com/Matrix-Software/MMSXX_MSX1PaletteQuantizer

---

# MMSXX_MSX1PaletteQuantizer
This tool converts images to use the MSX1 16-color palette using a median cut quantization algorithm.

## Batch runner (run_batch_pipeline.bat)
Drag and drop a file or folder onto `run_batch_pipeline.bat` to invoke ten runs of `msx1pq_cli.exe` with varied parameters. The fifth call demonstrates reading the adjacent LUT file (`ContrastAndSaturationBoos.cube`). Outputs are written next to the input inside an `out` folder, using numbered prefixes to keep results separated.
Each line in the batch file can be reused as a reference when you want to run the commands directly.

## About the AE plugin
An After Effects plugin is included so you can apply the same algorithm as an effect within AE.

## About the CLI
You can process a single file directly from the command line with `msx1pq_cli.exe`.

# Documentation
For more details, see the repository below.
https://github.com/Matrix-Software/MMSXX_MSX1PaletteQuantizer
