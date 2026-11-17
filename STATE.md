# State

- **Version:** 0.8.2
- **Milestone:** 0.8.2: generated-sound batches survive an unfinishable take
- **Active task:** 0.9.0 (PLAN.md): textures, PBR sets, sprites, sprite rendering, comfy-forge backend start
- **Current revision:** `v0.8.2` = `8d6a6c4` on main
- **Last known-good:** tag `v0.8.2`

## Completed

- Sound batch fix (0.8.2, 2026-11-16), from a field report: a 39-prompt `audio-sfx` run (117 takes, ~30 min) went FAILED in `audio.finish` because one best take was silent after trimming, keeping one output. Now each item falls back to its next take (`AUDIO-TAKE` WARNING), an item with no usable take is `AUDIO-FINISH` FAIL while the rest finish, near-silent takes (peak < -40 dBFS) never win over audible ones, `audio-process` finishes again from `audio-generation.json` / `music-generation.json`, the default worker timeout scales with the batch, JSON prompt entries with `"prompt"` are read instead of dropped, and a message-less FFmpeg failure names its exit code. The report's empty-stderr "could not prepare" was not reproduced locally (FFmpeg 9.0.2 wrote a header-only stage for every silent case tried); the fallback covers it either way. Released 2026-11-16: local suite 229 OK / 2 skipped with every provider present; real 3-prompt MOSS run reproduced the report (an item with only near-silent takes failed alone, the others finished); CI 7/7 green on `8d6a6c4`; 0 open Dependabot/secret alerts (code scanning not set up); release asset SHA-256 `b052ae8f…3dbb` re-downloaded and matched; installed from the zip, doctor exit 0; checkout `.venv` rebuilt, PATH `assetforge` reports 0.8.2, doctor exit 0.

- Audit (0.8.1, 2026-11-15): baseline 190 tests OK / 2 skipped with every provider present, doctor exit 0, CI green on `e434715`, 0 open Dependabot/secret alerts. 18 findings, each reproduced; fixes listed in CHANGELOG 0.8.1. New `tests/test_audit_regressions.py` (30 tests) failed before the fixes and passes after. Released 2026-11-15: local suite 220 OK / 2 skipped with every provider present; CI 7/7 green on `3167bfc` (the first push, `e5617b0`, failed on Windows/Python 3.12 because the clock ticks in ~15 ms steps there; fixed with a strictly increasing `created_ns`); 0 open Dependabot/secret alerts; release asset SHA-256 `17c03010…12dc` re-downloaded and matched; installed from the zip, doctor exit 0. Real runs: `blender-qa` on a `.blend` without `SM_Crate` now checks its mesh; `Install.ps1` twice in a copy under a path with spaces, `()` and `!`.
- Music (0.8.0, 2026-11-14):
  - `audio-music` renders ACE-Step 1.5 through comfy-forge 0.8.0's `TOOLS/music.py`, using a running ComfyUI or one started for the job and stopped afterwards (`comfybackend.py`).
  - Takes are ranked by length, then CLAP. `loop=true` builds bar-aligned seamless loops from the full-level bars. `AUDIO-LENGTH`, `AUDIO-LOOP` and `AUDIO-LYRICS` added.
  - Minecraft export streams music.
  - The provider id is now `comfy-forge`, with the old names still accepted.
  - Real instrumental, vocal and loop runs; evidence in `VALIDATION.md`.

- Audio (0.7.0, 2026-11-13):
  - Recipes `audio-voice` (Qwen3-TTS voice design and cloning, Dia nonverbals, Kokoro), `audio-sfx` (MOSS-SoundEffect v2) and `audio-process`.
  - `audio-setup`, which builds uv runtimes under `~/.assetforge/audio`.
  - Whisper and CLAP take checks, fixed-gain finishing, `AUDIO-001`–`006` checks, and the `minecraft` sound export target.
  - Real runs of every engine through the CLI on an RTX 4080 SUPER; evidence in `VALIDATION.md`.
  - Music (ACE-Step 1.5) is planned.
