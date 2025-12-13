# MMSXX_MSX1PaletteQuantizer (After Effects / Premiere PRO 向けプラグイン / CLI)

Adobe After Effects (AE) / Premiere PRO 用の MSX1 風エフェクトプラグイン / コマンドラインツール。

English documentation: [README_en](README.md)

| source movie | result |
|---------|--------|
|![source_movie_capture](docs%2Fsource_movie_capture.png)|![result_capture](docs%2Fresult_capture.png)|

## 動画サンプル


* [Wing It in 8-bit MSX (TMS9918) Colors](https://www.youtube.com/watch?v=HZ43BCsNMus) - YouTube - (C) Blender Foundation | studio.blender.org

|                                                |                                                |
|------------------------------------------------|------------------------------------------------|
| ![capture_00008.png](docs%2Fcapture_00010.png) | ![capture_00009.png](docs%2Fcapture_00011.png) |

* [MSXガールin吉祥寺 ドット絵動画](https://www.youtube.com/watch?v=-X0sMmEDrdY) - YouTube
* [元動画とエフェクト適用後の比較動画](https://www.youtube.com/shorts/yKph3DFmB7M) - YouTube Shorts

## 概要

「MSX1PaletteQuantizer」は、コンポジットに MSX1（TMS9918）の見た目を再現するエフェクトプラグインです。
MSX1特有のルール（15色、横8ドット内に2色）に基づいたグラフィックスタイルを模倣し、MSX2向けの15色パレットも切り替えできます。
After Effects のスマートレンダリングとマルチフレームレンダリングに対応しており、書き出しを高速化できます。CLI 版ではパレット無効化や LUT 適用、SCREEN2 バイナリ出力などもサポートしています。

## 対応プラットフォーム

- Windows
- Adobe After Effects CC 2018 以降
- Adobe Premiere Pro CC 2018 以降

Mac でも Xcode でビルドすれば動作する想定です。

## 免責事項

このプラグインを使用することにより生じたいかなる損害についても、作者は一切の責任を負いません。自己の責任において使用してください。

## インストール

1.  プラグインファイル（.aexまたは.plugin）を取得します。
2.  After Effects / Premiere PRO の共通プラグインフォルダにプラグインファイルをコピーします。
    - Windows: `C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore\`

## 使用方法

1.  After Effectsを起動します。
2.  フッテージをコンポジションに追加します。
3.  エフェクトメニューから「MMSXX」>「MSX1PaletteQuantizer」を選択し、フッテージに適用します。
4.  エフェクトコントロールパネルで設定を調整します。

プレミアも同様の手順で使用できます。

以降の MSX1PaletteQuantizer の詳細な使用方法や設定については、
* [After Effectsでの使い方](docs/AE_guide_ja.md)
* https://note.com/harayoki/n/nef7d2f9b5380 note記事

コマンドライン版の使い方については、
* [CLI の使い方](docs/CLI_guide_ja.md)

## Visual Studio 2022でのビルド手順 (Windows)

Visual Studio (Windows) を使用してプロジェクトをビルドします。

* x64 Native Tools Command Prompt for VS2022 にて AESDK_ROOT に After Effects SDK のパスを設定。
  * `setx AESDK_ROOT F:\ae25.6_61.64bit.AfterEffectsSDK\Examples\`
* Command Prompt を再起動
* このリポジトリのルートディレクトリに移動
  * `cd {your_pc_path}\MMSXX_MSX1PaletteQuantizer`
* msbuild コマンドでビルド
  * `msbuild platform\Win\MSX1PaletteQuantizer.vcxproj /p:Configuration=Release /p:Platform=x64`

platform\Win\x64 フォルダに MMSXX_MSX1PaletteQuantizer.aex が生成されます。

## Xcodeでのビルド手順 (Mac)

*   After Effects SDK をインストールしたパスを `AESDK_ROOT` 環境変数に設定します（例：`/Applications/Adobe After Effects 2023/Support Files/After Effects SDK`）。
*   `platform/Mac/MSX1PaletteQuantizer.xcodeproj` を Xcode で開きます。
*   `MSX1PaletteQuantizer` ターゲットをビルドして `MSX1PaletteQuantizer.plugin` を生成します。

## LinuxでのCLIビルド手順（コンテナ向け、検証は限定的）

Adobe SDK が不要な環境（例: コンテナ化した Linux 環境）で `msx1pq_cli` のみをビルドする手順です。ディストリビューション全体では未検証です。

1. ビルド用ツールチェーンをインストール（Ubuntu 例）:
   ```bash
   sudo apt-get update && sudo apt-get install -y build-essential
   ```
2. `make` で CLI バイナリをビルド:
   ```bash
   make -C platform/Linux
   ```
3. 実行ファイルは `bin/msx1pq_cli` に生成されます。

## Windows版 msx1pq_cli の自動テストの実行方法

CLI の挙動確認用テストは Windows 環境で、既にビルド済みの `platform/Win/x64/msx1pq_cli.exe` が存在する前提で動作します。

1. このリポジトリのルートで `platform/Win/x64/msx1pq_cli.exe` があることを確認します。
2. コマンドプロンプトまたは PowerShell でリポジトリのルートに移動します。
3. `python -m unittest tests/test_msx1pq_cli.py` を実行します。

テスト結果は標準出力に unittest の結果として表示されます。`tests` フォルダに入力用 PNG がある場合はそれを利用し、存在しない場合は 256x192 のカラフルな PNG を自動生成します。出力画像や SC2 ファイルは `tests/msx1pq_outputs` 以下に、使用したパラメータが分かるプレフィックス/サフィックス付きのファイル名で保存され、次回のテスト開始時にまとめて削除されます。

## 実装について

プラグインは8ビットエフェクトでGPUレンダリングには対応していません。After Effects のマルチフレームレンダリングに対応しています。
また無料・安価な動画編集ソフトへの移植（OpenFX形式など）など歓迎します。

## ライセンス

* MITライセンスの下で公開されています。
  * [LICENSE](LICENSE)

* CLI版にはPNGエンコーダ/デコーダライブラリ「lodepng」を使用しています。
  * https://github.com/lvandeve/lodepng/
  * [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt)



