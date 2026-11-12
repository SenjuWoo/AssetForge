# Providers

Providers are optional external owners. Detection is read-only: AssetForge never installs, updates, launches a server or changes another tool's configuration.

Missing providers produce an actionable reason. Jobs that require one exit with code `4` instead of silently selecting a different method.

## Detection order

1. Explicit environment variable.
2. Project configuration in `assetforge.json` under `integrations`.
3. Standard install locations.
4. Declared tool roots from `ASSETFORGE_ROOTS` and `~/.uabs/profile/TOOL-ROOTS.txt`, searched breadth-first with a small limit.

## Pillow

- Kind: Python package.
- Used for: image inspection, resize, re-encode, thumbnail and comparison.
- Detect: import/package metadata.
- If absent: image recipes fail with an install hint. `Install.ps1 -WithImages` installs it into the local environment.

## glTF-Transform

- Kind: Node CLI.
- Used for: conservative GLB optimization.
- Detect: `gltf-transform` on `PATH`, or `.tools/node_modules/@gltf-transform/cli/bin/cli.js` in the project or AssetForge root.
- Local developer setup:

```bash
npm install --prefix .tools @gltf-transform/cli
```

No runtime command installs it. The optimizer runs with simplification, compression, flattening, joining, instancing, palette merging and solid-texture pruning disabled, so hierarchy and textures are preserved.

## Khronos glTF Validator

- Kind: Node package plus the packaged `validate_glb.mjs` bridge.
- Detect: `node` plus `.tools/node_modules/gltf-validator/index.js`.
- Local developer setup:

```bash
npm install --prefix .tools gltf-validator
```

When absent, validation reports `GLB-014 NOT_TESTED`; when present, the official report is recorded alongside AssetForge's structural checks.

## Blender

- Kind: external application, background mode.
- Detect: `BLENDER_EXE`, legacy `BLENDER`, `PATH`, Blender Foundation install folders, or the Steam install at `C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe`.
- The probe runs `--version` and requires a `Blender x.y` version string. A shim that starts some other program is reported as unavailable rather than accepted. Candidate paths are tried in order, so a broken PATH shim does not hide a real install.
- Used by: `mesh-gameready`, `blender-sample`, and all `blender.skills.*` steps. `mesh-gameready` imports a GLB directly and does not need blender-skills. The default cap is 20,000 triangles. See [GAME-READY.md](GAME-READY.md).
- Blender is GPL software and remains independently installed and maintained.

## blender-skills

