# Capabilities, providers and workflows

The detail behind the README: what each capability has proven, which external programs AssetForge drives, the recommended Blender and comfy-forge workflows, every built-in recipe, the project layout and the security boundaries. Recipe parameters are in [RECIPES.md](RECIPES.md); provider detection is in [PROVIDERS.md](PROVIDERS.md).

## Capability status

| Capability | Status | Boundary |
| --- | --- | --- |
| CLI, projects, jobs, manifests | VERIFIED | Full test suite |
| Image processing | VERIFIED | Pillow; alpha and JPEG-flatten behavior tested |
| PBR channel packing | VERIFIED | R=occlusion, G=roughness, B=metallic; mismatched sizes fail unless resize is explicitly enabled |
| Sprite atlases | VERIFIED | Deterministic grid, frames copied into the asset, JSON frame rectangles; the JSON ships with the export |
| Seamless textures and PBR sets | VERIFIED | `texture-generate` ran through a real SwarmUI render; seam measured; derived maps stay `TEX-DERIVED` `NOT_TESTED` |
| Cut-outs, pixel art, sheet slicing | VERIFIED | Unit and recipe tests; colour-key cut-out needs a plain background |
| Sprites from a GLB | VERIFIED | `sprite-render` on real Blender 5.3: facing directions, anchors, animations and one shared scale checked from the pixels |
| Image to 3D | IMPLEMENTED | `comfy-3d` drives comfy-forge 0.11.0's `model3d.py`; tested against a stand-in, the collapse step on a real Pixal3D mesh |
| Texture-only export | VERIFIED packaging | Generic/Godot/Roblox packages contain PNGs and no mesh; engine import `NOT_TESTED` |
| GLB inspection | VERIFIED | Standard-library container and accessor reader |
| Source probe | VERIFIED | `probe` on files and folders; read-only, no project needed |
| Structural GLB validation | VERIFIED | Container, accessors, materials, UV sets, node transforms; not a conformance claim |
| Rig and animation validation | VERIFIED | Joints, inverse bind matrices, skin weights and animation channels are consistent; deformation is not rendered |
| Embedded texture budgets | VERIFIED | Sizes read from PNG, JPEG, WebP and KTX2 headers inside the GLB |
| Mesh conversion | VERIFIED | Blender 5.3: rigged animated FBX and OBJ to GLB; other formats depend on the installed Blender build |
| Khronos glTF validation | VERIFIED when installed | Optional Node package in `.tools`; otherwise `NOT_TESTED` |
| Conservative GLB optimization | VERIFIED | glTF-Transform; source and optimized structure compared |
| Game-ready mesh collapse | VERIFIED | `mesh-gameready` decimates a GLB in Blender and fails above the budget cap (default 20,000 triangles). Real Blender 5.3 runs: a 699,878-triangle GLB to 17,000 (official validator 0 errors) and the 21,856-triangle showcase sword to 16,951 (glTF checks PASS=14, FAIL=0). Engine import remains `NOT_TESTED` |
| Blender background export | VERIFIED | Real Blender 5.3.0 (earlier 5.2.3); `blender-sample` and upstream export pipeline executed |
| blender-skills catalog and routing | VERIFIED | 28 skills detected at upstream v1.3.1 (`b1b21df`); CLI list/route tested |
| Blender asset QA gate | VERIFIED | Upstream `blender-asset-qa`: 108 tris, 0 errors, 0 warnings; review sheets generated and explicitly approved after inspection |
| Blender optimization and retopo/UV | VERIFIED | `blender-optimize` and `blender-retopo-uv` execute whitelisted `blender-game-optimization` and `blender-retopology-uv` scripts on real Blender; mutating operations create new `.blend` artifacts |
| comfy-forge image generation | VERIFIED | `comfy-generate` and `texture-generate` through comfy-forge's running SwarmUI; starting SwarmUI for a job is covered by tests, not by a live run |
| img2threejs probe | VERIFIED | Upstream v2.0.1; technical probe only; reconstruction remains agent-driven |
| img2threejs spec-to-Three.js codegen | VERIFIED | Upstream deterministic generator; consumes an ObjectSculptSpec, not a raw image |
| Roblox Studio import | NOT TESTED | No Studio run is automated |
| img2threejs reconstruction | PLANNED | Image-to-spec review gates remain agent-driven |
| Roblox / Godot / generic export | VERIFIED packaging | Mesh and texture-only packages; the export itself runs no engine, so its engine import stays `NOT_TESTED` |
| Godot import check | VERIFIED | `engine-check`: Godot 4.7.2 headless imports the GLB, then loads and instantiates it; rendering and playback are not tested |
| teardown simulator page | VERIFIED | Upstream example bundled through `teardown-build`; page opens offline (`PAGE-001`) |
| teardown film | VERIFIED | Upstream example rendered to MP4 in headless Chromium through `teardown-film`; visual review stays `NOT_TESTED` |
| Voice lines | VERIFIED | Qwen3-TTS designed a voice and cloned it for 3 lines, 100% Whisper word match; Dia and Kokoro lines also passed. Nobody listened: `AUDIO-LISTEN` stays `NOT_TESTED` |
| Sound effects | VERIFIED | MOSS-SoundEffect v2 through `audio-sfx` with CLAP prompt scores; listening stays `NOT_TESTED` |
| Audio finishing and checks | VERIFIED | Trim, fixed-gain loudness/peak levelling, encode; decode, level, true-peak, loudness, edge-silence and format checks |
| Minecraft sound export | VERIFIED packaging | Ogg files plus `sounds.json` with numbered variants grouped; game load `NOT_TESTED` |
| Music generation | VERIFIED | `audio-music`: ACE-Step 1.5 through comfy-forge, via a running SwarmUI backend and via a ComfyUI started for the job; instrumental and vocal takes passed CLAP and loudness checks. Listening and sung words stay `NOT_TESTED` |
| FFmpeg | USED | Audio finishing and measurement; `teardown-film` encodes through it; `doctor` reports version and purpose |
| ImageMagick | USED | `image-prep format=dds` writes DXT1/DXT5 with mipmaps through it |
| Rig deformation preview, MCP, Graphite | PLANNED | Not implemented yet |

