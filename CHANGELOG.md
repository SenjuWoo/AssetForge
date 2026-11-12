# Changelog

## 0.4.0 — 2026-11-12

- Add `assetforge probe PATH`: inspect a file or a folder before any project exists. It reports the facts that decide a pipeline (triangles, vertices, texture sizes, rig, animations, how the mesh sits against each export budget) and prints the exact recipe commands that fit. It writes nothing.
- Add `mesh-convert`: FBX, OBJ, STL, PLY, glTF, USD, Alembic and `.blend` become one validated GLB through Blender. Rigs, skin weights and animations are kept. The importer is looked up in the installed Blender at run time, so a format a build cannot read fails with that importer's message.
- Rig and animation validation (`GLB-013`) is now a real check instead of a notice: joint lists, inverse bind matrices, skinned primitives without weights, weights that name a joint past the skin, weights that do not sum to 1, animation channels that name a missing node or sampler, and key/value count mismatches. A rig that passes is consistent data; the deformation is still not rendered.
- Add `GLB-015` (materials, textures and images resolve; a textured surface has the UV set its material asks for) and `GLB-016` (non-finite, zero-scale and mirrored node transforms).
- Texture budgets now apply to textures embedded in a GLB. Their size is read from the PNG, JPEG, WebP or KTX2 header; before this an export reported the check as not tested and an oversized embedded texture passed.
- `inspect` and comparison reports carry per-image sizes, the largest texture, UV set count, vertex colours, morph targets, joint counts, animation names and duration.
- Export profiles may set a `joints` budget.
- `mesh-gameready` now reports a warning when the source had animations, because the collapse does not carry them over.
- Assets are named after their input file (`crate-mesh-convert-...`) instead of the recipe alone.
- Fix: a provider launched through a `.cmd` or `.bat` file failed when its path or an argument contained a space, and a `!` in the path could be eaten by delayed expansion.
- Add `AGENTS.md`: the short runbook for an agent that has never seen the repository.

## 0.3.1 — 2026-11-12

- Add `mesh-gameready`: import a GLB in Blender, collapse it under a hard triangle cap, shrink textures, then validate and compare. The written file is deleted if it is over the cap.
- Default budget `game` is 20,000 triangles and a 1024 texture. That is the Roblox MeshPart ceiling and the handheld-prop ceiling used here. `hero` is 30,000 / 2048 and is not a Roblox mesh. `accessory` is 4,000 / 1024 for a worn Roblox accessory.
- A 700,000-triangle sculpt does not pass. An explicit triangle override above the budget is rejected. There is no 50,000 `pc` budget on this recipe.
- Measured once: a 699,878-triangle PBR GLB (61.5 MB) collapsed to 17,000 triangles, 21,186 vertices, and 6.2 MB, with three textures brought down to 1024. The official glTF validator reported 0 errors and 0 warnings. Engine import was not run.
- `glb-optimize` is unchanged: it still does not simplify. Game-ready reduction is the new recipe, not a silent change to the conservative pass.
- blender-skills operations still require a `.blend`. They are not a second GLB importer.

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