- Kind: optional external skill owner.
- Upstream: [EL4CTEO/blender-skills](https://github.com/EL4CTEO/blender-skills), MIT License, Copyright (c) 2026 EL4CTEO.
- Tested revision: `389f28addc79b87b28764898e38e7bf408d14b77` (v1.2.0), with Blender 5.2.3 LTS on Windows. Upstream `validate_skills.py` passed and its 69 headless tests passed with Blender.
- Detect: `BLENDER_SKILLS_ROOT`, project `integrations.blender_skills`, `~/blender-skills`, `~/.claude/skills`, or `~/.agents/skills`. Both a checkout (`<root>/skills/<name>/SKILL.md`) and an installed folder (`<root>/<name>/SKILL.md`) are accepted. Required markers are `blender-core` and `blender-asset-qa`.
- All 28 discovered skills are exposed in the catalog. The verified surface executes six upstream skills: `blender-core` (headless runner), `blender-pbr-materials`, `blender-asset-qa`, `blender-export-pipelines`, `blender-game-optimization` (`mesh_stats.py`, `make_lods.py`) and `blender-retopology-uv` (`auto_retopo.py`, `uv_pack.py`, `texel_density.py`). Other skills are cataloged and tested upstream, not claimed as executed by AssetForge.
- AssetForge reports the detected commit when the root is a Git checkout. It never installs, updates or rewrites upstream skills.
- Catalog and routing:

```bash
assetforge blender-skills --json
assetforge blender-skills --route materials
```

Routes cover core, scene, modeling, sculpting, UV, texturing, materials, baking, rigging, animation, optimization, export, QA, rendering, lighting, simulation, clothing, hair, facial, NPR, weather, video, addon, pipeline and recipes. The JSON includes each skill's `SKILL.md`, scripts and absolute path for the agent.

- Execution: all skill scripts go through upstream `blender-core/scripts/run_in_blender.py` with `BLENDER_EXE` set to the executable AssetForge verified. No Blender MCP server is required; the integration is headless.
- Whitelist: `blender.skills.run` accepts only the operations documented for `blender-optimize` and `blender-retopo-uv` (`mesh-stats`, `make-lods`, `auto-retopo`, `uv-pack`, `texel-density`) and only their documented arguments. It has no arbitrary script path or shell access.
- Recipes: `blender-pipeline`, `blender-qa`, `blender-optimize` and `blender-retopo-uv`.
- QA gate: `blender-asset-qa/scripts/qa_check.py` runs on the generated `.blend` before delivery. Any reported error fails the job. Warnings must be fixed or explicitly accepted with `warning_note`; zero warnings is the verified path. `review_shots.py` writes random and wire contact sheets. A generated sheet is recorded as `BLENDER-QA-RENDER PASS`, while `BLENDER-QA-VISUAL` remains `NOT_TESTED` until `visual_review=approved` and a recorded `approval_note` are supplied. QA numeric results and project-relative review paths are stored in the asset provenance.
- Current pipeline result: 108 triangles, 0 QA errors, 0 warnings, GLB exported, optimized and validated with `GLB-014 PASS` when the Khronos validator is installed.

### Hermes Agent compatibility

The skills use standard `SKILL.md` frontmatter and are compatible with Hermes's external skill directories. AssetForge exposes them without copying them. To also load them natively in Hermes, add the directory to `~/.hermes/config.yaml` or the active profile config:

```yaml
skills:
  external_dirs:
    - ${BLENDER_SKILLS_ROOT}/skills
```

Then restart the Hermes session. External dirs are scanned alongside the local profile; project skills still take precedence. Do not add the directory if you do not want the 28 skills in the agent's skill index. AssetForge does not edit Hermes configuration.

### Install blender-skills

Use the upstream installer; AssetForge does not duplicate it:

```bash
git clone https://github.com/EL4CTEO/blender-skills
./blender-skills/install/install.sh          # macOS / Linux
.\blender-skills\install\install.ps1          # Windows
```

Then set `BLENDER_SKILLS_ROOT` to the checkout or to the installed skills directory (`~/.agents/skills` or `~/.claude/skills`).


## comfy-kit

- Kind: external owner folder.
- Detect: `COMFY_KIT_ROOT`, project `integrations.comfy_kit`, `~/comfy-kit`, or declared roots. Required markers: `TOOLS/image-stack.ps1` and `presets/presets.json`.
- Used by: `comfy-generate` and `comfy-import`.
- Generation delegates to the owner's `TOOLS/image-stack.ps1 generate` and directs output into the AssetForge asset. No model files, presets, nodes or SwarmUI configuration are modified.
- If the owner's default model is unavailable, pass `--set model=<model-name>` or configure comfy-kit itself.

## img2threejs

- Kind: external skill checkout.
- Detect: `IMG2THREEJS_ROOT`, project `integrations.img2threejs`, standard skill directories, or declared roots. Required markers: `SKILL.md` and `forge/stage1_intake/probe_image.py`.
- Used by: `img2threejs-probe`, which runs the upstream technical image probe only.
- Full reference-image reconstruction and procedural Three.js generation are agent-driven upstream workflows and are **not** automated by AssetForge.

## Adding a provider

A provider needs:

- a unique id and title;
- capabilities and required dependencies;
- supported platforms;
- an availability result with a reason;
- structured argument-list execution with timeout and output verification;
- truthful `NOT_TESTED` when its real integration has not run.

Do not make the core import a provider's runtime dependencies.
