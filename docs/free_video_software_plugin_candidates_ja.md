# 無料で利用できる動画ソフトへの対応候補

## 1. この文書の目的

MSX1PaletteQuantizer を、Adobe After Effects / Premiere Pro 以外の、無料で利用できる動画ソフトへ展開する場合の候補を整理する。
ここでいう「無料」には、オープンソースソフトウェアだけでなく、無償版を提供する商用ソフトウェアも含める。

調査日: **2026-08-20**

> **ユーザー数についての注意**
>
> 各ソフトのアクティブユーザー数や、動画編集機能だけの利用者数について、比較できる公式統計はほとんど公開されていない。
> そのため本書では、根拠のない人数を推定せず、「非公開」と明記したうえで、知名度、配布規模、コミュニティー、対応形式などを人気の参考指標として扱う。
> GitHub の star 数やダウンロード数もユーザー数とは一致しないため、採用判断では最新版を別途確認すること。

## 2. 結論

優先順位は次のとおりとする。

1. **OpenFX（OFX）版を作り、DaVinci Resolve と Natron を同じアダプター層で対象にする**
2. **frei0r 版を作り、Shotcut と Kdenlive を対象にする**
3. Blender、Olive Editor、VapourSynth は、利用者から明確な要望があった場合に個別検討する

最初の対象としては **DaVinci Resolve** が最も有力である。無償版の知名度が高く、映像制作の実運用に適しており、OFX を採用すれば Natron にも展開できる可能性がある。
ただし、ホストごとの画像形式、座標、スレッド、タイルレンダリング、パラメーター保存互換性は異なるため、「同じ OFX バイナリーが無条件に全ホストで動く」とは考えない。

## 3. 候補比較

| 候補 | 無料提供形態 | 動作プラットフォーム | 主な拡張方法 | コア共通化 | ユーザー数 | 人気・対象層の目安 | 優先度 |
|---|---|---|---|---|---|---|---|
| **DaVinci Resolve** | 商用製品の無償版あり | Windows / macOS / Linux | OpenFX | **高い** | 公式の比較可能な数値は非公開 | 映像編集、カラー、合成まで含む著名な統合製品。候補中で最も広い層へ届く可能性が高い | **A** |
| **Natron** | オープンソース、無料 | Windows / macOS / Linux | OpenFX | **高い** | 非公開 | ノードベース合成に特化。Resolve より利用者層は狭いが、OFX の検証先として相性がよい | **A-** |
| **Shotcut** | オープンソース、無料 | Windows / macOS / Linux | MLT / frei0r | **中～高** | 非公開 | 無料のクロスプラットフォーム編集ソフトとして定着。一般編集ユーザーへ届きやすい | **B+** |
| **Kdenlive** | オープンソース、無料 | Linux / Windows / macOS | MLT / frei0r | **中～高** | 非公開 | KDE 系の代表的動画編集ソフト。特に Linux ユーザーへの到達性が高い | **B+** |
| **Blender Video Sequence Editor** | オープンソース、無料 | Windows / macOS / Linux | Python Add-on、内部エフェクト、Compositor | **中～低** | Blender 全体の利用者数と VSE 利用者数を分離した公式値は非公開 | Blender 自体は非常に著名だが、動画編集専用ユーザーの規模は判断できない | **C** |
| **Olive Editor** | オープンソース、無料 | Windows / macOS / Linux | ホスト固有実装（版により変動） | **低い** | 非公開 | 将来性はあるが、開発版の変化と拡張 API の安定性が採用リスク | **C** |
| **VapourSynth** | オープンソース、無料 | Windows / macOS / Linux など | C/C++ API、Python スクリプト | **高い** | 非公開 | GUI 編集ソフトではなく、スクリプト処理・エンコード用途の技術者向け | **C** |

プラットフォーム表記は、各プロジェクトが公式に配布またはサポート対象として案内するデスクトップ OS を基準にした。CPU アーキテクチャ、Linux ディストリビューション、OS バージョン、無償版における機能差はリリースごとに確認が必要である。

## 4. 候補ごとの特徴

### 4.1 DaVinci Resolve

- 編集、カラーグレーディング、Fusion 合成、音声、書き出しを一つにまとめた統合型ソフト。
- 無償版と有償の Studio 版があり、MSX1PaletteQuantizer の想定ユーザーにとって導入障壁が低い。
- 標準プラグイン API として OpenFX を利用できるため、画像処理コアを Adobe SDK から分離した現在の構造を活かしやすい。
- 実装前に、対象とする Resolve のバージョンと、無償版でのサードパーティー OFX の読み込み・配布条件を実機で確認する。
- Linux 版にはコーデック、GPU、ディストリビューションなどの制約があり得るため、「Linux 対応」を単一環境の確認だけで保証しない。

