# State

- **Version:** 0.1.0
- **Milestone:** Phase 0 + Phase 1 MVP complete; Phase 2 image layer and img2threejs codegen complete; 0.1.0 release preparation complete
- **Active task:** awaiting operator confirmation to create/push `SenjuWoo/AssetForge`
- **Current revision:** `55a8f69de1ddcdcba4c718373e8f276d19bd1faf` (verified code commit)
- **Last known-good:** `55a8f69de1ddcdcba4c718373e8f276d19bd1faf`

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
- Release metadata, roadmap, release notes and publication checklist prepared for `0.1.0`.
- Clean install from committed source verified with and without optional providers.
- comfy-kit documented as the recommended free local texture-generation companion.

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

Commit this release-preparation checkpoint. Publication is blocked only on operator confirmation. Then follow `RELEASE.md`: create `SenjuWoo/AssetForge`, push `main`, wait for hosted CI on the exact commit, tag `v0.1.0` and publish the release. Do not claim publication before the repository, remote CI and release exist. After publication, the next engineering task is a genuine reference-image-to-3D-to-engine workflow (see `ROADMAP.md`), not more provider breadth.

## Integration status

- Ultimate AI Starter Bundle: proposal only; no bundle file modified.
- comfy-kit: recommended free local texture-generation companion; read-only delegation, verified generation and import; no owner files modified.
- img2threejs/teardown candidate checkouts: inspected and documented; not vendored, modified or deleted.
