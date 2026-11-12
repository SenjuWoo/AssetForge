# Changelog

## 0.3.0 — 2026-11-12

- Add `blender-optimize` and `blender-retopo-uv` recipes for whitelisted blender-skills operations on existing `.blend` files.
- Add the generic `blender.skills.run` step, restricted to documented operations: `mesh-stats`, `make-lods`, `auto-retopo`, `uv-pack` and `texel-density`. No arbitrary skill names, script paths or shell commands are accepted.
- Preserve immutable `.blend` inputs; mutating operations write new project-owned artifacts and record upstream reports in asset provenance.
- Add the project-generated `enchanted-fire-sword.glb` showcase fixture, reproducible Blender generator and low-poly preview render to `examples/`.
- Inspect the committed showcase GLB in the Windows/Linux CI smoke test.

## 0.2.0 — 2026-11-08

- Add optional `blender-skills` provider detection with `BLENDER_SKILLS_ROOT`, project integration config and standard skill directories.
- Add `assetforge blender-skills` catalog and route command for all 28 upstream skills.
- Detect Blender through `BLENDER_EXE`, PATH, Blender Foundation folders and the Steam install; continue past broken shims.
- Add `blender-pipeline`: procedural crate, upstream PBR material, mandatory `blender-asset-qa` gate, random/wire review sheets, upstream GLB export, glTF-Transform optimization and validation.
- Add `blender-qa` for gating an existing `.blend` with the same upstream QA and review evidence.
- Record tested blender-skills revision, QA numbers and review paths in asset provenance.
- Exclude QA preview images from exported texture packages.
- Document Hermes `skills.external_dirs` exposure for blender-skills.

## 0.1.0 — 2026-11-07

Initial standalone release candidate.

- Python CLI with stable exit codes and JSON output for doctor, capabilities, providers, jobs, assets, validation and export.
- Versioned contracts for assets, recipes, jobs, validation and export records.
- Project-local assets with copied inputs, provenance, relative artifact paths and path-escape rejection.
- Explicit primary deliverable, so export never depends on artifact order.
- Image inspection, resize, re-encode, alpha handling and thumbnails through Pillow.
- PBR channel packing: occlusion/roughness/metallic into one RGB ORM texture; mismatches require explicit resizing.
- Sprite atlas generation with project-owned frame copies, job provenance, and bounded output dimensions.
- Texture-only export packaging for generic, Godot and Roblox profiles.
- GLB inspection and structural validation using the standard library.
- Optional Khronos glTF Validator bridge with a clear `NOT_TESTED` result when absent.
- Conservative glTF-Transform optimization with structure comparison.
- Blender background adapter (implemented, unverified without Blender).
- comfy-kit generation and import adapters; generation is delegated and never installs models.
- img2threejs technical probe adapter; full reconstruction remains a planned agent workflow.
- img2threejs deterministic spec-to-Three.js code generation, preserving the editable TypeScript factory.
- Roblox, Godot and generic export packaging with configurable budgets and explicit `NOT_TESTED` engine-import status.
- Windows installer with staged environment and rollback; update and start scripts.
- Unit, contract, failure-path and end-to-end tests, including a textured multi-node GLB fixture.
- CI for Windows and Linux.
