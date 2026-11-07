# Changelog

## 0.1.0 — 2026-11-07

Initial standalone release candidate.

- Python CLI with stable exit codes and JSON output for doctor, capabilities, providers, jobs, assets, validation and export.
- Versioned contracts for assets, recipes, jobs, validation and export records.
- Project-local assets with copied inputs, provenance, relative artifact paths and path-escape rejection.
- Explicit primary deliverable, so export never depends on artifact order.
- Image inspection, resize, re-encode, alpha handling and thumbnails through Pillow.
- PBR channel packing: occlusion/roughness/metallic into one RGB ORM texture.
- Sprite atlas generation with a deterministic grid and JSON frame metadata.
- GLB inspection and structural validation using the standard library.
- Optional Khronos glTF Validator bridge with a clear `NOT_TESTED` result when absent.
- Conservative glTF-Transform optimization with structure comparison.
- Blender background adapter (implemented, unverified without Blender).
- comfy-kit generation and import adapters; generation is delegated and never installs models.
- img2threejs technical probe adapter; full reconstruction remains a planned agent workflow.
- Roblox, Godot and generic export packaging with configurable budgets and explicit `NOT_TESTED` engine-import status.
- Windows installer with staged environment and rollback; update and start scripts.
- Unit, contract, failure-path and end-to-end tests, including a textured multi-node GLB fixture.
- CI for Windows and Linux.
