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

Combine three grayscale maps into one RGB texture: R=occlusion, G=roughness, B=metallic. If a map differs in size it is resized to the occlusion map and the job reports a warning.

| Parameter | Type | Default |
| --- | --- | --- |
| `thumbnail` | integer | `256` |

```bash
assetforge run texture-pack \
  --input occlusion=ao.png \
  --input roughness=rough.png \
  --input metallic=metal.png
```

## `sprite-atlas`

Pack every image in a folder (sorted by filename, up to 64) into a grid. `atlas.png` is the deliverable and `atlas.json` records the cell size, padding, columns and frame rectangles. Alpha is preserved.

| Parameter | Type | Default |
| --- | --- | --- |
| `columns` | integer | `4` |
| `padding` | integer | `2` |
| `thumbnail` | integer | `256` |

```bash
assetforge run sprite-atlas --input path/to/frames --set columns=4
```

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
