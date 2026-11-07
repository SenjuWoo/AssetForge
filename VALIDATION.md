# Validation evidence

Verified code commit: `55a8f69de1ddcdcba4c718373e8f276d19bd1faf`.

Environment: Windows 11, Python 3.14.10, Node 26.13.0, Pillow 13.0.0, jsonschema 4.x, glTF-Transform 4.5.1, Khronos glTF Validator installed locally in `.tools`. The project works without any optional provider.

## Test suite

Command:

```text
python -m unittest discover -s tests
```

Result (final run after the review corrections):

```text
Ran 75 tests in 92.519s
OK (skipped=1)
exit code 0
```

The skipped test is `test_symlink_escape_is_rejected`: this Windows account does not hold the symlink-creation privilege. The test runs on Linux CI.

Coverage includes:

- GLB header, length, accessor bounds, degenerate triangles, missing normals, scale bounds, unresolved images.
- Textured multi-node fixture: 2 nodes, 2 meshes, 2 materials, 1 embedded texture, 2 triangles.
- Image inspection, resize, WebP conversion, alpha handling, JPEG flatten warning, comparison.
- PBR channel packing with per-channel pixel verification; atlas grid, frame metadata and alpha handling.
- Atlas 65-frame rejection, copied frame provenance, negative padding/zero columns, side and pixel limit rejection.
- Texture-only export for generic, Godot and Roblox packages, including JSON export records and import notes.
- ORM mismatch rejection and explicit resize warning.
- img2threejs codegen adapter contract; real upstream generator produced a 64,589-byte TypeScript factory from the upstream conformance fixture.
- Project/asset/job storage, schema validation and asset lookup.
- Recipe loading, unknown-step rejection, project overrides and typed parameters.
- CLI end-to-end: init, recipes, image-prep, glb-inspect, validate, export, status, dry run, exit codes.
- Job failure paths: `GlbError`, `AdapterError`, `StoreError`, `OSError`, unexpected exception; every case ends `FAILED`.
- Input-copy failure after job creation marks both job and asset `FAILED`, with no orphan left `RUNNING`.
- Input copying and provenance: artifacts relative, originals only in job `sources`.
- Export primary selection with source and optimized artifacts in reversed manifest order.
- Export blocked when any validation check fails, even if the primary mesh itself is valid.
- Artifact rejection: absolute path, `../` escape, missing file and symlink escape.
- Official validator separated from structural `GLB-014`.

## Official validator

The Khronos validator reported `0 error(s), 0 warning(s)` for the single-triangle fixture, the optimized fixture and the textured multi-node fixture. Structural checks remain independently reported; when the validator is absent, `GLB-014` is `NOT_TESTED`.

## glTF-Transform end-to-end

Command:

```text
assetforge run glb-optimize --input examples/assets/textured-scene.glb --json
```

Observed: job `SUCCEEDED`; source and optimized both 2 nodes, 2 meshes, 2 materials, 1 image, 1 texture, 2 triangles; comparison record written; validation `PASS=12, FAIL=0`; export hash matched the optimized primary.

## Export

```text
assetforge export <asset> --target godot
assetforge export <asset> --target roblox
assetforge export <asset> --target generic
```

Observed: export folders, `export.json`, `IMPORT.md`, file hashes and manifest export records. Every record contains `engine_import: NOT_TESTED`. No Roblox Studio or Godot editor was launched.

## Real external integrations

### comfy-kit generation

- First attempt used comfy-kit's default model. SwarmUI refused it: invalid model. AssetForge recorded the job as `FAILED` with the owner's message, returned exit code `6`, and did not leave the job in `RUNNING`.
- Second attempt used an explicit valid model (`--set model=Anima/Anime/Anima-2.9B-preview-v1.safetensors`), 512×512, seed 42. Job `SUCCEEDED`, one PNG (523,297 bytes) written inside the asset, and the job record preserved provider version and output.
- No comfy-kit, preset, model, node or SwarmUI configuration file was modified.

