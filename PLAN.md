# Plan

Status values are strict: **VERIFIED** (executed with evidence), **IMPLEMENTED / UNVERIFIED** (code exists, real integration not exercised), **PLANNED**, **BLOCKED**.

## Phase 0 — foundation

| ID | Task | Depends | Status | Verification | Evidence |
| --- | --- | --- | --- | --- | --- |
| F0-01 | Repository foundation, CLI, project/asset/job storage | — | VERIFIED | `python -m assetforge --version`, `doctor`, `recipes`, `init` | CLI/navigation tests; installer doctor |
| F0-02 | Versioned JSON schemas for asset, recipe, job, validation, export | F0-01 | VERIFIED | schema tests with `jsonschema` | `tests/test_schemas.py` |
| F0-03 | Test suite and CI definition | F0-01 | VERIFIED locally / CI not executed remotely | `python -m unittest discover -s tests`; `.github/workflows/ci.yml` | final suite result in `VALIDATION.md` |
| F0-04 | Windows installer/update/start scripts with staged rollback | F0-01 | VERIFIED | `Install.ps1`; `assetforge.cmd doctor` | `.venv` created, doctor exit `0` |
| F0-05 | README, licensing, architecture, provider, recipe docs | F0-01 | VERIFIED | document review; public-path test | `README.md`, `docs/`, `LICENSE` |

## Phase 1 — real MVP

| ID | Task | Depends | Status | Verification | Evidence |
| --- | --- | --- | --- | --- | --- |
| P1-01 | Image inspection, resize, re-encode, alpha, thumbnail | F0-01 | VERIFIED | `image-prep` unit and CLI tests | `tests/test_images.py`, `tests/test_cli.py` |
| P1-02 | GLB inspection and structural validation | F0-01 | VERIFIED | valid/corrupt/degenerate fixtures | `tests/test_glb.py` |
| P1-03 | Optional Khronos glTF validation | P1-02 | VERIFIED when installed | official report on fixtures | `GLB-014` official `PASS` |
| P1-04 | Conservative GLB optimization | P1-02 | VERIFIED | single-node and textured multi-node E2E | `tests/test_cli.py`; structure preserved |
| P1-05 | Roblox, Godot, generic export packaging | P1-04 | VERIFIED packaging / engine import NOT_TESTED | export records and hashes | `tests/test_exporters.py`, CLI E2E |
| P1-06 | Blender background adapter | F0-01 | VERIFIED | real Blender 5.2.3 smoke and upstream pipeline | `blender-sample` job `SUCCEEDED`; `blender-pipeline` 108 tris |
| P1-07 | img2threejs technical probe | F0-01 | VERIFIED probe / reconstruction PLANNED | real external probe run | `img2threejs-probe` job `SUCCEEDED` |
| P1-08 | comfy-kit generation and import | F0-01 | VERIFIED | real generation and import | `comfy-generate` and `comfy-import` jobs `SUCCEEDED` |
| P1-09 | Bundle companion proposal | F0-05 | VERIFIED documentation / not applied | fragment + contract review | `integration/COMPANIONS.asset-forge.json` |
| P1-10 | Examples and standalone smoke | P1-01, P1-02 | VERIFIED | fresh project outside repo | `examples/`, `VALIDATION.md` |

## Review corrections

| ID | Finding | Status | Verification |
| --- | --- | --- | --- |
| R-01 | Jobs must finalize on adapter, GLB, storage, subprocess and unexpected errors | VERIFIED | failure-path tests in `tests/test_runner.py`; real comfy-kit model failure recorded as `FAILED` |
| R-02 | Execute against project-owned input copies; retain originals as provenance only | VERIFIED | copied-input test; `Context` refuses an unowned file |
| R-03 | Export must use an explicit primary artifact, not artifact order | VERIFIED | reversed-order primary test |
| R-04 | Reject absolute, `../`, missing and symlink artifact paths | VERIFIED | `tests/test_exporters.py`; symlink test skipped on Windows without symlink privilege |
| R-05 | Representative GLB with multiple nodes, materials and a texture | VERIFIED | `make_textured_glb`; optimization preserves counts |
| R-06 | Do not modify the bundle or comfy-kit; do not delete the candidate checkouts | VERIFIED | only documentation and external read-only execution |
| R-07 | Input-copy/setup failures must not leave orphaned assets or `RUNNING` jobs | VERIFIED | job is created before copying; copy failure marks job and asset `FAILED`; focused test |
| R-08 | Sprite atlas must not truncate frames; copy sources, record hashes, bound resources | VERIFIED | 65-frame rejection test; frame copies and job provenance asserted; side/pixel/padding/column limits tested |
| R-09 | Export image-only assets without a GLB | VERIFIED | Generic, Godot and Roblox texture packages; no engine import claimed |
| R-10 | ORM mismatch must be explicit, with channel/color guidance | VERIFIED | mismatch fails with `resize=true` guidance; opt-in resize warns; docs state linear-data mapping |

## Phase 2+ — planned

| ID | Task | Status |
| --- | --- | --- |
| P2-01 | Material Maker / PBR material interchange | PLANNED |
| P2-02 | Krita/Inkscape manual-editor workflows | PLANNED |
| P2-03 | Sprite sheets and texture atlases | VERIFIED (image pipeline; editor integration pending) |
| P2-04 | ORM material channel packing | VERIFIED |
| P2-05 | img2threejs deterministic spec-to-Three.js codegen | VERIFIED |
| P2-06 | blender-skills provider, catalog and routing | VERIFIED |
| P2-07 | Blender pipeline with mandatory QA gate and review evidence | VERIFIED |
| P2-08 | Imported `.blend` QA recipe | VERIFIED |
| P3-01 | TripoSR image-to-3D provider, isolated environment | PLANNED |
| P3-02 | Rigging validation interfaces and UniRig adapter | PLANNED |
| P3-03 | teardown simulation/presentation module | VERIFIED (0.6.0: `teardown-build`, `teardown-film`) |
| P4-01 | Additional export profiles (Unity, Unreal, web, Skyrim) | PLANNED |
| P4-02 | MCP server over the same service layer | PLANNED |
| P4-03 | Remote GPU execution | PLANNED |

## Next executable task

The standalone `v0.1.0` release is published and the Blender integration is local and verified. Before the next release, run the full CI on the exact integration commit and publish only after it passes. The next engineering priority is the reference-image-to-3D-to-engine workflow in `ROADMAP.md`, not another provider.