`VERIFIED` means the behaviour was executed with recorded evidence. `IMPLEMENTED / UNVERIFIED` means code exists but the real integration was not exercised. A successful export is not proof that an asset works inside the target engine.

## External providers

AssetForge detects providers without installing or reconfiguring them.

| Provider | Used for | Missing behaviour |
| --- | --- | --- |
| Pillow | Image inspection and conversion | Image recipes fail with a clear message |
| glTF-Transform | GLB optimization | `glb-optimize` exits with code `4` |
| Khronos glTF Validator | Official conformance check | Recorded as `NOT_TESTED` |
| Blender | Background execution and export | `blender-sample` exits with code `4` |
| blender-skills | Recommended Blender skills catalog, QA and export | Blender steps exit with code `4` |
| comfy-forge (formerly comfy-kit) | Images, textures and sprites through SwarmUI; ACE-Step music and image to 3D through ComfyUI | The generating recipes exit with code `4` |
| img2threejs | Technical image probe and spec-to-Three.js codegen | `img2threejs-probe` / `img2threejs-codegen` exit with code `4` |
| teardown | Offline simulator pages and their films | `teardown-build` / `teardown-film` exit with code `4` |
| audio-speech / audio-sfx / audio-kokoro | Local voice and sound-effect models, installed by `assetforge audio-setup` | `audio-voice` / `audio-sfx` exit with code `4` and name the setup command |
| FFmpeg | Audio finishing and measurement, video encoding | Audio recipes exit with code `4` |
| ImageMagick | DDS output | `image-prep format=dds` exits with code `4` |

Detection paths and environment variables are documented in [PROVIDERS.md](PROVIDERS.md).

## Recommended texture workflow (comfy-forge)

For free local texture generation, the recommended companion is **comfy-forge** (formerly comfy-kit). It owns the SwarmUI/ComfyUI installation, models, presets and MCP configuration; AssetForge only delegates a render and keeps the result inside the asset.