- teardown (0.6.0, 2026-11-13): `teardown-build` and `teardown-film` recipes, provider detection, `PAGE-001`/`VIDEO-001` validation. Upstream `a91262a` cloned beside the other provider clones with `npm ci`; the old candidate snapshots were retired. The upstream V8 example built and filmed through AssetForge on Windows.
- Provider recheck (0.5.1, 2026-11-13): blender-skills v1.3.0 and img2threejs v2.0.1 installed as clones in a declared tool root, each upstream suite run (69/69 on Blender 5.3.0; 1,416 img2threejs tests, 0 failures, 3 Windows symlink errors), AssetForge suite 144 OK / 2 skipped with every provider present, real pipeline/probe/codegen/engine-check runs. blender-skills is now found in tool roots and reports its release version; img2threejs reports its version; a wrong provider variable is reported instead of bypassed; pipeline `.blend1` backups removed; CI Actions v7 plus Dependabot. Companion tools evaluated in `docs/UPSTREAM-EVALUATIONS.md`.
- `engine-check` (0.5.0): Godot 4 headless imports a GLB, then loads and instantiates it. On 2026-11-12 Godot 4.7.2 passed the showcase sword (61 meshes) and the test triangle and failed a non-GLB file. Rendering is not tested.
- Godot, FFmpeg and ImageMagick detection (0.5.0) with a stated purpose each; FFmpeg and ImageMagick are not called by any recipe.
- Blender discovery (0.4.1): Steam libraries, uninstall registry, tool roots; a Hermes profile wrapper named `blender` is skipped. Proven on 2026-11-12 with Steam Blender 5.3 that was not on PATH.
- `probe` (0.4.0): read-only routing for a file or folder; prints the recipe commands that fit and the numbers behind them.
- `mesh-convert` (0.4.0): FBX/OBJ/STL/PLY/glTF/USD/Alembic/`.blend` to GLB through Blender. On 2026-11-12 a rigged, animated FBX (1 skin, 2 joints, 1 s animation) and an OBJ with `.mtl` converted with Blender 5.3.0 from a folder named with a space, `!`, parentheses and an accented letter; official glTF validator 0 errors.
- `GLB-013` rig/animation, `GLB-015` material/UV and `GLB-016` transform checks (0.4.0); embedded texture sizes decoded and budgeted.
- `.cmd`/`.bat` provider launch fixed for paths with spaces and `!`.
- `mesh-gameready` (0.3.1, local): default budget `game` fails a written GLB over 20,000 triangles. `hero` is 30,000. `accessory` is 4,000. A 700,000-triangle count is rejected. Guide: `docs/GAME-READY.md`. On 2026-11-12 a 699,878-triangle PBR GLB wrote 17,000 triangles, 21,186 vertices, 6,192,808 bytes, and three 1024 PNGs. Official glTF validator: 0 errors, 0 warnings. Engine import was not run.
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
- blender-skills 28-skill catalog, route CLI and Hermes external-dir documentation; tested upstream v1.3.1 (`b1b21df`), earlier v1.3.0 (`3e481ad`) and v1.2.0 (`389f28a`).
- `blender-pipeline` and `blender-qa`; mandatory upstream QA gate with numeric and random/wire review evidence.
- Whitelisted `blender-optimize` (`mesh-stats`, `make-lods`) and `blender-retopo-uv` (`auto-retopo`, `uv-pack`, `texel-density`); immutable input `.blend`, new project-owned outputs and upstream reports in provenance.
- Windows installer, updater, start script, local launcher; CI definition; examples; documentation.
- Project-owned `enchanted-fire-sword.glb` showcase: artisan-style low-poly GLB, preview PNG, reproducible generator, local GLB validation and third-party-free fixture.

- Release metadata, roadmap, release notes and publication checklist prepared for `0.1.0`.
- Clean install from committed source verified with and without optional providers.
- comfy-kit documented as the recommended free local texture-generation companion.

