# AssetForge 0.1.0 — standalone asset toolkit (development release)

First standalone development release.

## Included

- Python CLI with stable exit codes, JSON output and project/job manifests.
- Project-owned inputs, relative artifact paths, path-escape rejection and explicit primary artifacts.
- Image inspection, resize/re-encode, thumbnails, PBR ORM packing and bounded sprite atlases.
- GLB inspection, structural validation, optional Khronos validation and conservative glTF-Transform optimization.
- Mesh and texture-only packaging for generic, Godot and Roblox profiles. Engine import remains `NOT_TESTED`.
- Optional adapters for comfy-kit texture generation, img2threejs probe/codegen and Blender.
- Windows installer with staged rollback, updater and local launchers.
- Tests, schema contracts and Windows/Linux CI.

## Verified boundaries

- img2threejs TypeScript generation is verified. Compilation, rendering, visual fidelity and game-ready conversion are not.
- Blender execution, Teardown, Graphite, AI 3D generation, rigging, MCP and real engine import are not verified.
- comfy-kit generation is verified against a running installation; model installation and ownership stay with comfy-kit.

## Requirements

- Python 3.10 or newer; the CI matrix covers Python 3.12–3.14.
- Pillow is optional but recommended for image recipes.
- All external tools and model weights are optional and independently installed.
