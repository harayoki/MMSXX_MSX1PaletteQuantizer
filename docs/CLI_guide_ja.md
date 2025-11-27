# CLI ガイド (日本語)

CLI ツール `msx1pq_cli` は、PNG 画像を MSX1/2 風の TMS9918 ルール準拠の画像に変換します。After Effects や Premiere Pro を開かずにバッチ処理や自動化を行いたい場合に便利です。

## ビルド方法

```bash
make
```

ビルド後、実行ファイルは `bin/msx1pq_cli` に生成されます。

## 使い方

```bash
./bin/msx1pq_cli --input <ファイル|ディレクトリ> --output <ディレクトリ> [オプション]
```

- 単一の PNG ファイル、またはディレクトリ内の複数 PNG をまとめて処理できます。
- 出力先ディレクトリが存在しない場合は自動で作成します。
- `--force` を付けない場合、既存ファイルの上書き前に確認を求めます。

### 主なオプション（`--help` の内容）

| オプション | 説明 |
| --- | --- |
| `--input, -i <ファイル|ディレクトリ>` | 入力 PNG ファイルまたはディレクトリを指定。 |
| `--output, -o <ディレクトリ>` | 変換結果を保存するディレクトリを指定。 |
| `--output-prefix <文字列>` | 出力ファイル名の先頭に付ける文字列。 |
| `--color-system <msx1|msx2>` | MSX1（15色）か MSX2 パレットを選択。既定: `msx1`。 |
| `--dither` / `--no-dither` | ディザリングの有無。既定: 有効。 |
| `--dark-dither` / `--no-dark-dither` | 暗部専用ディザを使うか。既定: 有効。 |
| `--8dot <none|fast|basic|best|best-attr|best-trans>` | 8ドット2色アルゴリズムを選択。既定: `best`。 |
| `--distance <rgb|hsb>` | パレット選択時の色距離計算方法。既定: `hsb`。 |
| `--weight-h`, `--weight-s`, `--weight-b` | `hsb` 距離使用時の色相・彩度・明度の重み（0〜1）。 |
| `--pre-sat <0-10>` | 量子化前に彩度を上げる。既定: `1.0`。 |
| `--pre-gamma <0-10>` | 量子化前にガンマを暗くする。既定: `1.0`。 |
| `--pre-highlight <0-10>` | 量子化前にハイライトを明るくする。既定: `1.0`。 |
| `--pre-hue <-180-180>` | 量子化前に色相を回転。既定: `0.0`。 |
| `--pre-lut <.cube ファイル>` | 量子化前に CUBE 形式の 3D LUT を適用。 |
| `-f, --force` | 確認なしで出力を上書き。 |
| `-v, --version` | バージョン情報を表示。 |
| `-h, --help` | ロケールに応じたヘルプを表示（日本語優先）。 |
| `--help-ja`, `--help-en` | 日本語または英語のヘルプを強制表示。 |

### 使用例

単一ファイルを `dist/` に出力:

```bash
./bin/msx1pq_cli -i input.png -o dist
```

`assets/frames` 内の PNG を MSX2 カラー・ディザリングなしで一括変換:

```bash
./bin/msx1pq_cli --input assets/frames --output dist --color-system msx2 --no-dither --force
```

彩度を強め、8dot アルゴリズムに "best-attr" を使用:

```bash
./bin/msx1pq_cli -i shot.png -o dist --pre-sat 1.4 --8dot best-attr
```

`msx_` という接頭語を付け、前処理で LUT を適用:

```bash
./bin/msx1pq_cli -i shot.png -o dist --output-prefix msx_ --pre-lut looks/film.cube
```
