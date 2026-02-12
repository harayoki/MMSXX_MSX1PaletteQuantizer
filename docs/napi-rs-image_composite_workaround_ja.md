# `@napi-rs/image` の `Transformer does not support composite` エラー対処

`@napi-rs/image` の `Transformer` API には、`sharp` でいう `composite()` 相当のレイヤー合成機能がありません。
そのため、`Transformer` に対して合成前提の処理を書こうとすると、実行時に
`Transformer does not support composite` が発生します。

## 原因

- `@napi-rs/image` の `transform()` は主に単一画像の変換（リサイズ・回転など）向けです。
- 複数画像の重ね合わせ（オーバーレイ/アルファ合成）は `Transformer` の責務外です。

## 対処方針

### 1. 合成が必要な処理だけ別ライブラリに切り出す（推奨）

- 変換: `@napi-rs/image`
- 合成: `sharp` など

```ts
import { transform } from '@napi-rs/image'
import sharp from 'sharp'

const base = await transform(inputBuffer, { resize: { width: 640, height: 480 } })

const out = await sharp(base)
  .composite([{ input: overlayPngBuffer, top: 24, left: 24 }])
  .png()
  .toBuffer()
```

### 2. 合成を自前実装する

ピクセル配列を展開してアルファブレンドを実装する方法です。
ただし実装コストと保守コストが高く、通常は 1 の方法が実用的です。

## 設計上の注意

- `@napi-rs/image` は高速ですが、全機能が `sharp` と 1 対 1 で対応しているわけではありません。
- 既存コードが `sharp` 前提なら、**合成だけ `sharp` を残すハイブリッド構成**が安全です。
- 将来の差し替えを考え、画像処理を `transform`（単体変換）と `compose`（合成）で層分離してください。

## チェックリスト

- `transform()` の戻り値に対して `composite()` 相当を直接呼んでいないか
- 合成処理の責務を別関数/別モジュールに分けているか
- 出力フォーマット（PNG/JPEG/WebP）を合成後に統一しているか