**適性:** 最優先。まず Windows と macOS で OFX の最小実装を検証し、その後 Linux を追加する。

### 4.2 Natron

- After Effects よりも Nuke に近い、ノードベースの合成ソフト。
- OpenFX を中核にしているため、Resolve 向け OFX アダプターの移植性を確認する第二ホストに適する。
- タイムライン編集よりコンポジット用途が中心であり、一般的な動画編集者への到達規模は Resolve、Shotcut、Kdenlive より限定的と考えられる。
- OFX 仕様への準拠確認には有用だが、Resolve で動けば Natron でも動くと仮定せず、ホスト別の自動・実機テストを用意する。

**適性:** OFX 版と同時に検証する価値が高い。

### 4.3 Shotcut

- MLT を基盤とする、比較的導入しやすいノンリニア動画編集ソフト。
- frei0r エフェクトを利用できるため、薄い frei0r ラッパーから既存 C++ コアを呼ぶ構成が考えられる。
- OFX と frei0r はパラメーター宣言、画像受け渡し、ライフサイクルが別物であり、OFX ラッパー自体の共用はできない。
- パラメーターの表示順、範囲、初期値、列挙値が Adobe 版と一致するかをテストする必要がある。

**適性:** OFX 版の次の有力候補。

### 4.4 Kdenlive

- Shotcut と同様に MLT を利用するノンリニア動画編集ソフト。
- frei0r を共通の入口にできれば、一つの実装で Shotcut と Kdenlive の双方を狙える。
- エフェクトのメタデータや UI への露出方法はホスト依存部分が残る可能性がある。
- Linux での配布先、ライブラリ探索、ABI、パッケージ形式の違いを考慮する必要がある。

**適性:** frei0r 版を作る場合は Shotcut と同じ段階で検証する。

### 4.5 Blender Video Sequence Editor

- Blender に含まれる Video Sequence Editor（VSE）を利用する案。
- Python Add-on から CLI をフレームごとに起動する方式は、処理速度、色管理、一時ファイル、キャンセル、エラー追跡に問題が出やすいため、正式対応の第一案にはしない。
- 内部エフェクトや Compositor ノードとして統合する場合、Blender 固有 API とビルドへの依存が大きく、単独配布可能なプラグインより保守負担が高い。

**適性:** Blender ユーザーから需要が確認できた場合の追加候補。

### 4.6 Olive Editor

- オープンソースのノンリニア編集ソフトで、UI とワークフローには魅力がある。
- 安定した外部プラグイン ABI を前提に設計しにくく、ホスト側の開発状況に追随するコストが大きい。

**適性:** 現段階では監視対象。拡張 API と安定版の状況を再調査してから判断する。

### 4.7 VapourSynth

- Python から映像フィルターを組み立てるフレームサーバーで、一般的な GUI 動画編集ソフトとは利用形態が異なる。
- C/C++ プラグインからコアを呼び出しやすく、バッチ処理や再現可能なスクリプト処理には向く。
- 本プロジェクトには既に CLI があるため、GUI 編集ソフト対応を優先する目的では追加価値が相対的に小さい。

**適性:** 技術者向けの要望がある場合に検討する。

## 5. コード共通化の実現性

### 5.1 現状

量子化処理とパレットは `src/core/` に置かれ、Adobe SDK に依存する処理は `src/ae/` に分離されている。このため、アルゴリズムを各ホスト向けに書き直す必要はない。

共通利用できるもの:

- MSX1 / MSX2 パレット
- 色空間変換、前処理、ディザリング、量子化
- 横 8 ドット内 2 色制限の各アルゴリズム
- `QuantInfo` と列挙値
- LUT 読み込み（ホストのファイルアクセス規約を満たす範囲）

ホストごとに必要なもの:

- パラメーターの登録、UI 表示、値の取得
- ホストの画像バッファーとコアの画素形式の変換
- ROI、タイル、row stride、上下方向、アルファ、色深度への対応
- レンダリング時刻、スレッド、キャンセル通知への対応
- プラグインの検出情報、署名、インストール、パッケージング

### 5.2 推奨する層構造

```text
Host SDK (AE / OFX / frei0r / ...)
        ↓
薄いホストアダプター
  - パラメーター変換
  - PixelView の組み立て
  - エラーをホストへ通知
        ↓
共通レンダー API
  - ホスト非依存の画像ビュー
  - パラメーター検証
  - 1 回のフレーム処理
        ↓
既存 MSX1PQCore
```

