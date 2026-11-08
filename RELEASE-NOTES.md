# AssetForge 0.2.0 — Blender-skills integration (development preview)

Second development release. Adds an optional, verified headless Blender asset pipeline built around the upstream [blender-skills](https://github.com/EL4CTEO/blender-skills) skill pack.

## Included

- Optional blender-skills detection through `BLENDER_SKILLS_ROOT`, project configuration and standard agent skill folders.
- `assetforge blender-skills` capability catalog and routing for 28 upstream skills.
- `blender-pipeline`: procedural Blender build, material assignment, upstream `blender-asset-qa`, GLB export, optimization and Khronos validation.
- `blender-qa`: standalone QA gate for an existing `.blend` file.
- QA enforcement: upstream errors fail the step; warnings require an explicit `warning_note`; visual approval requires `visual_review=approved` and `approval_note`.
- Immutable build/material `.blend` stages, project-relative review evidence and artifact hashes recorded in `asset.json`.
- Mesh and texture-only packaging for generic, Godot and Roblox profiles. Engine import remains `NOT_TESTED`.
- All 0.1.0 image, GLB, comfy-kit, img2threejs and export functionality remains available.

## Verified

- Full suite: 91 tests, 89 passed, 2 skipped, 0 failed.
- Real Blender 5.2.3 LTS: procedural crate, 108 triangles, QA clean with 0 errors and 0 warnings, GLB exported and optimized, Khronos validation `PASS`.
- 0.2.0 wheel installed into a clean environment and exercised end-to-end.
- The `v0.1.0` release remains unchanged.

## Boundaries

- Only 4 of the 28 cataloged blender-skills were exercised end-to-end.
- Blender integration tests are skipped in hosted CI because CI has no Blender installation.
- Visual QA is explicitly approval-gated, not automatic.
- Roblox Studio and Godot imports were not run; exports are verified packages only.
- img2threejs reconstruction, Teardown, Graphite, AI 3D generation, rigging and MCP remain unimplemented or unverified.

## Requirements

- Python 3.10 or newer; CI covers Python 3.12–3.14.
- Pillow is optional but recommended for image recipes.
- Blender and blender-skills are optional and independently installed.
- All external tools and model weights are optional.
