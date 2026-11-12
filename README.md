# AssetForge

AssetForge is a standalone, agent-friendly toolkit for producing, validating and packaging game assets. It provides a Python CLI, versioned JSON contracts and optional adapters for Blender, blender-skills, glTF-Transform, the Khronos glTF Validator, comfy-kit and img2threejs.

It is designed to work on its own and can also be registered as a companion of the Ultimate AI Starter Bundle. The bundle is recommended, never required.

AssetForge orchestrates other owners. It does not fork Blender, ComfyUI, Graphite, img2threejs or any other upstream application.

## Quick start (Windows)

1. Run `START-HERE.bat`. It creates a repo-local `.venv`, installs Pillow for the image recipes, and runs `doctor`.
2. Create or enter a project folder and run:

```bat
assetforge.cmd init .
assetforge.cmd recipes
assetforge.cmd providers
assetforge.cmd run image-prep --input path\to\source.png
```

The installer writes only inside the AssetForge folder. It does not install Blender, Node packages, ComfyUI or model weights.

## Quick start (Linux / macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[images]"
assetforge doctor
```

## Commands

```text
assetforge --version
assetforge doctor [--json]
assetforge capabilities [--json]
assetforge providers [--json]
assetforge blender-skills [--route NAME] [--json]
assetforge init [path] [--name NAME]
assetforge recipes [list | RECIPE] [--json]
assetforge run RECIPE [--input PATH | NAME=PATH] [--set KEY=VALUE] [--dry-run] [--json]
assetforge status [JOB_ID | --last] [--json]
assetforge inspect ASSET [--json]
assetforge validate ASSET [--json]
assetforge export ASSET --target roblox|godot|generic [--dry-run] [--json]
```

Exit codes are stable: `0` success, `2` usage/recipe error, `3` missing project/asset/job, `4` provider unavailable, `5` validation or budget failure, `6` run failure.

## Recommended texture workflow (comfy-kit)

For free local texture generation, the recommended companion is **comfy-kit**. It owns the SwarmUI/ComfyUI installation, models, presets and MCP configuration; AssetForge only delegates a render and keeps the result inside the asset.

```bat
assetforge.cmd run comfy-generate --set "prompt=seamless weathered steel, top-down, tileable" --set width=1024 --set height=1024
assetforge.cmd run texture-pack --input occlusion=ao.png --input roughness=rough.png --input metallic=metal.png
assetforge.cmd export ASSET --target godot
```

`comfy-import` also accepts an existing comfy-kit output folder. If comfy-kit is not installed, `comfy-generate` exits with code `4` and a clear provider message; AssetForge never installs models or changes comfy-kit configuration.

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

Blender 5.2+ is required. `BLENDER_EXE` selects the executable; detection also checks `PATH`, Blender Foundation folders and the Steam install. Blender MCP is optional and not required; every step runs headless.

Upstream was tested at revision `389f28addc79b87b28764898e38e7bf408d14b77` (v1.2.0) with Blender 5.2.3. AssetForge reports the detected revision but never updates upstream automatically. Installation, Hermes `skills.external_dirs` setup, routing and the tested evidence are in [docs/PROVIDERS.md](docs/PROVIDERS.md).

## Showcase

![AssetForge-generated enchanted fire sword](examples/assets/enchanted-fire-sword.png)

This low-poly enchanted-fire sword is the AssetForge showcase for stylized game props. It is built directly in Blender and included at `examples/assets/enchanted-fire-sword.glb`, with a reproducible generator (`examples/generate-enchanted-fire-sword.py`) producing the faceted blade shell, ember layers, raised runes and scrollwork, bat-wing crossguard, wrapped hilt, finial and floating sparks. It is a strong reference for low-poly stylized games such as Roblox-style worlds and games; Roblox Studio import was not run, so engine integration remains `NOT_TESTED`.

The concept exploration for this prop was generated locally through the comfy-kit / SwarmUI workflow; the shipped GLB itself is project-owned procedural geometry and does not depend on the generated reference images. comfy-kit remains the recommended free local companion for texture work.

## Built-in recipes

| Recipe | Purpose |
| --- | --- |
| `image-prep` | Inspect, resize/re-encode and thumbnail a raster image. |
| `texture-pack` | Pack occlusion, roughness and metallic maps into an RGB ORM texture. |
| `sprite-atlas` | Pack a folder of images into a grid atlas with JSON frame metadata. |
| `glb-inspect` | Record geometry statistics and structural conformance. |
| `glb-optimize` | Conservative glTF-Transform pass: no simplification, compression, flattening or joining. |
| `blender-sample` | Headless Blender bevelled-cube export. Requires Blender. |
| `blender-pipeline` | Procedural crate → PBR material → upstream QA gate → GLB export → optimize → validate. |
| `blender-qa` | Run upstream `blender-asset-qa` and review sheets on an existing `.blend`. |
| `blender-optimize` | Run whitelisted `blender-game-optimization` operations (`mesh-stats`, `make-lods`). |
| `blender-retopo-uv` | Run whitelisted `blender-retopology-uv` operations (`auto-retopo`, `uv-pack`, `texel-density`). |
| `comfy-generate` | Delegate one render to an installed comfy-kit. |
| `comfy-import` | Copy newest images from a comfy-kit output folder. |
| `img2threejs-probe` | Run the external img2threejs technical image probe. |
| `img2threejs-codegen` | Generate an editable Three.js factory from an ObjectSculptSpec through upstream img2threejs. |

Every recipe writes a job record under `.assetforge/jobs/` with per-step status, errors and tool versions. Assets keep copied inputs, a JSON manifest, relative artifact paths and provenance. A manifest-defined primary artifact decides what gets exported.

`img2threejs-codegen` output is TypeScript source, not a mesh or texture. It remains an editable intermediate artifact: it is not compiled, rendered or exported by AssetForge. Compilation, visual fidelity and game-ready conversion are unverified and must be handled by the owning workflow.

## Capability status

| Capability | Status | Boundary |
| --- | --- | --- |
| CLI, projects, jobs, manifests | VERIFIED | Full test suite |
| Image processing | VERIFIED | Pillow; alpha and JPEG-flatten behavior tested |
| PBR channel packing | VERIFIED | R=occlusion, G=roughness, B=metallic; mismatched sizes fail unless resize is explicitly enabled |
| Sprite atlases | VERIFIED | Deterministic grid, frames copied into the asset, JSON frame rectangles |
| Texture-only export | VERIFIED packaging | Generic/Godot/Roblox packages contain PNGs and no mesh; engine import `NOT_TESTED` |
| GLB inspection | VERIFIED | Standard-library container and accessor reader |
| Structural GLB validation | VERIFIED | Not a conformance claim |
| Khronos glTF validation | VERIFIED when installed | Optional Node package in `.tools`; otherwise `NOT_TESTED` |
| Conservative GLB optimization | VERIFIED | glTF-Transform; source and optimized structure compared |
| Blender background export | VERIFIED | Real Blender 5.2.3; `blender-sample` and upstream export pipeline executed |
| blender-skills catalog and routing | VERIFIED | 28 skills detected at upstream revision `389f28a`; CLI list/route tested |
| Blender asset QA gate | VERIFIED | Upstream `blender-asset-qa`: 108 tris, 0 errors, 0 warnings; review sheets generated and explicitly approved after inspection |
| Blender optimization and retopo/UV | VERIFIED | `blender-optimize` and `blender-retopo-uv` execute whitelisted `blender-game-optimization` and `blender-retopology-uv` scripts on real Blender; mutating operations create new `.blend` artifacts |
| comfy-kit generation | VERIFIED | Exercised against a running comfy-kit; generation is delegated |
| img2threejs probe | VERIFIED | Technical probe only; reconstruction remains agent-driven |
| img2threejs spec-to-Three.js codegen | VERIFIED | Upstream deterministic generator; consumes an ObjectSculptSpec, not a raw image |
| img2threejs reconstruction | PLANNED | Image-to-spec review gates remain agent-driven |
| Roblox / Godot / generic export | VERIFIED packaging | Mesh and texture-only packages; no engine import was run, always `NOT_TESTED` |
| AI 3D providers, rigging, MCP, teardown, Graphite | PLANNED | Not implemented yet |

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
| comfy-kit | Free local texture generation (recommended companion) | `comfy-generate` exits with code `4` |
| img2threejs | Technical image probe and spec-to-Three.js codegen | `img2threejs-probe` / `img2threejs-codegen` exit with code `4` |

Detection paths and environment variables are documented in [docs/PROVIDERS.md](docs/PROVIDERS.md).

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
- AssetForge does not upload assets to Roblox, Godot or any account, and never stores credentials.

## Adding to the Ultimate AI Starter Bundle

The bundle detects an installed AssetForge through the companion registry and routes asset work to it. AssetForge keeps ownership of installation, updates, diagnostics, dependencies and releases. The proposed registry entry and the exact contract are in [docs/UABS-INTEGRATION.md](docs/UABS-INTEGRATION.md) and `integration/COMPANIONS.asset-forge.json`.

No bundle files are modified by this repository.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Providers](docs/PROVIDERS.md)
- [Recipes](docs/RECIPES.md)
- [Upstream evaluations](docs/UPSTREAM-EVALUATIONS.md)
- [Bundle integration](docs/UABS-INTEGRATION.md)
- [Third-party notices](docs/THIRD-PARTY-NOTICES.md)
- [Plan](PLAN.md) / [State](STATE.md) / [Validation evidence](VALIDATION.md)
- [Roadmap](ROADMAP.md) / [Release checklist](RELEASE.md)

## License

MIT. See [LICENSE](LICENSE).