## Outstanding defects

None known. Open limits are evidence gaps, not known code defects:

- Engine imports (Roblox Studio, Godot editor) were not executed.
- A passing rig check proves consistent data, not a correct deformation.
- `mesh-gameready` drops animations (reported as a job warning).
- The symlink-escape regression test is skipped on Windows without symlink privilege; it runs on Linux CI.
- comfy-kit's built-in default model was rejected by the running SwarmUI; a valid `--set model=...` produced a successful render. The adapter reports the owner error correctly.
- blender-skills is optional; a machine without Blender or the skills still gets clean exit `4` and no changed core behavior.
- QA review sheets were inspected by the agent; no formal human art review was recorded.

## Exact commands

```text
python -m unittest discover -s tests -v
python -m unittest test_blender_skill_runner -v
python -m assetforge doctor --json
python -m assetforge probe examples/assets
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

NEXT ACTION (0.9.0 is uncommitted in the working tree; VERSION already says 0.9.0, nothing pushed or released):

1. Run `python -m unittest discover -s tests` on the final tree. The last full run (355 tests, OK, 2 skipped) predates the two-band fold, `repair_unit_vectors`, the `flat` engine, clean generated names and the sprite-render export change; each of those passed its own test file afterwards.
2. Docs still to update: README (recipe table, capability table, texture section, ImageMagick row), `docs/RECIPES.md` (the 11 new recipes, image-prep, sprite-atlas, comfy-generate), AGENTS.md table, `docs/PROVIDERS.md` (comfy-forge start, ImageMagick), `docs/UPSTREAM-EVALUATIONS.md` (spritecast: not a provider, paid OpenAI/Tripo keys), ROADMAP.md, RELEASE.md, RELEASE-NOTES.md. `docs/TEXTURES-SPRITES.md` and the CHANGELOG entry are written.
3. VALIDATION.md: record the real runs. Done: `texture-generate` through a running SwarmUI (seam 6.69 -> 0.56, PBR set); `mesh-gameready` on the reported Pixal3D axe (2 tangents rewritten, official validator 0 errors, Godot `engine-check` PASS); `sprite-render` on that axe (workbench) and the showcase sword (eevee); DDS and TGA through `image-prep`. Not done: `sprite-generate`, `comfy-3d` and a render through a SwarmUI AssetForge started itself (`backend=start`) - the GPU was held by other sessions; the start/stop path is covered by mocked tests only.
4. PLAN.md: fill the Evidence column, then commit, push, CI on the SHA, alerts, release zip, install, doctor.

Open: comfy-forge 0.11.0 is unreleased; `comfy-3d` and the optional `generate` flags were built against its working tree and tested against stand-ins. Its `-Tileable` crashes on Anima here (field report filed there). The field report against `mesh-gameready` is fixed and cleared.

Earlier line:

Earlier note: Deliberately left from the audit (suspected, not proven defects): `adapters.comfykit_*` keep their comfy-kit names; the `examples/README` fixture regeneration one-liner was not re-run.
Candidates after that: Candidates: Roblox Studio import evidence; a Unity import check (MCP for Unity or Unity-MCP, see `docs/UPSTREAM-EVALUATIONS.md`); a rendered rig deformation preview; KTX2 texture compression as an opt-in recipe (Blender 5.3's glTF exporter writes KTX2 natively, per blender-skills 1.3.0).

## Integration status

- Ultimate AI Starter Bundle: proposal only; no bundle file modified.
- comfy-kit: recommended free local texture-generation companion; read-only delegation, verified generation and import; no owner files modified.
- blender-skills: recommended optional Blender skills provider; read-only catalog and delegation; tested v1.3.1 (`b1b21df`) on Blender 5.3.0; optimization/retopo/UV runner verified on the current Blender 5.3.0 installation; no upstream files modified.
- img2threejs and teardown: provider Git clones (v2.0.1, `a91262a`); the earlier candidate snapshots matched upstream and were retired to the Recycle Bin on 2026-11-13.