### comfy-kit import

Command:

```text
assetforge run comfy-import --input <generated-output-folder>
```

Observed: job `SUCCEEDED`; one image copied into a new asset, thumbnail written, primary image set.

### img2threejs probe

Command:

```text
assetforge run img2threejs-probe --input <reference.png>
```

Observed: job `SUCCEEDED`; upstream probe JSON stored as a report; result `technicalSuitability=conditional`. This is a technical probe, not 3D reconstruction.

## Installer and packaging

- `Install.ps1` created a repo-local `.venv`, ran `doctor`, exited `0`.
- `assetforge.cmd --version` printed `assetforge 0.1.0`; `doctor --json` exited `0`.
- Wheel build: `assetforge-0.1.0-py3-none-any.whl`, 48,579 bytes, SHA-256 `b2dc930a415c2a28cf6715ead543bd1b305cd24ec025832077a45fed3e8bbc48`.
- Wheel installed into a clean environment; `assetforge --version` returned 0.1.0; `texture-pack`, `sprite-atlas` and `img2threejs-codegen` returned job status `SUCCEEDED`; the packaged bridge passed the Khronos validator with `0 error(s), 0 warning(s)` in a project path containing spaces.
- Wheel installed into a clean environment; `assetforge --version` returned 0.1.0, `glb-inspect` ran against the textured fixture, `validate` returned `PASS` with `PASS=11, FAIL=0, NOT_TESTED=2` (official validator unavailable in that isolated environment, plus no rig data).
- Packaged validator bridge verified from that installed wheel in a project path containing spaces:
  - before installing the validator into the project's `.tools`, `GLB-014` was `NOT_TESTED`;
  - after installing `gltf-validator`, the installed bridge was detected and `GLB-014` returned `PASS` with `0 error(s), 0 warning(s)`;
  - the bridge path itself contained spaces and was invoked by argument list, not shell interpolation.

## Clean install from committed source

A fresh clone of the committed source was installed into a new virtual environment with `pip install ".[images]"`.

- `assetforge --version` → `assetforge 0.1.0`; recipe discovery listed all built-in recipes.
- `doctor --json` exited `0` (`DEGRADED` only because the clone root had no project).
- `image-prep` from `examples/assets/source.png` → `SUCCEEDED`.
- `texture-pack` → `SUCCEEDED`; `export` to generic, Godot and Roblox → `PASS`, `kind=texture`, `engine_import=NOT_TESTED`.
- `glb-inspect` → `SUCCEEDED`; `validate` with no validator → `GLB-014=NOT_TESTED`.
- `glb-optimize` without the Node package → exit `4`; `blender-sample` without real Blender → exit `4`.
- After linking project-local `.tools`, `gltf-transform` and `gltf-validator` were detected: `glb-optimize` → `SUCCEEDED`, official `GLB-014` → `PASS` with 0 errors and 0 warnings.
- `Install.ps1` and `Install.ps1 -WithImages` both completed; `assetforge.cmd --version` printed 0.1.0.

## Not verified

| Item | Why |
| --- | --- |
| Blender background export | Blender is not installed here. The detected `blender` command launches Hermes, so the provider correctly reports no Blender version. |
| Roblox Studio import | No Studio session was run. File-format support is documented; runtime/visual compatibility is `NOT_TESTED`. |
| Godot import | No editor session was run. |
| img2threejs image-to-spec reconstruction | Upstream workflow is agent-driven; only the technical probe and deterministic spec-to-Three.js codegen are automated. |
| img2threejs compilation/render/fidelity | Generated TypeScript is stored as an editable intermediate; it was not compiled, rendered or converted to a game-ready mesh. |
| AI 3D, rigging, MCP, teardown, Graphite | Planned, not implemented. |
| Windows symlink-escape test | Skipped without symlink privilege; policy logic is covered by absolute/`../`/missing tests and runs on Linux CI. |
