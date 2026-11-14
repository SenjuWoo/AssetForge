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
- Detect: `BLENDER_EXE`, legacy `BLENDER`, `PATH`, the Blender Foundation install folders, the folder the Windows uninstall registry records, every Steam library, and a portable copy under a declared tool root.
- The probe runs `--version` and requires a `Blender x.y` version string. A shim that starts some other program is reported as unavailable rather than accepted. Candidate paths are tried in order, so a broken PATH shim does not hide a real install.
- Used by: `mesh-gameready`, `blender-sample`, and all `blender.skills.*` steps. `mesh-gameready` imports a GLB directly and does not need blender-skills. The default cap is 20,000 triangles. See [GAME-READY.md](GAME-READY.md).
- Blender is GPL software and remains independently installed and maintained.

## blender-skills

- Kind: optional external skill owner.
- Upstream: [EL4CTEO/blender-skills](https://github.com/EL4CTEO/blender-skills), MIT License, Copyright (c) 2026 EL4CTEO.
- Tested release: **v1.3.1**, revision `b1b21dfb73bc40b874ebf2aa12645931bfed3523`, with Blender 5.3.0 on Windows (2026-11-13). Upstream `validate_skills.py` passed and its 72 headless tests passed with Blender 5.3.0; AssetForge's full suite and its real-Blender runner tests (LODs, auto-retopo, UV pack, texel density, mesh stats) passed against it. v1.3.1 makes auto-retopo try voxel remesh first, adds a review grid to `review_shots.py` and warns about seams in `uv_pack.py`; the command lines AssetForge passes are unchanged. v1.3.0 (`3e481ad`) and v1.2.0 (`389f28a`) remain compatible.
- Detect: `BLENDER_SKILLS_ROOT`, project `integrations.blender_skills`, `~/blender-skills`, `~/.claude/skills`, `~/.agents/skills`, then a checkout under a declared tool root (same bounded search as comfy-kit). Both a checkout (`<root>/skills/<name>/SKILL.md`) and an installed folder (`<root>/<name>/SKILL.md`) are accepted. Required markers are `blender-core` and `blender-asset-qa`. A set variable that points at the wrong folder is reported, never bypassed.
- Version: the release number comes from upstream `.claude-plugin/plugin.json`; the per-skill metadata version, which can lag a release, is reported as `details.skill_version`.
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

A plain clone is enough for AssetForge. Put it in a declared tool root, or anywhere and set `BLENDER_SKILLS_ROOT`:

```bash
git clone --branch v1.3.1 https://github.com/EL4CTEO/blender-skills
```

To also load the skills into your agents, run the upstream installer; AssetForge does not duplicate it:

```bash
./blender-skills/install/install.sh          # macOS / Linux
.\blender-skills\install\install.ps1          # Windows
```

Update with `git -C blender-skills fetch --tags` and check out the new tag, then rerun `python tools/validate_skills.py` and `python tools/run_tests.py` in the checkout before relying on it.


## comfy-forge (formerly comfy-kit)

- Kind: external owner folder. It owns SwarmUI/ComfyUI, models, presets and its music generator.
- Detect: `COMFY_FORGE_ROOT` (or the older `COMFY_KIT_ROOT`), project `integrations.comfy_forge` (or `comfy_kit`), `~/comfy-forge`, `~/comfy-kit`, or a declared tool root. Required markers: `TOOLS/image-stack.ps1` and `presets/presets.json`. `providers.get("comfy-kit")` still answers with this provider.
- Used by: `comfy-generate` and `comfy-import` (images), and `audio-music` (songs, when `TOOLS/music.py` is present: comfy-forge 0.8.0 or later).
- Images delegate to the owner's `TOOLS/image-stack.ps1 generate` with output directed into the AssetForge asset. No model files, presets, nodes or SwarmUI configuration are modified.
- Music runs the owner's `TOOLS/music.py generate` (standard-library Python, run by AssetForge's interpreter) against a ComfyUI API, with output directed into the asset's `work/music/`. `backend=auto` (the default) uses a running ComfyUI (`COMFYUI_URL`, 8188, or SwarmUI's 7820-7832, the ports comfy-forge checks). When none answers, it asks comfy-forge for its interpreter (`image-stack.ps1 python`), starts that ComfyUI headless on a free local port, and stops it, process tree included, when the job ends. `backend=running` refuses to start one and exits 4; `backend=start` always starts its own.
- Tested 2026-11-14 with comfy-forge 0.8.0 and ComfyUI 0.44.0, `aio` variant on an RTX 4080 SUPER. A temporary backend was up in 18 s, and a 45 s instrumental took 2 takes in 98 s including startup. Through the running SwarmUI backend, a 40 s vocal song took 2 takes in 34 s.
- If the owner's default image model is unavailable, pass `--set model=<model-name>` or configure comfy-forge itself.