```bat
assetforge.cmd run texture-generate --set "prompt=weathered steel plates" --set name=steel
assetforge.cmd export ASSET --target godot
```

A running SwarmUI is used as it is; otherwise comfy-forge's SwarmUI is started without a browser for the job and stopped afterwards. `seed=-1` picks a seed and records it. `comfy-import` also accepts an existing comfy-forge output folder. If comfy-forge is not installed, the generating recipes exit with code `4` and a clear provider message; AssetForge never installs models or changes comfy-forge configuration.

## Recommended Blender workflow (blender-skills)

For Blender work, the recommended provider is [EL4CTEO/blender-skills](https://github.com/EL4CTEO/blender-skills), an MIT-licensed set of 28 agent skills for modeling, UVs, PBR, baking, rigging, animation, optimization, QA and export. AssetForge exposes all 28 and executes six of them through explicit, whitelisted operations: core runner, PBR materials, asset QA, export pipelines, mesh optimization (`mesh-stats`, `make-lods`) and retopology/UV (`auto-retopo`, `uv-pack`, `texel-density`). AssetForge does not vendor upstream; point `BLENDER_SKILLS_ROOT` at a checkout or installed skills folder, then inspect the catalog:

```bat
assetforge.cmd blender-skills --json
assetforge.cmd blender-skills --route materials
assetforge.cmd run blender-pipeline
assetforge.cmd run blender-optimize --input input.blend --set operation=mesh-stats --set budget=roblox
assetforge.cmd run blender-retopo-uv --input sculpt.blend --set operation=uv-pack
assetforge.cmd export ASSET --target godot
```

`blender-pipeline` builds a procedural crate, applies an upstream PBR preset, runs the **mandatory** `blender-asset-qa` gate, writes random/wire review sheets, exports GLB through upstream `blender-export-pipelines`, optimizes it and validates it. A QA error or unaccepted warning fails the job before delivery. Rendering the review sheets is not visual approval: `BLENDER-QA-VISUAL` stays `NOT_TESTED` until an explicit `--set visual_review=approved --set approval_note="..."` records the inspection. `blender-qa` applies the same gate to an existing `.blend`. `blender-optimize` and `blender-retopo-uv` expose the mesh-statistics, LOD generation, retopology, UV packing and texel-density scripts on an existing `.blend`; mutating operations write a new `.blend` artifact and leave the input untouched.

Blender 5.2+ is required. `BLENDER_EXE` selects the executable; detection also checks `PATH`, the Blender Foundation folders, the uninstall registry, every Steam library and a portable copy under a declared tool root. Blender MCP is optional and not required; every step runs headless.

Upstream was tested at v1.3.1 (revision `b1b21dfb73bc40b874ebf2aa12645931bfed3523`) with Blender 5.3.0; v1.3.0 and v1.2.0 remain compatible. AssetForge finds a plain clone in a declared tool root, reports the detected release and revision, and never updates upstream automatically. Installation, Hermes `skills.external_dirs` setup, routing and the tested evidence are in [PROVIDERS.md](PROVIDERS.md).

## Built-in recipes

| Recipe | Purpose |
| --- | --- |
| `image-prep` | Inspect, resize/re-encode (PNG, JPEG, WebP, TGA, DDS with mipmaps) and thumbnail a raster image. |
| `texture-pack` | Pack occlusion, roughness and metallic maps into an RGB ORM texture. |
| `sprite-atlas` | Pack up to 256 images into a grid atlas with JSON frame metadata. |
| `texture-generate` | Prompt to a tileable PBR material through comfy-forge. |
| `texture-tileable` | Make a picture repeat without a seam; the seam is measured (`TEX-SEAM`). |
| `texture-pbr` | Normal (OpenGL or DirectX), height, roughness, occlusion, metallic and ORM from one colour map. |
| `sprite-generate` | Prompt to a transparent, trimmed sprite through comfy-forge. |
| `image-cutout` | Make a plain background transparent, trim, record the anchor. |
| `pixel-art` | Downscale onto a palette (built-in, file, or picked colours). |
| `sprite-slice` | Cut a sheet into frames by grid or by islands of pixels. |
| `sprite-render` | Render a GLB as sprites: 1-16 facings at a camera pitch, every animation, sheet and anchors. |
| `comfy-3d` | One picture to a game-ready GLB: comfy-forge image-to-3D, then the `mesh-gameready` collapse. |
| `mesh-convert` | FBX, OBJ, STL, PLY, glTF, USD, Alembic or `.blend` to one validated GLB through Blender; rigs and animations kept. |
| `glb-inspect` | Record geometry, rig, material and texture statistics and structural conformance. |
| `glb-optimize` | Conservative glTF-Transform pass: no simplification, compression, flattening or joining. |
| `mesh-gameready` | Collapse a generated GLB under a hard triangle cap. Default `game` fails above 20,000 triangles. |
| `blender-sample` | Headless Blender bevelled-cube export. Requires Blender. |
| `blender-pipeline` | Procedural crate → PBR material → upstream QA gate → GLB export → optimize → validate. |
| `blender-qa` | Run upstream `blender-asset-qa` and review sheets on an existing `.blend`. |
| `blender-optimize` | Run whitelisted `blender-game-optimization` operations (`mesh-stats`, `make-lods`). |
| `blender-retopo-uv` | Run whitelisted `blender-retopology-uv` operations (`auto-retopo`, `uv-pack`, `texel-density`). |
| `comfy-generate` | One render through comfy-forge (SwarmUI started for the job when it is down); image to image with `--input init=`. |
| `comfy-import` | Copy newest images from a comfy-forge output folder. |
| `img2threejs-probe` | Run the external img2threejs technical image probe. |
| `img2threejs-codegen` | Generate an editable Three.js factory from an ObjectSculptSpec through upstream img2threejs. |
| `teardown-build` | Bundle a teardown machine simulator into one offline HTML page. |
| `teardown-film` | Render a teardown simulator to MP4, or to a labelled review sheet, in headless Chromium. |
| `audio-voice` | Voice lines from text: Qwen3-TTS voice design and cloning, Dia nonverbals, Kokoro presets; Whisper-checked takes. |
| `audio-sfx` | Sound effects from text prompts with MOSS-SoundEffect v2; CLAP-checked takes. |
| `audio-music` | Songs and instrumentals from style tags (and lyrics): ACE-Step 1.5 through comfy-forge; CLAP-checked takes. |
| `audio-process` | Trim, level, convert and measure existing audio files or a folder of them. |

Every recipe writes a job record under `.assetforge/jobs/` with per-step status, errors and tool versions. Assets keep copied inputs, a JSON manifest, relative artifact paths and provenance. A manifest-defined primary artifact decides what gets exported.

`img2threejs-codegen` output is TypeScript source, not a mesh or texture. It remains an editable intermediate artifact: it is not compiled, rendered or exported by AssetForge. Compilation, visual fidelity and game-ready conversion are unverified and must be handled by the owning workflow.

## Project layout

```text
project/
  assetforge.json
  assets/<asset-id>/
    asset.json
    inputs/
    outputs/
    previews/
    exports/
  .assetforge/jobs/<job-id>/
    job.json
    run.log
```

Artifact paths in `asset.json` are project-relative and are validated against path escapes before use. Large binaries never live inside JSON. Original input locations are kept only in the job's provenance record.

## Security boundaries

- Recipes are declarative JSON. They can only name implemented step kinds; they cannot inject shell commands or arbitrary code.
- External tools run through structured argument lists with explicit working directories and timeouts. AssetForge does not install them silently.
- Asset inputs are copied into the project. Artifact paths are rejected if absolute, missing or outside the project, including `..` and symlink escapes.
- Validation and export never claim an engine import was tested. `engine_import` is always `NOT_TESTED` until a real editor run is recorded.
- AssetForge does not upload assets to Roblox, Godot or any account, and never stores credentials. Audio models run locally; their weights download from Hugging Face on first use.
