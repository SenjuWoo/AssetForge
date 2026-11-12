# State

- **Version:** 0.3.1
- **Milestone:** 0.3.1: `mesh-gameready` hard triangle cap
- **Active task:** publish 0.3.1 from the green main commit
- **Current revision:** 0.3.1 on main, ahead of the published `v0.3.0`
- **Last known-good:** `9027141dc5680a29ed4d7d4745bc551a04647e72` (`main`; CI `43170035309` passed 7/7)

## Completed

- `mesh-gameready` (0.3.1, local): default budget `game` fails a written GLB over 20,000 triangles. `hero` is 30,000. `accessory` is 4,000. A 700,000-triangle count is rejected. Guide: `docs/GAME-READY.md`. On 2026-11-12 a 699,878-triangle PBR GLB wrote 17,000 triangles, 21,186 vertices, 6,192,808 bytes, and three 1024 PNGs. Official glTF validator: 0 errors, 0 warnings. Engine import was not run.
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
- External adapters: Blender headless export (verified), blender-skills catalog/QA/export (verified), comfy-kit generate/import (verified), img2threejs probe and codegen (verified).
- blender-skills 28-skill catalog, route CLI and Hermes external-dir documentation; tested upstream revision `389f28a`.
- `blender-pipeline` and `blender-qa`; mandatory upstream QA gate with numeric and random/wire review evidence.
- Whitelisted `blender-optimize` (`mesh-stats`, `make-lods`) and `blender-retopo-uv` (`auto-retopo`, `uv-pack`, `texel-density`); immutable input `.blend`, new project-owned outputs and upstream reports in provenance.
- Windows installer, updater, start script, local launcher; CI definition; examples; documentation.
- Project-owned `enchanted-fire-sword.glb` showcase: artisan-style low-poly GLB, preview PNG, reproducible generator, local GLB validation and third-party-free fixture.

- Release metadata, roadmap, release notes and publication checklist prepared for `0.1.0`.
- Clean install from committed source verified with and without optional providers.
- comfy-kit documented as the recommended free local texture-generation companion.

## Outstanding defects

None known. Open limits are evidence gaps, not known code defects:

- Engine imports (Roblox Studio, Godot editor) were not executed.
- The symlink-escape regression test is skipped on Windows without symlink privilege; it runs on Linux CI.
- comfy-kit's built-in default model was rejected by the running SwarmUI; a valid `--set model=...` produced a successful render. The adapter reports the owner error correctly.
- blender-skills is optional; a machine without Blender or the skills still gets clean exit `4` and no changed core behavior.
- QA review sheets were inspected by the agent; no formal human art review was recorded.

## Exact commands

```text
python -m unittest discover -s tests -v
python -m unittest test_blender_skill_runner -v
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

Tag `v0.3.1` on the green main SHA and publish `AssetForge-0.3.1.zip`. Guide: `docs/GAME-READY.md`.

## Integration status

- Ultimate AI Starter Bundle: proposal only; no bundle file modified.
- comfy-kit: recommended free local texture-generation companion; read-only delegation, verified generation and import; no owner files modified.
- blender-skills: recommended optional Blender skills provider; read-only catalog and delegation; tested revision `389f28a`; optimization/retopo/UV runner verified on the current Blender 5.3.0 installation; no upstream files modified.
- img2threejs/teardown candidate checkouts: inspected and documented; not vendored, modified or deleted.
