# Emscripten セットアップ手順（Windows / Linux / macOS）

MSX1 Palette Quantizer の WebAssembly ビルドに必要な Emscripten 環境を構築する手順です。各 OS で `emcc` が使える状態までをまとめています。

> ヒント: シェルを開き直すたびに環境変数を再読み込みする必要があります。PowerShell なら `emsdk_env.ps1`、Unix シェルなら `emsdk_env.sh` を毎回読み込んでください。

## Windows (PowerShell)

1. 依存ツール: [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio) の「C++ build tools」をインストールし、PowerShell を「x64 Native Tools」環境で起動します。
2. Emscripten SDK を取得:
   ```powershell
   git clone https://github.com/emscripten-core/emsdk.git
   cd emsdk
   .\emsdk.ps1 install latest
   .\emsdk.ps1 activate latest
   .\emsdk_env.ps1
   ```
3. 動作確認:
   ```powershell
   emcc -v
   ```
   バージョン情報が表示されれば準備完了です。

## Linux (bash/zsh など)

1. 依存ツールをインストール（Debian/Ubuntu 例）:
   ```bash
   sudo apt-get update
   sudo apt-get install -y git cmake build-essential python3
   ```
2. Emscripten SDK を取得:
   ```bash
   git clone https://github.com/emscripten-core/emsdk.git
   cd emsdk
   ./emsdk install latest
   ./emsdk activate latest
   source ./emsdk_env.sh
   ```
3. 動作確認:
   ```bash
   emcc -v
   ```

## macOS (zsh)

1. Xcode Command Line Tools をインストール:
   ```bash
   xcode-select --install
   ```
2. 依存ツール（git など）が入っていない場合は Homebrew で導入してください。
3. Emscripten SDK を取得:
   ```bash
   git clone https://github.com/emscripten-core/emsdk.git
   cd emsdk
   ./emsdk install latest
   ./emsdk activate latest
   source ./emsdk_env.sh
   ```
4. 動作確認:
   ```bash
   emcc -v
   ```

## ビルドの実行

環境変数を有効にしたシェルで、リポジトリルートから `src/webasm/README.md` にある `emcc` コマンドを実行します。ビルド成果物は `dist/msx1pq.js` と `dist/msx1pq.wasm` などが生成されます。

