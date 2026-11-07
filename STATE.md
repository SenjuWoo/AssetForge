# State

- **Version:** 0.1.0
- **Milestone:** Phase 0 + Phase 1 MVP complete; Phase 2 image layer and img2threejs codegen complete
- **Active task:** none — repository is at a verified checkpoint
- **Current revision:** `3f095db38bf03ca9ffe70f6ab16dc99edaabcc3d` (verified code commit)
- **Last known-good:** `3f095db38bf03ca9ffe70f6ab16dc99edaabcc3d`

## Completed

- Standalone CLI: `doctor`, `capabilities`, `providers`, `init`, `recipes`, `run`, `status`, `inspect`, `validate`, `export`.
- Project/asset/job contracts with versioned JSON schemas.
- Inputs copied into the project; original locations kept only in job provenance.
- Relative artifact paths; absolute, `../`, missing and symlink escapes rejected.
- Explicit primary artifact selection for export.
- Job finalization on `AdapterError`, `GlbError`, `StoreError`, `OSError` and unexpected exceptions.
- Pillow image pipeline; GLB inspection and structural validation; optional Khronos validation.
- PBR channel packing (occlusion/roughness/metallic to RGB ORM) with explicit resize consent.
- Deterministic sprite atlases with project-owned frame copies, job provenance and bounded output size.
- Texture-only export packages for generic, Godot and Roblox profiles.
- img2threejs deterministic spec-to-Three.js codegen through the upstream generator; reconstruction remains agent-driven.
- Conservative glTF-Transform optimization with before/after comparison.
- Roblox/Godot/generic export packaging with engine import marked `NOT_TESTED`.
- External adapters: Blender (implemented, unavailable), comfy-kit generate/import (verified), img2threejs probe and codegen (verified).
- Windows installer, updater, start script, local launcher; CI definition; examples; documentation.

## Outstanding defects

None known. Open limits are evidence gaps, not known code defects:

- Blender is not installed here; the `blender` command on PATH launches Hermes, so the provider correctly reports unavailable.
- Engine imports (Roblox Studio, Godot editor) were not executed.
- The symlink-escape regression test is skipped on Windows without symlink privilege; it runs on Linux CI.
- comfy-kit's built-in default model was rejected by the running SwarmUI; a valid `--set model=...` produced a successful render. The adapter reports the owner error correctly.

## Exact commands

```text
python -m unittest discover -s tests -v
python -m assetforge doctor --json
python -m assetforge recipes list
python -m assetforge run glb-optimize --input examples/assets/textured-scene.glb
python -m assetforge run texture-pack --input occlusion=ao.png --input roughness=rough.png --input metallic=metal.png
python -m assetforge run sprite-atlas --input path/to/frames --set columns=4
```

Installer:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File Install.ps1
assetforge.cmd doctor
```

## Next action

Commit this verified checkpoint. Next engineering task: verify Blender against a real installation, then add the optional Teardown build adapter and Graphite interchange note. Do not publish or add providers until the operator asks. When publication is authorized: create `SenjuWoo/AssetForge`, push `main`, confirm CI on the exact commit, then publish a release archive containing `Install.ps1`, `Update.ps1`, `VERSION`, `src/`, `pyproject.toml`, docs and `LICENSE`.

## Integration status

- Ultimate AI Starter Bundle: proposal only; no bundle file modified.
- comfy-kit: read-only delegation, verified generation and import; no owner files modified.
- img2threejs/teardown candidate checkouts: inspected and documented; not vendored, modified or deleted.
