# Plan

## 0.9.0 - cover what a text-and-code agent cannot make (2026-11-17)

Goal: an agent that can only write text and code gets every 2D asset it needs from AssetForge:
textures (through comfy-forge), PBR map sets, cut-out sprites, pixel art, sprite sheets, and
sprites rendered from a 3D model at the game's camera. Status: `pending` / `complete` / `blocked`.
A task is `complete` only when its Verify passed; Evidence records `cmd @ sha exit=n`.

| ID | Task | Status | Depends on | Verify | Evidence |
| --- | --- | --- | --- | --- | --- |
| T1 | `texture.py`: seamless tiling (`make_tileable`), seam metric (`TEX-SEAM`) | complete | - | cmd:python -m unittest discover -s tests -p "test_texture.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T2 | `texture.py`: PBR set from a colour map (height, normal, roughness, AO, metallic, ORM, material.json) | complete | T1 | cmd:python -m unittest discover -s tests -p "test_texture.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T3 | `sprites.py`: cut-out (background key + border flood fill, feather, decontaminate, trim, anchor) | complete | - | cmd:python -m unittest discover -s tests -p "test_sprites.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T4 | `sprites.py`: pixel art (downscale, fixed palettes or `.hex`, dither, preview) | complete | T3 | cmd:python -m unittest discover -s tests -p "test_sprites.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T5 | `sprites.py`: sheet slicing (grid and alpha islands) | complete | T3 | cmd:python -m unittest discover -s tests -p "test_sprites.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T6 | `sprite-render`: Blender renders a GLB in N facings at a camera pitch, per animation, with anchor and sheet | complete | - | cmd:python -m unittest discover -s tests -p "test_sprite_render.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T7 | comfy-forge images: `steps`/`cfg` pass-through, SwarmUI started for the job when none runs, messages say comfy-forge | complete | - | cmd:python -m unittest discover -s tests -p "test_*.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T8 | Recipes `texture-tileable`, `texture-pbr`, `texture-generate`, `image-cutout`, `sprite-generate`, `pixel-art`, `sprite-slice`, `sprite-render`; runner handlers, STEP_PROVIDERS, schema | complete | T1-T7 | cmd:python -m unittest discover -s tests -p "test_*.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T9 | Export: sidecar data (atlas.json, sprites.json, material.json) ships, stale files cleared, name collisions refused | complete | T8 | cmd:python -m unittest discover -s tests -p "test_exporters.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T10 | Bugs found in the read: image size bounds, atlas frame cap, `name=path` input message (exit 2), probe routes for the new recipes | complete | T8 | cmd:python -m unittest discover -s tests -p "test_*.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T11 | DDS and TGA output for `image-prep` (ImageMagick writes DDS) | complete | T10 | cmd:python -m unittest discover -s tests -p "test_images.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T12 | Real runs: texture-generate through SwarmUI, texture-pbr, sprite-render on the showcase sword, sprite-generate | complete | T8 | file:VALIDATION.md | file:VALIDATION.md (0.9.0 section) @ 809fa8d |
| T13 | Docs (README, AGENTS, RECIPES, TEXTURES-SPRITES, UPSTREAM-EVALUATIONS, ROADMAP), version 0.9.0, changelog, STATE | complete | T12 | cmd:python -m unittest discover -s tests | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped); docs and CHANGELOG in the commit |
| T15 | Field report: `mesh-gameready` output fails GLB-014 (zero tangents after the collapse); `repair_unit_vectors` | complete | - | cmd:python -m unittest discover -s tests -p "test_glb_repair.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T16 | `comfy-3d` recipe over comfy-forge 0.11.0 `model3d.py`; optional `generate` flags probed from its `param()` block | complete | T8 | cmd:python -m unittest discover -s tests -p "test_comfy_forge.py" | cmd:python -m unittest discover -s tests @ 809fa8d exit=0 (365 OK, 2 skipped) |
| T14 | Push, CI green on the exact SHA, alerts checked, release asset verified, installed, doctor | complete | T13 | cmd:gh run list --commit <sha> | cmd:gh run view 44202681239 @ 809fa8d exit=0 (7/7 jobs success); release v0.9.0 asset SHA-256 b471245e…efa9 re-downloaded and matched; zip install doctor exit=0; 0 Dependabot / 0 secret-scanning alerts |

### Decisions

- **spritecast is not a provider.** Its drawing step is the OpenAI Images API and its characters need Tripo or Meshy keys; it is a Claude Code plugin, not a CLI contract. The idea worth having is the 3D guide rendered at the game's exact camera. `sprite-render` does that natively with Blender, and any redraw goes through comfy-forge.
- **Pillow only, no numpy.** `ImageChops.offset` wraps, so tiling-correct derivatives and seam checks need no array library. Core keeps zero hard dependencies.
- **Derived PBR maps are labelled as derived.** Height, normal, roughness and AO computed from a colour map are approximations; `TEX-DERIVED` is `NOT_TESTED` until someone looks.
- **comfy-forge keeps generation.** AssetForge calls `image-stack.ps1 generate`; it may start comfy-forge's SwarmUI for one job (as it already does with ComfyUI for music) and stops it afterwards. Flags comfy-forge does not expose (negative prompt, init image, tiling) are filed as a field report there, not patched from here.
- **Image to 3D stays in comfy-forge.** Its Pixal3D templates have no CLI; a UI-graph converter here would duplicate its ownership. Field report filed; `mesh-gameready` remains the hand-off.
- **Sidecar role `data`.** Files an engine needs beside a texture (frame rectangles, anchors, material maps) are artifacts with role `data` and are exported; reports stay evidence.

### Assumptions

- Blender 5.3 renders Workbench with a transparent film in background mode on this machine (checked by T6).
- SwarmUI accepts `--port` and `--launch_mode none` (checked by T12 before T7 is called complete).

### Risks

- SwarmUI start time and first model load can exceed a short timeout: default 900 s, raised by the caller.
- glTF animations import as NLA tracks; a file with unusual action layout renders its rest pose and says so (`SPRITE-ANIM` WARNING).

## History

Status values in the tables below are the older scheme: **VERIFIED** (executed with evidence), **IMPLEMENTED / UNVERIFIED** (code exists, real integration not exercised), **PLANNED**, **BLOCKED**.

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
| P3-04 | Audio: voice lines, sound effects, finishing, sound export | VERIFIED (0.7.0: `audio-voice`, `audio-sfx`, `audio-process`, `audio-setup`, `minecraft` target) |
| P3-05 | Music generation | VERIFIED (0.8.0: `audio-music` through comfy-forge, temporary or running ComfyUI) |
| P4-01 | Additional export profiles (Unity, Unreal, web, Skyrim) | PLANNED |
| P4-02 | MCP server over the same service layer | PLANNED |
| P4-03 | Remote GPU execution | PLANNED |

## Next executable task

Releases through `v0.8.2` are published from green commits. Before the next release, run the full local suite with real providers and hosted CI on the exact commit, and publish only after both pass. The next engineering priority is the reference-image-to-3D-to-engine workflow in `ROADMAP.md`, not another provider.
