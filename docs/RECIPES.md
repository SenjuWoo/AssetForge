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

Requires the glTF-Transform provider. Missing provider exits `4`. This recipe does not decimate. A 700,000-triangle GLB stays 700,000 triangles.

## `mesh-convert`

Import a mesh in Blender and write one GLB, then inspect and validate it. Rigs, skin weights and animations are kept. The source is read where it lies, so an `.obj` finds its `.mtl` and a `.gltf` finds its `.bin` and textures; the project keeps a copy of the main file as provenance.

| Parameter | Type | Default |
| --- | --- | --- |
| `animations` | boolean | `true` |
| `timeout` | integer | `900` |

Formats: `.fbx`, `.obj`, `.stl`, `.ply`, `.gltf`, `.glb`, `.usd`, `.usda`, `.usdc`, `.usdz`, `.abc`, `.blend`, and `.dae` where the Blender build still has a Collada importer. The importer is looked up at run time; a format the build cannot read fails with exit `6` and the importer's own message.

```bash
assetforge probe model.fbx
assetforge run mesh-convert --input model.fbx
assetforge run mesh-convert --input model.fbx --set animations=false
```

Needs the Blender provider. Missing Blender exits `4`.

## `mesh-gameready`

Import a GLB in Blender, collapse it under a hard triangle cap, shrink textures, validate, and compare. The written file is deleted and the job fails if it is over the cap. A 700,000-triangle sculpt does not ship. Full rules: [GAME-READY.md](GAME-READY.md).

| Parameter | Type | Default |
| --- | --- | --- |
| `budget` | `game`, `hero`, `accessory` | `game` (20,000 triangles, texture 1024) |
| `tris` | integer | `0` (use the budget; a value above the cap is rejected) |
| `texture` | integer | `0` (use the budget; a larger request is clamped down) |
| `timeout` | integer | `900` |

`hero` is 30,000 triangles and texture 2048. It is not a Roblox mesh. `accessory` is 4,000 triangles and texture 1024.

```bash
assetforge run mesh-gameready --input mesh=model.glb
assetforge run mesh-gameready --input mesh=model.glb --set budget=hero
assetforge run mesh-gameready --input mesh=model.glb --set budget=accessory
```

Needs the Blender provider. Missing Blender exits `4`. `glb-optimize` is a different, conservative pass and does not replace this recipe.

## `blender-sample`

Build a deterministic bevelled cube in headless Blender and export GLB. This is a small provider smoke test, not the QA-gated production pipeline.

| Parameter | Type | Default |
| --- | --- | --- |
| `timeout` | integer | `240` |

Requires Blender. Missing provider exits `4`.

## `blender-pipeline`

Build a procedural crate, apply an upstream `blender-pbr-materials` preset, run the mandatory `blender-asset-qa` gate, write random and wire review sheets, export GLB through `blender-export-pipelines`, optimize with glTF-Transform and validate.

| Parameter | Type | Default |
| --- | --- | --- |
| `preset` | string | `wood` |
| `warning_note` | string | empty (warnings fail the gate) |
| `visual_review` | `pending`, `approved` | `pending` |
| `approval_note` | string | empty (required when approved) |
| `timeout` | integer | `600` |

```bash
assetforge run blender-pipeline
assetforge run blender-pipeline --set visual_review=approved --set "approval_note=Inspected random and wire sheets"
assetforge export ASSET --target godot
```

Requires Blender, `blender-skills` and glTF-Transform. A QA error fails the job. Warnings fail unless `warning_note` records why each is acceptable. Review sheets are generated as `BLENDER-QA-RENDER`; `BLENDER-QA-VISUAL` is `NOT_TESTED` until plain visual review is explicitly approved. The pipeline exports 108 triangles in the tested revision and records QA numbers plus project-relative review paths in the asset.

## `blender-qa`

Run `blender-asset-qa` and review shots against an existing `.blend`. Use this as a gate for assets produced by other Blender workflows.

