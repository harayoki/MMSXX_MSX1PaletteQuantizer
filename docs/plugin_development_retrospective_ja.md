# After Effects / Premiere Pro エフェクトプラグイン開発の振り返りと環境構築

## 1. この文書の目的と前提

この文書は、`MMSXX_MSX1PaletteQuantizer` のソースコードと Git 履歴から、Adobe After Effects（以下 AE）と Premiere Pro（以下 Premiere）の両方で動くエフェクトプラグインを作る際に難しかった点を整理し、次のプラグインをゼロから開発するときの手引きにするものである。

- 主対象は **Windows で開発し、Windows x64 向け `.aex` を作る場合**。
- macOS については、このリポジトリに Xcode プロジェクトはあるものの、README も「動作すると思う」という記述にとどまる。したがって後半の macOS 手順は出発点であり、実機・対象ホスト・対象 CPU での検証が必要である。
- Linux については、コアロジックの開発環境と、Adobe ホストで実際にロードできるバイナリのビルド・検証環境を分けて考える。
- SDK の仕様は更新されるため、実装時には必ず [After Effects C++ SDK Guide](https://ae-plugins.docsforadobe.dev/) と、使用する SDK に同梱されたサンプル・ヘッダーを正とする。本書ではこのリポジトリの状態を無条件に最新 SDK の正解とはみなさない。

また、新規プロジェクトでは実装前に `spec.md` を用意し、対応ホスト、対応 OS / CPU、対応ピクセル形式、色深度、ROI、スレッド安全性、パラメーター互換性、性能目標、非対応事項を明文化することを強く勧める。本リポジトリには現時点で `spec.md` がなく、後から Smart Render、ROI、Multi-Frame Rendering（MFR）対応を加えた履歴では、設計判断が多数の修正コミットに分散した。仕様書はその再発を防ぐための判断基準になる。

## 2. 現在の構成から読み取れる設計

| 層 | 主なファイル | 責務 |
|---|---|---|
| Adobe ホストアダプター | `src/ae/MSX1PaletteQuantizer.cpp/.h` | エントリポイント、パラメーター、AE/Premiere 分岐、pixel world、Smart Render、iterate suite |
| PiPL | `src/ae/MSX1PaletteQuantizerPiPL.r` | ホストがロード前に読むプラグイン情報、エントリポイント、バージョン、out flags |
| ホスト非依存コア | `src/core/MSX1PQCore.*`, `MSX1PQPalettes.*` | 前処理、量子化、パレット、8-dot/2-color 処理 |
| Windows ビルド | `platform/Win/MSX1PaletteQuantizer.vcxproj` | Visual C++ DLL（拡張子 `.aex`）、PiPL 生成、SDK include、x64/ARM64 構成 |
| macOS ビルド | `platform/Mac/MSX1PaletteQuantizer.xcodeproj` | `.plugin` bundle、PiPL resource、SDK source/header、Info.plist |
| 配置補助 | `tools/copy_aex_to_mediacore.bat` | Windows 共通 MediaCore フォルダーへのコピー |

良かった設計判断は、Adobe SDK 型に依存しない画像処理を `src/core` に分けたことである。これにより CLI から同じ処理を使え、アルゴリズムの再現確認をホスト起動なしで行える。一方、ARGB/BGRA のメモリー表現、`rowbytes`、ROI、パラメーター checkout/checkin など、ホスト固有の責務はアダプターに残している。この境界は次のプロジェクトでも最初から作るべきである。

## 3. 履歴から見える苦労した点

### 3.1 Smart Render と ROI は「矩形を小さくすれば速い」だけではない

2025-11-29〜30 の履歴には、Smart Render 対応開始後に、クラッシュ回避、ROI の有効判定、`max_result_rect`、全幅化の撤回、`extent_hint`、8 ピクセル境界、クランプ、前段エフェクトによる位置ずれなどの修正が集中している。最終コードにも「入力 ROI を広げると前に挟むエフェクトによって位置がずれる」「出力 rect を変更するとクリッピングされる」と判断した痕跡が残る。

このエフェクトには、座標依存ディザと横 8 ドット単位の後処理がある。そのため、要求された ROI だけを独立に計算すると、タイル境界が変わったときに結果も変わり得る。現在のコードはグローバル座標を `FilterRefcon` に保持し、必要な場合は横方向を 8 境界へ揃える。ここから得られる教訓は次の通り。

1. **アルゴリズムの依存範囲を先に定義する。** 1 ピクセル独立、近傍 N ピクセル、行全体、フレーム全体のどれかで ROI 契約が変わる。
2. ローカルバッファ座標とコンポジション上の絶対座標を混同しない。ディザや周期模様は絶対座標を明示的に渡す。
3. `result_rect`、`max_result_rect`、`extent_hint`、実際の `width/height/data` は同じものとは限らない。
4. 8 ドット後処理のようにブロック内の他画素へ依存する場合、要求矩形をブロック境界まで広げるか、必要領域を checkout して最終要求部分だけ返す設計を、最初からテスト可能な関数にする。
5. 空矩形、負の座標、コンポジション外、負の `rowbytes`、部分フレーム、前後に変形系エフェクトがある場合をテストする。

SmartFX の契約は [SmartFX](https://ae-plugins.docsforadobe.dev/smartfx/smartfx/) を実装前に確認する。

### 3.2 通常 Render と Smart Render の二重経路

現在は `PF_Cmd_RENDER` と `PF_Cmd_SMART_PRE_RENDER` / `PF_Cmd_SMART_RENDER` の両方を持つ。通常 Render は `params[]` から直接値を読み、Smart Render は時刻付き `PF_CHECKOUT_PARAM` / checkin で値を取得している。この二経路で、型変換、クランプ、デフォルト、処理順がずれる危険がある。実際、履歴には共通レンダーパスのリファクターと `PF_FpLong` から `float` への明示変換がある。

次回は以下を最初から行う。

- 「ホストからパラメーターを読む処理」と「正規化済みの不変な render settings を作る処理」を分ける。
- 通常/Smart の両経路が同じ settings 型と同じコア関数へ到達するようにする。
- checkout に成功したものは、エラー経路を含め必ず checkin する。入力 pixel checkout も同様に対にする。
- エラーを後続処理で上書きしない。最初のエラーと cleanup のエラーを区別する。

### 3.3 AE と Premiere のピクセル形式・UI 差

コードは `appl_id == kAppID_Premiere` でホストを分け、Premiere 起動時に `PF_PixelFormatSuite1` で `PrPixelFormat_BGRA_4444_8u` を宣言する。AE 側は 8-bit ARGB、Premiere 側は 8-bit BGRA として別コールバックを使う。また Premiere では一部 UI パラメーターを固定・無効化している。

つまり「AE SDK のエフェクトなら Premiere でもそのまま動く」とは限らない。次回は次を仕様化する。

- ホスト別のサポート表（AE/Premiere、バージョン、8/16/32 bpc、CPU/GPU）。
- チャンネル順、premultiplied alpha の扱い、row alignment、負の `rowbytes`。
- Premiere に提示する pixel format と、実際に `GetPixelFormat` で受けた形式。不明形式を黙って BGRA と解釈せず、形式名・値をログに出して明示的なエラーにする。
- ホストごとのパラメーター表示・変更可否。識別は表示名ではなく安定した parameter ID で行う。

Premiere 固有の suite は、使用する SDK の `PrSDKAESupport.h`、`PrSDKPixelFormat.h` と SDK サンプルを、その SDK バージョンに合わせて確認する。

### 3.4 MFR はフラグを立てる前にスレッド安全性が必要

履歴では、`QuantInfo*` を refcon で共有する実装に thread-safety の TODO を置き、レンダー呼び出しごとの値コピーへ変更してから MFR を有効化している。これは正しい順番である。その後も out flag の名称・数値と PiPL の修正が続いており、ランタイムで返す `out_flags2` と PiPL の宣言を一致させる難しさも表れている。

次回の MFR チェックリストは以下の通り。

- render 中に書き換える global/static、遅延初期化、共有キャッシュ、乱数器を置かない。
- パラメーターをレンダー呼び出し単位の値オブジェクトへコピーし、pixel callback からは `const` として参照する。
- LUT などを共有するなら、寿命、所有権、不変性、破棄のタイミングを設計する。
- ホストから渡された suite / world / handle を別フレームや別スレッドへ保存しない。
- MFR 有効/無効で画像一致を比較し、複数フレーム同時書き出しをストレステストする。
- `GlobalSetup` と PiPL の能力フラグを同時に更新し、数値を記憶で手入力せず、対象 SDK ヘッダーで定義を確認する。

MFR の要件は [Multi-Frame Rendering in AE](https://ae-plugins.docsforadobe.dev/effect-details/multi-frame-rendering-in-ae/) を参照する。

### 3.5 PiPL、エントリポイント、バージョンはロード可否に直結する

PiPL は単なる説明ファイルではない。現在の `.r` には Windows x64、Mac Intel 64、Mac ARM64 のエントリポイント、API バージョン、effect version、out flags、match name がある。履歴では PiPL のパス修正、version packed value の同期、MFR flag の数値修正が発生している。

次回は次を自動化する。

- プラグイン名、match name、category、バージョン、out flags の単一の定義元を作り、C++ と PiPL の差分を検査する。
- match name は公開後に変更しない。既存プロジェクトがエフェクトを再発見するための永続 ID と考える。
- Windows のビルドでは `.r → .rr → .rrc → .rc → resource` のどこで失敗したかをログで確認する。
- 「ホストに表示されない」場合、コピー先を増やすフォールバックを作る前に、対象バイナリの architecture、export、PiPL resource、ホストの plugin loading log、重複配置を確認する。

PiPL の役割は [PiPL Resources](https://ae-plugins.docsforadobe.dev/effect-basics/pipl-resources/) を参照する。

### 3.6 SDK / コンパイラー制約とクロスプラットフォーム C++

履歴には「C++17 依存を避ける」修正、Windows の `min/max` マクロ衝突回避、macOS のログを `fprintf` にする修正がある。Windows だけで書いたコードを後から Mac に持っていくと、この種の差が一度に現れる。

- 採用する C++ 標準を `spec.md` と両プロジェクトで固定する。
- コアでは Win32 型・API・SDK header を使わない。
- `std::min` / `std::max` と Windows マクロの衝突を設計段階で避ける（必要なら Windows include 前の `NOMINMAX` など、原因に対する対策を採る）。
- 固定幅整数、明示 cast、サイズ・符号の警告を重視する。
- OS ごとのログ出力先を薄い adapter に閉じ込める。
- Windows で warning-as-error、Mac で相当する警告を有効にし、両方の CI でコンパイルする。

## 4. 次のエフェクトをゼロから作る推奨順序

1. **`spec.md` を作る。** 効果の数式、座標依存、近傍範囲、alpha、色空間、ホスト/OS/CPU/bpc、Smart Render/MFR/GPU の対象、非対応を決める。
2. **対象 SDK の最小サンプルを複製してロード確認する。** 名前だけ変えた pass-through を AE と Premiere の双方で表示・適用・保存・再読込する。
3. **match name と parameter ID を確定する。** 表示文字列と分離し、公開後に ID や追加順を不用意に変えない。削除ではなく予約を検討する。
4. **純粋なコアを作る。** SDK 非依存の pixel/settings 型を使い、静止画像・小さな既知配列で unit test を先に書く。
5. **8-bit の通常 Render を一本通す。** ARGB/BGRA、alpha、rowbytes、奇数サイズ、1×1、透明画素を検証する。
6. **AE/Premiere 分岐を明示する。** pixel format を交渉し、未対応形式は診断可能なログ付きで失敗させる。
7. **Smart Render を追加する。** まず全フレーム相当で通常 Render と画像一致させ、その後 ROI を小さくする。いきなり最適化しない。
8. **MFR を追加する。** 共有可変状態がないことをレビュー・テストしてから能力フラグを立てる。
9. **追加 bpc / GPU は別マイルストーンにする。** 8/16/32 bpc の変換を一つの曖昧なテンプレートに押し込まず、精度と alpha の期待値をテストする。
10. **二つのホストでリリース試験する。** プレビューだけでなく、書き出し、プロキシ、部分解像度、複数エフェクト、プロジェクト再読込も行う。

## 5. Windows 開発環境の作り方

### 5.1 必要なもの

このリポジトリの現在の基準は以下である。

- 64-bit Windows。
- Visual Studio 2022。Desktop development with C++、MSVC v143、Windows 10/11 SDK、MSBuild を導入する。
- Adobe After Effects C++ SDK。ダウンロード元と対象ホストとの互換性は [After Effects C++ SDK Guide](https://ae-plugins.docsforadobe.dev/) および SDK の release notes で確認する。
- テスト対象の AE と Premiere。両方に同じ SDK 由来プラグインをロードして確認する。
- Git。コアの自動テストを作る場合は任意の test framework も導入する。

SDK は空白を含まない固定ディレクトリへ展開すると custom build の引用符問題を減らせる。ただし、このプロジェクトの `AESDK_ROOT` は `Headers`、`Resources`、`Util` が直下にあるディレクトリを指す必要があり、README の例では SDK の `Examples\` を指している。末尾の `\` も既存 project の `$(AESDK_ROOT)Headers` という連結に必要である。

### 5.2 環境変数とビルド

「x64 Native Tools Command Prompt for VS 2022」を開く。新規シェルだけで試すなら `set`、永続化するなら `setx` を使う。`setx` は現在のシェルには反映されない点に注意する。

```bat
set "AESDK_ROOT=F:\ae25.6_61.64bit.AfterEffectsSDK\Examples\"
set "AE_PLUGIN_BUILD_DIR=%CD%\platform\Win\x64"

if not exist "%AESDK_ROOT%Headers\AE_Effect.h" exit /b 1
if not exist "%AESDK_ROOT%Resources\PiPLTool.exe" exit /b 1

msbuild platform\Win\MSX1PaletteQuantizer.vcxproj ^
  /m /p:Configuration=Release /p:Platform=x64
```

`AE_PLUGIN_BUILD_DIR` を設定しない場合とした場合で `OutDir` の評価が変わり得るため、ビルドログの最終出力パスを必ず確認する。新規プロジェクトでは未定義時の既定値を project 内に置き、空の環境変数からルート相対パスができないようにする。

### 5.3 配置と起動

管理者権限で次へ `.aex` をコピーする。

```text
C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore\
```

このリポジトリでは `tools\copy_aex_to_mediacore.bat` も使える。開発中に毎回管理者コピーを避ける方法を採る場合でも、配置先を一つに決め、古い同名バイナリを複数フォルダーに残さない。ホストを完全終了してから入れ替え、ファイルの更新時刻・version・architecture を確認して再起動する。

### 5.4 デバッグ

1. `.aex` の Debug 構成をビルドし、PDB と一緒に保持する。
2. Visual Studio から AE または Premiere を起動するか、起動済み process に Attach する。native code を選択する。
3. `EffectMain`、`GlobalSetup`、`ParamsSetup`、`Render`、`SmartPreRender`、`SmartRender` に breakpoint を置く。
4. ロードされない場合は、breakpoint より先にホストの plugin loading log、Windows Event Viewer、`dumpbin /headers` と `dumpbin /exports`、PiPL resource の生成ログを調べる。
5. 値が取れない、suite が取得できない、pixel format が違う場合は、`cmd`、`appl_id`、host/version、parameter ID、error code、pixel format、矩形、rowbytes をログに出し、原因を特定する。適当な既定値や別形式へのフォールバックで隠さない。

### 5.5 最低限の検証マトリクス

| 軸 | ケース例 |
|---|---|
| Host | AE / Premiere |
| Render path | 通常 / Smart / MFR on・off |
| Frame | 1×1、7/8/9 px 幅、奇数サイズ、4K、部分 ROI |
| Memory | padding 付き rowbytes、可能なら負 rowbytes、透明/半透明 |
| Timeline | 先頭/中間/末尾、静止、複数フレーム同時書き出し |
| Composition | 前後に blur/transform/crop、プリコンポーズ、部分解像度 |
| Result | reference PNG との pixel diff、クラッシュ、リーク、再現性 |

本プロジェクトのような座標依存効果では、フルフレーム描画と複数の部分 ROI を合成した描画の pixel diff が特に重要である。

## 6. macOS 開発環境の補足（要実機検証）

### 6.1 必要なものと既存プロジェクト

- 対象 AE/Premiere が動く macOS と Mac 実機。
- App Store または Apple Developer から取得した Xcode と Command Line Tools。
- 対象ホストに適合する AE SDK。
- `platform/Mac/MSX1PaletteQuantizer.xcodeproj` と `platform/Mac/MSX1PaletteQuantizer.plugin-Info.plist`。

既存 Xcode project は `$(AESDK_ROOT)/Headers`、`Resources`、`Util`、および `src/core` を参照し、bundle extension を `.plugin` にしている。PiPL には Intel 64 と ARM64 の entry が記載されている。ただし **PiPL に両 architecture を書くだけでは universal binary にならない**。target の `ARCHS`、各 dependency、実際の Mach-O slices を確認する必要がある。

### 6.2 設定・ビルドの出発点

GUI から起動した Xcode は shell の環境変数を継承しない場合があるため、`AESDK_ROOT` は Scheme の environment、`.xcconfig`、または Xcode build setting として明示する方が再現しやすい。例:

```sh
export AESDK_ROOT="/path/to/AfterEffectsSDK/Examples"
xcodebuild \
  -project platform/Mac/MSX1PaletteQuantizer.xcodeproj \
  -target MSX1PaletteQuantizer \
  -configuration Release \
  ARCHS="arm64 x86_64" ONLY_ACTIVE_ARCH=NO
```

実際の SDK 配布物のディレクトリ構成に合わせ、次を事前確認する。

```sh
test -f "$AESDK_ROOT/Headers/AE_Effect.h"
test -f "$AESDK_ROOT/Util/Smart_Utils.cpp"
xcodebuild -project platform/Mac/MSX1PaletteQuantizer.xcodeproj -showBuildSettings
lipo -info path/to/MSX1PaletteQuantizer.plugin/Contents/MacOS/MSX1PaletteQuantizer
```

現在の project は古い設定を引き継いでいる可能性があり、`Headers/Win` を search path に含む、Cocoa prefix header を使うなど、現行 Xcode/SDK に本当に必要か再評価が必要である。警告を消すために設定を無差別に緩めず、SDK の現行サンプル target と比較して差の理由を確認する。

### 6.3 配置、署名、デバッグ

Adobe 共通 plugin directory は、対象ホストと SDK の資料で確認する。一般にはシステム側またはユーザー側の Adobe 共通 Plug-ins ディレクトリへ `.plugin` bundle を置くが、配布時の正確な配置先・権限・署名要件を現行ホストで検証する。

- 開発中は Xcode から対象ホスト executable を起動し、C++ breakpoint と stderr / Console のログを使う。
- `codesign -dv --verbose=4 <bundle>`、`spctl`、`otool -L`、`file`、`lipo -info` で署名、依存 library、architecture を診断する。
- Intel ホストを Apple Silicon 上の Rosetta で動かす場合と native arm64 は別ケースとして試験する。
- 社外配布では Developer ID 署名、hardened runtime、notarization が必要になる可能性が高い。要件は Apple と Adobe の現行資料を確認し、CI の秘密鍵・notary credential を安全に管理する。
- Windows の `OutputDebugStringA` は使えないため、ログ abstraction を通して stderr / `os_log` 等へ出す。release build で機密パスや大量の pixel log を残さない。

## 7. Linux で開発して Windows / macOS 両対応にできるか

### 結論

**コアロジックの主開発場所として Linux を使うことは可能で有益だが、Linux だけで正式な Windows `.aex` と macOS `.plugin` を作り、AE/Premiere 上で検証・出荷まで完結する環境は現実的ではない。** Linux 版 AE/Premiere がないためホスト内テストができず、MSVC/Windows SDK と Xcode/macOS SDK/署名・notarization もそれぞれの正規環境が必要だからである。

推奨構成は次の三段である。

1. **Linux CI:** `src/core` を GCC/Clang + sanitizer で build/test、format、static analysis、golden image diff を実行する。Adobe SDK を repository に再配布してよいかはライセンスを確認する。
2. **Windows runner:** Visual Studio/MSBuild + AE SDK で `.aex` をビルドし、可能なら Windows test machine で AE/Premiere の smoke test をする。
3. **macOS runner:** Xcode + AE SDK で x86_64/arm64 bundle をビルドし、署名/notarization と Mac 実機のホストテストをする。

MinGW や Linux 上の cross compiler で PE/COFF を生成できても、MSVC ABI、Windows resource/PiPL tool、SDK が想定する toolchain、そして実ホスト検証の問題が残る。macOS バイナリについても、非 macOS 上で Apple SDK と署名 toolchain を使う方法はライセンス・再現性・出荷の面で採用すべきでない。従って「Linux から一つの command で二 OS の CI job を起動する」は可能だが、「Linux machine 一台だけで二 OS 向け成果物を保証する」は不可、と整理するのが安全である。

この構成を成功させる鍵は、Adobe adapter を薄く保ち、効果の大部分を標準 C++ のコアとしてテスト可能にすることである。このリポジトリが途中で行った core 分離は、そのまま次回の初期設計に採用できる。

## 8. リリース前チェックリスト

- [ ] `spec.md` と実装の対応ホスト/OS/CPU/bpc/ROI/MFR が一致している。
- [ ] C++、PiPL、Info.plist、配布ファイル名の version と識別子が一致している。
- [ ] Windows x64 と macOS の必要 slices を binary inspection で確認した。
- [ ] AE と Premiere の双方で表示、適用、保存、再読込、書き出しを確認した。
- [ ] 通常 Render / Smart Render / MFR の reference image が一致する。
- [ ] pixel format、alpha、rowbytes、空/部分 ROI、境界サイズを試験した。
- [ ] 未対応形式は診断可能なエラーとなり、黙ったフォールバックをしない。
- [ ] thread sanitizer 等のコア試験と MFR stress test を行った。
- [ ] 古い同名 plugin を除去し、clean machine で配置試験をした。
- [ ] macOS 配布物の署名/notarization、Windows 配布方法、第三者ライセンスを確認した。
