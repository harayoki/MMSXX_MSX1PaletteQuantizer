# WebAssembly bindings for MSX1 Palette Quantizer

ブラウザ上で core（MSX1PQCore / Output / Palettes / lodepng）を呼ぶための最小バインディング。リアルタイム更新前提なので **コンテキスト方式** でバッファを保持し、malloc/free を乱発しない。

## エクスポート API（C）

```c
// コンテキスト
msx1pq_context* msx1pq_create_context(void);
void            msx1pq_destroy_context(msx1pq_context* ctx);

// オプション（壊れにくい key/value 方式）
int msx1pq_set_option_i(msx1pq_context* ctx, int key, int value);
int msx1pq_set_option_f(msx1pq_context* ctx, int key, float value);

// 量子化（RGBA -> RGBA, out は既存バッファ or ctx 内部）
int msx1pq_quantize_rgba_into(msx1pq_context* ctx,
                              const uint8_t* rgba,
                              int width,
                              int height,
                              uint8_t* out_rgba,   // null なら ctx 内部を書き換え
                              int out_capacity,    // bytes
                              int* out_size);      // bytes
int msx1pq_get_last_rgba(const msx1pq_context* ctx,
                         const uint8_t** out_ptr,
                         int* out_size);

// PNG 生成（必要時のみ）
int msx1pq_encode_png_from_rgba(msx1pq_context* ctx,
                                const uint8_t* rgba,
                                int width,
                                int height,
                                const uint8_t** out_png,
                                int* out_size);
int msx1pq_get_last_png(const msx1pq_context* ctx,
                        const uint8_t** out_png,
                        int* out_size);

// SC2 生成（256x192 のみ対応、内部で量子化して VRAM 相当を返す）
int msx1pq_encode_sc2_from_rgba(msx1pq_context* ctx,
                                const uint8_t* rgba,
                                int width,
                                int height,
                                const uint8_t** out_sc2,
                                int* out_size);
int msx1pq_get_last_sc2(const msx1pq_context* ctx,
                        const uint8_t** out_sc2,
                        int* out_size);

// wasm ヒープ確保/解放（JS 側でまとめて再利用）
void* msx1pq_malloc(size_t size);
void  msx1pq_free(void* ptr);
```

### オプション key 一覧
```c
// msx1pq_set_option_i
MSX1PQ_OPT_COLOR_SYSTEM  // MSX1PQCore::MSX1PQ_COLOR_SYS_*
MSX1PQ_OPT_DISTANCE_MODE // MSX1PQCore::MSX1PQ_DIST_MODE_*
MSX1PQ_OPT_EIGHTDOT_MODE // MSX1PQCore::MSX1PQ_EIGHTDOT_MODE_*
MSX1PQ_OPT_USE_DITHER    // 0/1
MSX1PQ_OPT_USE_PALETTE   // 0/1 (palette 固定モード)
MSX1PQ_OPT_USE_DARK_DITH // 0/1

// msx1pq_set_option_f
MSX1PQ_OPT_W_H, MSX1PQ_OPT_W_S, MSX1PQ_OPT_W_V // HSV 重み
MSX1PQ_OPT_W_R, MSX1PQ_OPT_W_G, MSX1PQ_OPT_W_B // RGB 重み
```

### バッファ寿命と再確保条件
- `msx1pq_quantize_rgba_into` は ctx->work_pixels を再利用。`width * height` が変わると再確保され、JS 側は **毎回 quantize 後に `msx1pq_get_last_rgba` でポインタを取り直す**。
- PNG/SC2 も ctx 内部バッファを再利用するので、生成後に `msx1pq_get_last_png` / `msx1pq_get_last_sc2` で最新ポインタを取得。
- `out_rgba` を自前で確保する場合のみ `out_capacity` をチェック。不要なら `out_rgba = 0, out_capacity = 0` で OK。

## emcc ビルドコマンド例

```bash
emcc -O3 \
  -std=c++17 -fno-exceptions -fno-rtti \
  -I./src/core \
  src/webasm/MSX1PQWebBindings.cpp \
  src/core/MSX1PQCore.cpp src/core/MSX1PQOutput.cpp src/core/MSX1PQPalettes.cpp src/core/lodepng.cpp \
  -s ENVIRONMENT=web \
  -s MODULARIZE=1 -s EXPORT_NAME="MSX1PQ" \
  -s EXPORTED_FUNCTIONS='["_msx1pq_create_context","_msx1pq_destroy_context","_msx1pq_set_option_i","_msx1pq_set_option_f","_msx1pq_quantize_rgba_into","_msx1pq_get_last_rgba","_msx1pq_encode_png_from_rgba","_msx1pq_get_last_png","_msx1pq_encode_sc2_from_rgba","_msx1pq_get_last_sc2","_msx1pq_malloc","_msx1pq_free"]' \
  -s ALLOW_MEMORY_GROWTH=0 \
  -s INITIAL_MEMORY=268435456 \
  -s MALLOC="emmalloc" \
  -o src/webasm/dist/msx1pq.js
```