| Parameter | Type | Default |
| --- | --- | --- |
| `object` | string | empty (all visible meshes) |
| `warning_note` | string | empty (warnings fail the gate) |
| `visual_review` | `pending`, `approved` | `pending` |
| `approval_note` | string | empty (required when approved) |
| `timeout` | integer | `300` |

```bash
assetforge run blender-qa --input blend=asset.blend --set object=SM_Crate
assetforge run blender-qa --input blend=asset.blend --set visual_review=approved --set "approval_note=..."
```

Any QA error fails the job. Warnings require `warning_note`. Review sheets are written even when QA fails, so the failure is inspectable. This recipe records reports and previews only; it does not export a mesh.

## `blender-optimize`

Run a whitelisted `blender-game-optimization` operation on an existing `.blend`. Input is copied into the asset; mutating `make-lods` writes a new `blender-make-lods.blend` artifact and never overwrites the input.

| Parameter | Type | Default |
| --- | --- | --- |
| `operation` | `mesh-stats`, `make-lods` | `mesh-stats` |
| `objects` | string, space-separated | empty (all meshes) |
| `budget` | `mobile`, `roblox`, `web`, `vr`, `console`, `pc` | empty |
| `ratios` | string, space-separated | `0.5 0.25 0.125` |
| `symmetry` | boolean | `false` |
| `cleanup` | boolean | `false` |
| `rename` | boolean | `false` |
| `collection` | string | empty |
| `timeout` | integer | `300` |

```bash
assetforge run blender-optimize --input blend=asset.blend --set operation=mesh-stats --set budget=roblox
assetforge run blender-optimize --input blend=asset.blend --set operation=make-lods --set "ratios=0.5 0.25" --set cleanup=true
```

`mesh-stats` reports triangles, draw calls and textures against the selected budget. `make-lods` creates `*_LOD1`, `*_LOD2`, ... copies using upstream Decimate. The output is intermediate; run `blender-qa` and `blender-pipeline`/export after mutation.

## `blender-retopo-uv`

Run a whitelisted `blender-retopology-uv` operation on an existing `.blend`. Input is copied into the asset; mutating operations write a new `blender-<operation>.blend` artifact and never overwrite the input.

| Parameter | Type | Default |
| --- | --- | --- |
| `operation` | `auto-retopo`, `uv-pack`, `texel-density` | `uv-pack` |
| `objects` | string, space-separated | empty (all meshes) |
| `method` | `quadriflow`, `decimate`, `planar` for retopo; `smart`, `seams`, `min_stretch` for UVs | `decimate` for retopo, `smart` for UVs |
| `tris` | integer | `10000` |
| `voxel` | string | empty (auto) |
| `symmetry` | boolean | `false` |
| `angle` | string | `66.0` |
| `seams_from_sharp` | string | empty |
| `res` | integer | `2048` |
| `margin_px` | integer | `8` |
| `lightmap` | boolean | `false` |
| `shape` | `AABB`, `CONVEX`, `CONCAVE` | `AABB` |
| `target` | string, px/m | empty (report only) |
| `timeout` | integer | `300` |

```bash
assetforge run blender-retopo-uv --input blend=dense.blend --set operation=auto-retopo --set method=decimate --set tris=5000
assetforge run blender-retopo-uv --input blend=asset.blend --set operation=uv-pack --set method=smart --set res=2048
assetforge run blender-retopo-uv --input blend=asset.blend --set operation=texel-density --set res=2048
assetforge run blender-retopo-uv --input blend=asset.blend --set operation=texel-density --set target=512
```

`auto-retopo` creates `<name>_low` copies. `uv-pack` creates/packs UVs (and a lightmap UV2 when requested). `texel-density` reports density unless `target` is supplied, in which case it writes a scaled/repacked `.blend`. None of these recipes claims engine-import success or visual approval.


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

**Recommended for free local texture work:** comfy-kit owns installation, models and presets; AssetForge delegates the render, then `texture-pack` can combine the generated maps into an ORM texture. AssetForge never installs or redistributes models.

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