新しいホストごとにコアへ条件分岐を追加するのではなく、ホスト差はアダプターで吸収する。対応不能な画素形式や不正な stride を暗黙に別処理へフォールバックせず、ホスト名、画素形式、サイズ、stride、レンダー時刻を診断ログへ出して明示的に失敗させる。

### 5.3 共通化率の見込み

厳密な工数測定前の設計上の目安であり、完成コードの行数比を保証するものではない。

| 組み合わせ | 共通化できる範囲 | 見込み |
|---|---|---|
| AE/Premiere と OFX | `src/core/` のアルゴリズム、設定モデル、共通テスト | 高い |
| Resolve と Natron | OFX アダプターの大部分とコア | 非常に高い。ただしホスト互換対応は分離する |
| Shotcut と Kdenlive | frei0r ラッパーとコア | 非常に高い |
| OFX と frei0r | コアと共通レンダー API。SDK ラッパーは別 | 中～高 |
| Blender Add-on とネイティブプラグイン | アルゴリズムのみ。呼び出し・配布・UI は別 | 中～低 |

## 6. 実装前に決める事項

1. 対象ホストと最低対応バージョン
2. Windows / macOS / Linux の優先順位と CPU アーキテクチャ
3. 8-bit RGBA を最初の対応形式とするか、16-bit / float も初版から扱うか
4. ホストの色管理後の値を処理するのか、特定の色空間を要求するのか
5. アルファを保持するか、premultiplied / straight をどの層で変換するか
6. パラメーター ID と初期値を Adobe 版と永続的に揃えるか
7. OFX / frei0r の SDK・ヘッダー・サンプルコードのライセンスと、バイナリー配布条件
8. 各 OS での署名、インストーラー、配置先、自動テスト方法

## 7. 推奨ロードマップ

### Phase 0: 仕様固定

- 対応範囲、非対応範囲、色・アルファ・画素形式、パラメーター互換性を `spec.md` に定義する。
- 同じ入力フレームと設定に対する期待画像を用意し、Adobe 版、CLI 版、新プラグイン版で比較できるようにする。

### Phase 1: 共通レンダー API

- 既存 `src/core/` の上に、ホスト非依存の画像ビューと 1 フレーム処理 API を追加する。
- stride、端数幅、アルファ、入力破壊の有無、決定性を単体テストする。
- 例外的な入力を黙って丸めず、原因を特定できる診断情報を定義する。

### Phase 2: OpenFX MVP

- まず 8-bit RGBA、CPU レンダリング、主要パラメーターに範囲を限定する。
- Windows / macOS の DaVinci Resolve で検証する。
- 同じソースから Natron 用をビルドし、ホスト差を互換レイヤーへ閉じ込める。
- Linux はサポート対象環境と配布方法を固定した後に追加する。

### Phase 3: frei0r MVP

- Shotcut と Kdenlive の双方で同じフレームの結果を確認する。
- frei0r で表現しにくい UI やパラメーターがある場合、コアの仕様を変えず、公開機能の差として文書化する。

### Phase 4: 需要に基づく追加対応

- Issue、リリースのダウンロード、実利用報告をホスト別に集計する。
- Blender、VapourSynth、Olive は、需要と API 安定性を再評価してから着手する。

## 8. 調査・実装時の一次資料

仕様や対応状況は変更されるため、実装開始時には以下の公式資料を再確認する。

- [OpenFX 公式サイト](https://openfx.org/)
- [OpenFX リファレンス実装・ヘッダー](https://github.com/AcademySoftwareFoundation/openfx)
- [DaVinci Resolve 公式ページ](https://www.blackmagicdesign.com/products/davinciresolve)
- [DaVinci Resolve サポートセンター](https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion)
- [Natron 公式サイト](https://natrongithub.github.io/)
- [Natron ソースリポジトリ](https://github.com/NatronGitHub/Natron)
- [frei0r 公式リポジトリ](https://github.com/dyne/frei0r)
- [Shotcut 公式機能一覧](https://shotcut.org/features/)
- [Shotcut ソースリポジトリ](https://github.com/mltframework/shotcut)
- [Kdenlive 公式サイト](https://kdenlive.org/)
- [Kdenlive ソースリポジトリ](https://invent.kde.org/multimedia/kdenlive)
- [MLT Multimedia Framework](https://www.mltframework.org/)
- [Blender Video Editing マニュアル](https://docs.blender.org/manual/en/latest/video_editing/)
- [Olive Editor 公式サイト](https://www.olivevideoeditor.org/)
- [VapourSynth 公式ドキュメント](https://www.vapoursynth.com/doc/)

人気の比較に GitHub 指標を利用する場合は、同じ調査日に各公式リポジトリの star、リリース頻度、直近リリース日を記録する。ただし、それらを「ユーザー数」と表記しない。