- 256x192 + 作業バッファなら 128 MiB 固定で十分。HFDまで扱う場合は 256 MiB とする。より大きい入力を扱う場合は `INITIAL_MEMORY` を増やす。どうしても足りない場合のみ `-s ALLOW_MEMORY_GROWTH=1` にし、量子化後は毎回ポインタを取り直す。

## JS 最小サンプル（Canvas プレビュー + PNG/SC2 生成）

```js
import createMSX1PQ from './msx1pq.js';

const mod = await createMSX1PQ();
const ctx = mod._msx1pq_create_context();

// 一度だけ確保して使い回す
const width = 256;
const height = 192;
const inputBytes = new Uint8Array(width * height * 4); // RGBA ソース
const inputPtr = mod._msx1pq_malloc(inputBytes.length);

// 出力ポインタ/サイズ受け取り用ワーク（4byte*2）
const viewPtr = mod._msx1pq_malloc(8);
const viewSizePtr = viewPtr + 4;

const OptI = {
  COLOR_SYSTEM: 1,
  DISTANCE_MODE: 2,
  EIGHTDOT_MODE: 3,
  USE_DITHER: 4,
  USE_PALETTE: 5,
  USE_DARK_DITH: 6,
};
const OptF = { W_H: 1, W_S: 2, W_V: 3, W_R: 4, W_G: 5, W_B: 6 };

// オプション更新
function setOptions(opts) {
  mod._msx1pq_set_option_i(ctx, OptI.DISTANCE_MODE, opts.distanceMode);
  mod._msx1pq_set_option_i(ctx, OptI.USE_DITHER, opts.useDither ? 1 : 0);
  mod._msx1pq_set_option_f(ctx, OptF.W_R, opts.wr);
  mod._msx1pq_set_option_f(ctx, OptF.W_G, opts.wg);
  mod._msx1pq_set_option_f(ctx, OptF.W_B, opts.wb);
}

// Canvas 描画
const canvas = document.querySelector('canvas');
const ctx2d = canvas.getContext('2d');
const imageData = ctx2d.createImageData(width, height);

function preview() {
  // 入力コピー
  mod.HEAPU8.set(inputBytes, inputPtr);

  // 量子化（out_ptr/out_capacity は 0 -> ctx 内部に出力）
  mod._msx1pq_quantize_rgba_into(ctx, inputPtr, width, height, 0, 0, 0);

  // 最新バッファを取得して Canvas にコピー
  mod._msx1pq_get_last_rgba(ctx, viewPtr, viewSizePtr);
  const outPtr = mod.HEAP32[viewPtr >> 2];
  const outSize = mod.HEAP32[viewSizePtr >> 2];
  const outView = mod.HEAPU8.subarray(outPtr, outPtr + outSize);

  imageData.data.set(outView);
  ctx2d.putImageData(imageData, 0, 0);
}

async function exportPng() {
  // 既に量子化済みの RGBA をそのまま PNG へ
  mod._msx1pq_get_last_rgba(ctx, viewPtr, viewSizePtr);
  const lastPtr = mod.HEAP32[viewPtr >> 2];
  mod._msx1pq_encode_png_from_rgba(ctx, lastPtr, width, height, viewPtr, viewSizePtr);
  const pngPtr = mod.HEAP32[viewPtr >> 2];
  const pngSize = mod.HEAP32[viewSizePtr >> 2];
  const pngBytes = mod.HEAPU8.slice(pngPtr, pngPtr + pngSize);
  const blob = new Blob([pngBytes], { type: 'image/png' });
  // download ...
}

async function exportSc2() {
  mod._msx1pq_get_last_rgba(ctx, viewPtr, viewSizePtr);
  const lastPtr = mod.HEAP32[viewPtr >> 2];
  const ret = mod._msx1pq_encode_sc2_from_rgba(ctx, lastPtr, width, height, viewPtr, viewSizePtr);
  if (ret !== 0) throw new Error('SC2 export failed: ' + ret);
  const sc2Ptr = mod.HEAP32[viewPtr >> 2];
  const sc2Size = mod.HEAP32[viewSizePtr >> 2];
  const sc2Bytes = mod.HEAPU8.slice(sc2Ptr, sc2Ptr + sc2Size);
  // download or embed sc2Bytes
}

// スライダー/チェック変更時: setOptions(...) -> preview()
// 「確定」ボタン: exportPng() または exportSc2()
```

### JS 側メモリ運用のポイント
- `inputPtr`, `viewPtr` は一度確保して再利用。毎フレームの malloc/free を避ける。
- `msx1pq_get_last_*` で得たポインタは **次の量子化/エンコードまで有効**。サイズが変わると再確保されるので、そのたびに View を取り直す。
- SC2 は 256x192 固定。それ以外のサイズを渡すとエラーコード `-2` を返す。
