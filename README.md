# MMSXX_MSX1PaletteQuantizer

Adobe After Effects (AE) / Premiere PRO用の MSX1風エフェクトプラグイン

## 概要

「MSX1PaletteQuantizer」は、コンポジットに MSX1（TMS9918）の見た目を再現するエフェクトプラグインです。
これにより、画像をMSX1特有のルーㇽに基づいた（15色横8ドット内に2色）グラフィックスタイルを模倣します。

## 対応プラットフォーム

- Windows
- Adobe After Effects CC 2018？以降
- Adobe Premiere Pro CC 2018？以降

MacもXcodeでビルドすれば動作すると思います。

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

以降の MSX1PaletteQuantizer の詳細な使用方法や設定については、以下のブログ記事を参照してください。
https://note.com/harayoki/n/nef7d2f9b5380?from=notice

## Visual Studio 2022でのビルド手順 (Windows)

Visual Studio (Windows) または Xcode (Mac) を使用してプロジェクトをビルドします。
ビルドが成功すると、プラグインファイル（.aexまたは.plugin）が生成されます。

* x64 Native Tools Command Prompt for VS2022 にて AESDK_ROOT に After Effects SDK のパスを設定。
  * `setx AESDK_ROOT F:\ae25.6_61.64bit.AfterEffectsSDK\Examples\`
* Command Prompt を再起動
* このリポジトリのルートディレクトリに移動
  * `cd {your_pc_path}\MMSXX_MSX1PaletteQuantizer`
* msbuild コマンドでビルド
  * `msbuild Win\MSX1PaletteQuantizer.sln /p:Configuration=Release /p:Platform=x64`

Win\x64 フォルダに MMSXX_MSX1PaletteQuantizer.aex が生成されます。

## Xcodeでのビルド手順 (Mac)

未検証。リポジトリに含まれる Xcode プロジェクトは内容が間違っている可能性があります。


## ライセンス

MITライセンスの下で公開されています。 [LICENSE](LICENSE)


