# AssetForge

AssetForge is a standalone, agent-friendly toolkit for producing, validating and packaging game assets. It provides a Python CLI, versioned JSON contracts and optional adapters for Blender, glTF-Transform, the Khronos glTF Validator, comfy-kit and img2threejs.

It is designed to work on its own and can also be registered as a companion of the Ultimate AI Starter Bundle. The bundle is recommended, never required.

AssetForge orchestrates other owners. It does not fork Blender, ComfyUI, Graphite, img2threejs or any other upstream application.

## Quick start (Windows)

1. Run `START-HERE.bat`. It creates a repo-local `.venv` and runs `doctor`.
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
assetforge init [path] [--name NAME]
assetforge recipes [list | RECIPE] [--json]
assetforge run RECIPE [--input PATH | NAME=PATH] [--set KEY=VALUE] [--dry-run] [--json]
assetforge status [JOB_ID | --last] [--json]
assetforge inspect ASSET [--json]
assetforge validate ASSET [--json]
assetforge export ASSET --target roblox|godot|generic [--dry-run] [--json]
```

Exit codes are stable: `0` success, `2` usage/recipe error, `3` missing project/asset/job, `4` provider unavailable, `5` validation or budget failure, `6` run failure.

## Built-in recipes

| Recipe | Purpose |
| --- | --- |
| `image-prep` | Inspect, resize/re-encode and thumbnail a raster image. |
| `texture-pack` | Pack occlusion, roughness and metallic maps into an RGB ORM texture. |
| `sprite-atlas` | Pack a folder of images into a grid atlas with JSON frame metadata. |
| `glb-inspect` | Record geometry statistics and structural conformance. |
| `glb-optimize` | Conservative glTF-Transform pass: no simplification, compression, flattening or joining. |
| `blender-sample` | Headless Blender bevelled-cube export. Requires Blender. |
| `comfy-generate` | Delegate one render to an installed comfy-kit. |
| `comfy-import` | Copy newest images from a comfy-kit output folder. |
| `img2threejs-probe` | Run the external img2threejs technical image probe. |
| `img2threejs-codegen` | Generate an editable Three.js factory from an ObjectSculptSpec through upstream img2threejs. |

Every recipe writes a job record under `.assetforge/jobs/` with per-step status, errors and tool versions. Assets keep copied inputs, a JSON manifest, relative artifact paths and provenance. A manifest-defined primary artifact decides what gets exported.

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
| Blender background export | IMPLEMENTED / UNVERIFIED | Adapter is written; Blender is not installed in this environment |
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
| Blender | Background sample/export | `blender-sample` exits with code `4` |
| comfy-kit | Image generation | `comfy-generate` exits with code `4` |
| img2threejs | Technical image probe | `img2threejs-probe` exits with code `4` |

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

## License

MIT. See [LICENSE](LICENSE).
