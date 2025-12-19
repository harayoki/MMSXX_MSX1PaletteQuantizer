# WebAssembly bindings for MSX1 Palette Quantizer

## 推奨ディレクトリ構成
```
src/webasm/
  CMakeLists.txt        # または build.sh など、Emscripten 用ビルドスクリプト
  MSX1PQWebBindings.cpp # C API エクスポート実装（emscripten）
  README.md             # このガイド
```

## エクスポート API 例（C）
`MSX1PQWebBindings.cpp` が以下を提供する想定。
- `msx1pq_malloc` / `msx1pq_free` : JS 側が安全に wasm ヒープを確保・解放するためのラッパー。
- `msx1pq_quantize_rgba` : RGBA 入力を量子化して RGBA 出力を返す。
- `msx1pq_encode_png` / `msx1pq_decode_png` : lodepng を使った PNG 変換。

### バインディング実装サンプル
`MSX1PQWebBindings.cpp` を参照。`extern "C"` + `EMSCRIPTEN_KEEPALIVE` でエクスポートし、`Msx1pqOptions` から `QuantInfo` に変換して `quantize_image` を叩く。

## 初期化と呼び出しの流れ
1. 必要に応じて `Msx1pqOptions` を JS 側の `HEAP32`/`HEAPF32` に書き込む。
2. RGBA バッファ（`width * height * 4` バイト）を wasm ヒープにコピー。
3. `msx1pq_quantize_rgba` を呼ぶと、新しい RGBA バッファへのポインタとサイズが返る。
4. JS 側で結果を `HEAPU8.subarray(ptr, ptr + size)` で読み出し、終わったら `msx1pq_free` で解放。

### エクスポート関数シグネチャ
```c
// ヒープ確保/解放
void* msx1pq_malloc(size_t size);
void  msx1pq_free(void* ptr);

// 量子化（RGBA→RGBA）
int msx1pq_quantize_rgba(const uint8_t* rgba,
                         int width,
                         int height,
                         const Msx1pqOptions* opts,
                         uint8_t** out_rgba,
                         int* out_size);

// PNG 変換（任意）
int msx1pq_encode_png(const uint8_t* rgba, int width, int height,
                      uint8_t** out_png, int* out_size);
int msx1pq_decode_png(const uint8_t* png, int size,
                      uint8_t** out_rgba, int* out_width, int* out_height);
```

## emcc ビルドコマンド例
```bash
emcc -O3 \
  -std=c++17 \
  -I./src/core \
  src/webasm/MSX1PQWebBindings.cpp \
  src/core/MSX1PQCore.cpp src/core/MSX1PQOutput.cpp src/core/MSX1PQPalettes.cpp src/core/lodepng.cpp \
  -s ENVIRONMENT=web \
  -s MODULARIZE=1 -s EXPORT_NAME="MSX1PQ" \
  -s EXPORTED_FUNCTIONS='["_msx1pq_malloc","_msx1pq_free","_msx1pq_quantize_rgba","_msx1pq_encode_png","_msx1pq_decode_png"]' \
  -s ALLOW_MEMORY_GROWTH=1 \
  -s MALLOC="emmalloc" \
  -o dist/msx1pq.js
```

## JS からの最小呼び出し例
```js
import createMSX1PQ from './msx1pq.js';

const wasm = await createMSX1PQ();
const { HEAPU8, HEAP32, _msx1pq_malloc, _msx1pq_free, _msx1pq_quantize_rgba } = wasm;

const width = 320, height = 240;
const inputBytes = new Uint8Array(width * height * 4); // RGBA 入力

// 入力コピー
const inputPtr = _msx1pq_malloc(inputBytes.length);
HEAPU8.set(inputBytes, inputPtr);

// オプション配置
const optsPtr = _msx1pq_malloc(4 * 9); // int*6 + float*3 (簡易例)
HEAP32[optsPtr >> 2] = 1; // color_system = MSX1
HEAP32[(optsPtr >> 2) + 1] = 2; // distance_mode = HSV
HEAP32[(optsPtr >> 2) + 2] = 1; // eightdot_mode = NONE
HEAP32[(optsPtr >> 2) + 3] = 1; // use_dither
HEAP32[(optsPtr >> 2) + 4] = 0; // use_palette_color
HEAP32[(optsPtr >> 2) + 5] = 0; // use_dark_dither
// floatsは HEAPF32 を使って同じ位置に書き込む
const f32 = new Float32Array(wasm.HEAPU8.buffer, optsPtr + 24, 3);
f32[0] = 1.0; // w_h
f32[1] = 1.0; // w_s
f32[2] = 1.0; // w_v

// 出力ポインタ用ワーク領域
const outPtrPtr = _msx1pq_malloc(8); // uint8_t** + int*
const outSizePtr = outPtrPtr + 4;

const ret = _msx1pq_quantize_rgba(inputPtr, width, height, optsPtr, outPtrPtr, outSizePtr);
if (ret !== 0) throw new Error(`quantize failed: ${ret}`);

const outPtr = HEAP32[outPtrPtr >> 2];
const outSize = HEAP32[outSizePtr >> 2];
const outBytes = HEAPU8.slice(outPtr, outPtr + outSize);

_msx1pq_free(outPtr);
_msx1pq_free(outPtrPtr);
_msx1pq_free(optsPtr);
_msx1pq_free(inputPtr);
```

## core 側での注意点（Wasm 化）
- 例外を使わない前提なので `throw` を追加しない。`std::vector` の確保失敗は戻り値で検知して JS にエラーコードを返す。
- `new/delete` ではなく `malloc/free` を API 経由で隠蔽し、JS 側で解放を徹底する。
- スレッドやファイル I/O に依存しない（Emscripten の `-s ENVIRONMENT=web` を前提）。
- 条件付きコンパイルで AE/CLI 依存をビルド対象から除外し、`__EMSCRIPTEN__` 下では Web 固有の設定を追加する程度に留める。
- `lodepng` はそのままビルド可能。PNG 入出力は wasm 内で完結させ、ブラウザの File API 側とは JS ブリッジでやり取りする。
