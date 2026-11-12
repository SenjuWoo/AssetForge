# State

- **Version:** 0.2.0
- **Milestone:** Phase 0 + Phase 1 MVP complete; Phase 2 image layer and img2threejs codegen complete; 0.1.0 and 0.2.0 published; blender-skills runner for optimization and retopo/UV verified locally
- **Active task:** choose the next milestone; `main` contains unreleased skill-runner changes and no new release has been cut
- **Current revision:** `71b6903e1193a220ec23420a0bab0ed0ed2f1be9` (`Add whitelisted Blender skill runner`)
- **Last known-good:** `71b6903e1193a220ec23420a0bab0ed0ed2f1be9` (main; CI `43169849382` passed 7/7)

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
- External adapters: Blender headless export (verified), blender-skills catalog/QA/export (verified), comfy-kit generate/import (verified), img2threejs probe and codegen (verified).
- blender-skills 28-skill catalog, route CLI and Hermes external-dir documentation; tested upstream revision `389f28a`.
- `blender-pipeline` and `blender-qa`; mandatory upstream QA gate with numeric and random/wire review evidence.
- Whitelisted `blender-optimize` (`mesh-stats`, `make-lods`) and `blender-retopo-uv` (`auto-retopo`, `uv-pack`, `texel-density`); immutable input `.blend`, new project-owned outputs and upstream reports in provenance.
- Windows installer, updater, start script, local launcher; CI definition; examples; documentation.
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

Choose whether to cut `0.3.0` or continue the post-release milestone first. Do not publish a release until the user asks. CI `43169849382` passed 7/7 for `71b6903e1193a220ec23420a0bab0ed0ed2f1be9`; security check found 0 Dependabot and 0 secret-scanning alerts, with code-scanning unavailable (`no analysis found`).

## Integration status

- Ultimate AI Starter Bundle: proposal only; no bundle file modified.
- comfy-kit: recommended free local texture-generation companion; read-only delegation, verified generation and import; no owner files modified.
- blender-skills: recommended optional Blender skills provider; read-only catalog and delegation; tested revision `389f28a`; optimization/retopo/UV runner verified on the current Blender 5.3.0 installation; no upstream files modified.
- img2threejs/teardown candidate checkouts: inspected and documented; not vendored, modified or deleted.
