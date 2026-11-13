# AssetForge 0.5.1 — Providers brought current

blender-skills and img2threejs both shipped new releases. Each was run through its own test suite and through AssetForge's recipes before this release accepted it.

## Included

- blender-skills **v1.3.0** is the tested provider (Blender 5.3 support). A plain clone in a declared tool root is now found without setting `BLENDER_SKILLS_ROOT`, and the reported version is the upstream release, not lagging per-skill metadata.
- img2threejs **v2.0.1** is the tested provider; its version is now reported.
- A provider variable that points at the wrong folder is reported with the markers it lacks instead of being silently replaced by another copy.
- `blender-pipeline` no longer leaves a stray `.blend1` save backup in the asset.
- CI runs on `actions/checkout@v7` and `actions/setup-python@v7`; Dependabot watches Actions monthly.
- New companion tools (CLI-Anything, MCP for Unity, Unity-MCP, awesome-gamedev-agent-skills, OBS MCP and others) are evaluated in `docs/UPSTREAM-EVALUATIONS.md`. None is vendored.

## Verified

- blender-skills v1.3.0: upstream `validate_skills.py` OK and 69/69 headless tests on Blender 5.3.0 and on Blender 5.2.4 LTS (Windows).
- img2threejs v2.0.1: upstream suite of 1,416 tests with no assertion failures; 3 fixture errors are Windows symlink-privilege errors, 64 tests skipped.
- AssetForge full suite with every provider present on Windows: 144 tests, 2 platform skips.
- Real recipe runs: `blender-pipeline` (108 triangles, 0 QA errors, 0 warnings, Khronos validation `GLB-014 PASS`, Godot `engine-check` PASS), `glb-optimize`, `mesh-convert`, `img2threejs-probe`, `img2threejs-codegen` (64,589-byte TypeScript factory from the upstream conformance spec).

## Not verified

- Rendering, materials on screen, animation playback and physics in Godot. `engine-check` proves import and load.
- Roblox Studio import. Export packaging for Roblox remains a file check.
- img2threejs image-to-spec reconstruction stays agent-driven; generated TypeScript is not compiled or rendered by AssetForge.
- blender-skills features new in v1.3.0 that AssetForge does not call (KTX2 export through the `web` preset, Blender 5.3 compositor notes).