## img2threejs

- Kind: external skill checkout.
- Upstream: [img2threejs/img2threejs](https://github.com/img2threejs/img2threejs), Apache-2.0.
- Tested release: **v2.0.1**, revision `0c0c49bc168e648dbaf9c8c080474de0b3a941b6` (2026-11-13). Upstream suite: 1,416 tests, no assertion failures; 3 fixture errors were Windows symlink-privilege errors (`WinError 1314`) and 64 tests skipped. The probe (`forge/stage1_intake/probe_image.py IMAGE --out JSON`) and generator (`forge/stage3_build/generate_threejs_factory.py SPEC --out TS`) keep the command lines AssetForge uses.
- Detect: `IMG2THREEJS_ROOT`, project `integrations.img2threejs`, standard skill directories, or declared roots. Required markers: `SKILL.md` and `forge/stage1_intake/probe_image.py`. A pointer skill without `forge/` is not accepted. The version comes from the `version:` line of its `SKILL.md`. A set variable that points at the wrong folder is reported, never bypassed.
- Install: `git clone --branch v2.0.1 https://github.com/img2threejs/img2threejs` into a declared tool root, or set `IMG2THREEJS_ROOT`. Upstream's `npx img2threejs install` links the skill into every agent it finds; use it only if you want that.
- Used by: `img2threejs-probe` (technical image probe) and `img2threejs-codegen` (deterministic ObjectSculptSpec to Three.js TypeScript).
- Full reference-image reconstruction is an agent-driven upstream workflow and is **not** automated by AssetForge.

## teardown

- Kind: external skill checkout with its own npm dependencies.
- Upstream: [elvarofficial/teardown](https://github.com/elvarofficial/teardown), MIT. Built on claude-motion (MIT); its recorded samples are CC0.
- Tested revision: `a91262ac1109051e014662d42ecb0b7bc1f113b1` (package 1.0.0; upstream has no tagged release), Node 26, Playwright 1.58.2 with its Chromium 145 build, FFmpeg 9.0.2, on Windows (2026-11-13).
- Detect: `TEARDOWN_ROOT`, project `integrations.teardown`, `~/.claude/skills/teardown`, `~/.agents/skills/teardown`, or a checkout under a declared tool root. Required markers: `SKILL.md`, `paths.mjs` and `sims/build.mjs`. The checkout is available only after `npm install` (AssetForge checks `node_modules/esbuild` and `node_modules/three`); AssetForge never runs npm for it. A set variable that points at the wrong folder is reported, never bypassed.
- Install:

```bash
git clone https://github.com/elvarofficial/teardown
cd teardown
npm install
npx playwright install chromium
```

- If `npx playwright install chromium` downloads but never finishes extracting (seen twice with Playwright 1.58.2 on Node 26 on Windows), stop it, run `npx playwright install --dry-run chromium` for the folder and archive URL, extract the archive there with 7-Zip, and create empty `INSTALLATION_COMPLETE` and `DEPENDENCIES_VALIDATED` files in that folder. Do the same for `chromium-headless-shell`, which headless capture uses.
- Used by: `teardown-build` (`node sims/build.mjs <sim>` with `TEARDOWN_OUT` inside the asset) and `teardown-film` (`node sims/capture.mjs <entry> --out <file> ...`, with `FFMPEG` set to the FFmpeg AssetForge found). Every write lands in the asset; the checkout is only read.
- Evidence limits: a build proves the bundle, a film proves Chromium rendered the frames. Neither judges how the machine looks.

## Audio runtimes (`audio-speech`, `audio-sfx`, `audio-kokoro`)

- Kind: isolated Python environments that AssetForge builds and owns, one per dependency set. The model code and weights stay with their upstream projects.
- Install: `assetforge audio-setup` (all three) or `assetforge audio-setup speech|sfx|kokoro`. The command needs [uv](https://docs.astral.sh/uv/). It builds each runtime from the Python AssetForge runs on, installs PyTorch 2.9.1 from the PyTorch index (CUDA 12.8 when `nvidia-smi` works, CPU otherwise, or `--device`) and then the package set in `src/assetforge/data/audio/<runtime>.txt` (on Windows; elsewhere the top-level pins). After that it runs a smoke test. Running it again only changes what differs.
- Location: `~/.assetforge/audio` or `ASSETFORGE_AUDIO_HOME`, holding `envs/<runtime>` and the model cache `hf/`. It is not under `AppData`, because sandboxed hosts redirect writes there.
- Detect: a runtime is available only when its interpreter exists and its smoke-test marker (`assetforge-runtime.json`) was written. `doctor` reports torch, CUDA and the GPU.
- Runtimes, engines and models:

| Runtime | Engines | Models (licence) |
| --- | --- | --- |
| `speech` | `qwen3-tts`, `dia`, Whisper | Qwen3-TTS-12Hz-1.7B-VoiceDesign and -Base (Apache-2.0), Dia-1.6B-0626 (Apache-2.0), whisper-large-v3-turbo (MIT) |
| `sfx` | `moss-sfx`, CLAP | MOSS-SoundEffect-v2.0 (Apache-2.0), larger_clap_general (Apache-2.0) |
| `kokoro` | `kokoro` | Kokoro-82M (Apache-2.0) |

- Tested on 2026-11-13 on Windows 11 with Python 3.14.10, torch 2.9.1+cu128 and an RTX 4080 SUPER. Versions: qwen-tts 0.1.1, transformers 4.57.3 (speech), 4.57.1 (sfx) and 5.23.0 (kokoro); MOSS-TTS commit `934d6826b084c46a0d033402174d5f8ac4ed2519`; kokoro 0.9.4.
- How it runs: each job starts `<runtime python> -I audio_worker.py request.json` and reads back `result.json`. The worker loads each model once per job and writes only into the asset's `work/` folder. `ASSETFORGE_AUDIO_WORKER` swaps in another script that speaks the same protocol.
- Upstream quirks handled in the worker:
  - MOSS's `torch.compile` and CUDA-graph calls run eagerly on Python 3.14.
  - MOSS's DiT is stored in bf16.
  - MOSS's `seed` is passed through.
  - Whisper input is resampled to 16 kHz.
  - huggingface_hub's first-download symlink race on Windows is settled before any download.
  - Kokoro's spaCy model ships in the runtime, so it never installs itself into another Python.

## Godot

- Kind: external application, headless.
- Detect: `GODOT_EXE`, `GODOT`, `GODOT4`, `PATH` (`godot`, `godot4`), the winget package folder, `%LOCALAPPDATA%\Programs\Godot`, `%ProgramFiles%\Godot`, the Steam `Godot Engine` folder, and `godot*/Godot*.exe` under a declared tool root. On Windows the console build is preferred because it prints to the terminal.
- The probe runs `--version` and requires a version number in the output.
- Used by: `assetforge engine-check FILE.glb`. It writes a throwaway project to the temporary folder, copies the GLB in, runs `godot --headless --path PROJECT --import`, then a second headless run loads and instantiates the imported scene and prints the node classes it holds. The project is deleted afterwards.
- Evidence: import and load. Rendering, materials on screen, animation playback and physics are not tested and the report says so.
- Godot is MIT software and remains independently installed.

## FFmpeg

- Kind: command-line tool. Detect: `FFMPEG_EXE`, `FFMPEG`, `PATH`, the winget links and package folders, `%ProgramFiles%\ffmpeg\bin`.
- Used by: every `audio-*` recipe, `audio-music` included (trim, gain, resample, encode; `loudnorm`, `volumedetect` and `silencedetect` for the measurements; `ffprobe` for format facts) and `teardown-film` (video encoding).
- Also useful to an agent: a preview or turntable video from rendered frames.

## ImageMagick

- Kind: command-line tool. Detect: `MAGICK_EXE`, `MAGICK`, `PATH` (`magick`), `%ProgramFiles%\ImageMagick-*`.
- Used by: no recipe yet. Pillow handles the image recipes.
- What it is for: formats Pillow does not write (DDS, EXR), contact sheets with `magick montage`, and one-line batch conversion. The Windows `convert.exe` in System32 is a disk tool, not ImageMagick; only `magick` is accepted.

## Adding a provider

A provider needs:

- a unique id and title;
- capabilities and required dependencies;
- supported platforms;
- an availability result with a reason;
- structured argument-list execution with timeout and output verification;
- truthful `NOT_TESTED` when its real integration has not run.

Do not make the core import a provider's runtime dependencies.
