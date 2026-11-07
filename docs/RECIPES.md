# Recipes

Recipes are declarative JSON. They name step kinds implemented in `src/assetforge/runner.py`; they cannot introduce shell commands or arbitrary code. Project recipes in `<project>/recipes/` override built-ins by id.

## `image-prep`

Inspect, resize/re-encode and thumbnail a raster image.

| Parameter | Type | Default |
| --- | --- | --- |
| `format` | `png`, `jpeg`, `webp` | `png` |
| `width` | integer | `0` (keep) |
| `height` | integer | `0` (keep) |
| `quality` | integer | `90` |
| `thumbnail` | integer | `256` |

```bash
assetforge run image-prep --input source.png --set width=512 --set format=webp
```

Alpha is preserved for PNG/WebP. JPEG output flattens alpha onto white and records a warning.

## `texture-pack`

Combine three grayscale maps into one RGB texture: R=occlusion, G=roughness, B=metallic. Maps must share the occlusion map's dimensions; mismatches fail unless `resize` is explicitly enabled. The result is **linear data**, not sRGB color — keep base color and other color maps separate.

| Parameter | Type | Default |
| --- | --- | --- |
| `resize` | boolean | `false` |

```bash
assetforge run texture-pack \
  --input occlusion=ao.png \
  --input roughness=rough.png \
  --input metallic=metal.png
```

Use `--set resize=true` only when resampling every channel to the occlusion size is acceptable; the job records a warning.

## `sprite-atlas`

Pack every image in a folder (sorted by filename, maximum 64) into a grid. Frames are copied into the asset before the atlas is built, and `atlas.json` records the cell size, padding, columns and frame rectangles plus source hashes in the job record. Alpha is preserved. The operation rejects more than 64 frames, non-positive columns, negative padding, outputs above 8192px per side, more than 33,554,432 pixels, or an estimated memory use above 512 MiB.

| Parameter | Type | Default |
| --- | --- | --- |
| `columns` | integer | `4` |
| `padding` | integer | `2` |

```bash
assetforge run sprite-atlas --input path/to/frames --set columns=4
```

Split larger sprite sets into multiple atlas jobs; nothing is silently dropped.

## `glb-inspect`

Record geometry statistics and structural checks. The source mesh becomes the primary deliverable.

```bash
assetforge run glb-inspect --input model.glb
```

## `glb-optimize`

Run glTF-Transform with conservative flags, validate the result, compare both files and set the optimized mesh as the primary deliverable.

| Parameter | Type | Default |
| --- | --- | --- |
| `timeout` | integer | `300` |

```bash
assetforge run glb-optimize --input model.glb
```

Requires the glTF-Transform provider. Missing provider exits `4`.

## `blender-sample`

Build a deterministic bevelled cube in headless Blender and export GLB.

| Parameter | Type | Default |
| --- | --- | --- |
| `timeout` | integer | `240` |

Requires Blender. Missing provider exits `4`.

## `comfy-generate`

Delegate one render to an installed comfy-kit.

| Parameter | Type | Default |
| --- | --- | --- |
| `prompt` | string, required | — |
| `preset` | string | `Anima - Author Daily (Euler + SGM)` |
| `model` | string | empty (owner default) |
| `width` | integer | `1024` |
| `height` | integer | `1024` |
| `seed` | integer | `-1` |
| `count` | integer | `1` |
| `timeout` | integer | `900` |

```bash
assetforge run comfy-generate --set "prompt=weathered steel texture, top-down"
```

Output is written inside the asset. The owner's presets and models are not changed. If the owner's default model is invalid, pass `--set model=<model-name>`.

## `comfy-import`

Copy the newest images from a comfy-kit output folder into an asset.

| Parameter | Type | Default |
| --- | --- | --- |
| `limit` | integer | `1` |
| `thumbnail` | integer | `256` |

```bash
assetforge run comfy-import --input path/to/comfy-kit/out
```

## `img2threejs-probe`

Run the upstream technical probe and store its JSON.

```bash
assetforge run img2threejs-probe --input reference.png
```

This is a probe, not reconstruction. It answers technical suitability questions and does not create a 3D model.

## `img2threejs-codegen`

Run the upstream deterministic ObjectSculptSpec-to-Three.js generator and store the editable TypeScript factory. This consumes a spec; it does not perform image reconstruction or visual review.

| Parameter | Type | Default |
| --- | --- | --- |
| `timeout` | integer | `120` |

```bash
assetforge run img2threejs-codegen --input object-sculpt-spec.json
```

Requires an installed img2threejs owner with `forge/stage3_build/generate_threejs_factory.py`. Missing provider exits `4`; a generator failure is a failed job, not a partial success.

## Custom recipes

```json
{
  "schema": 1,
  "id": "inspect-only",
  "title": "Inspect only",
  "input": {"name": "mesh", "kind": "mesh", "required": true},
  "params": {},
  "steps": ["glb.inspect", "asset.record"]
}
```

The recipe is rejected if any step is not in the implementation set.
