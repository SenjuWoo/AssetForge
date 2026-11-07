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

- Kind: Node package plus the `tools/validate_glb.mjs` bridge.
- Detect: `node` plus `.tools/node_modules/gltf-validator/index.js`.
- Local developer setup:

```bash
npm install --prefix .tools gltf-validator
```

When absent, validation reports `GLB-014 NOT_TESTED`; when present, the official report is recorded alongside AssetForge's structural checks.

## Blender

- Kind: external application, background mode.
- Detect: `BLENDER`, `PATH`, or a standard Blender Foundation install folder.
- The probe runs `--version` and requires a `Blender x.y` version string. A shim that starts some other program is reported as unavailable rather than accepted.
- Used by: `blender-sample`.
- Blender is GPL software and remains independently installed and maintained.

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
