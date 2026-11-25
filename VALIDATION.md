# Validation evidence

Verified working tree: 0.3.0 release candidate based on `9027141dc5680a29ed4d7d4745bc551a04647e72`.

Environment: Windows 11, Python 3.14.10, Node 26.13.0, Pillow 13.0.0, jsonschema 4.x, glTF-Transform 4.5.1, Khronos glTF Validator installed locally in `.tools`, current Blender reports 5.3.0. The project works without any optional provider.

## 0.9.1 sound batches that share a GPU — 2026-11-25

Environment: Windows 11, Python 3.14.10, Pillow 13.0.0, Blender 5.3.0, Godot 4.7.2, ImageMagick 7.1.2-34, FFmpeg 9.0.2, Node 26.13.1, the three audio runtimes present.

- Baseline before any change (0.9.0 at `1915927`): **365 OK, 2 skipped**, `doctor` exit 0.
- Full suite after the fixes: **369 OK, 2 skipped** with every provider present (the real Kokoro test included); CI 7/7 green on `0edfd8f`. A later test-only commit adds a pure-Python run of `sfx_job` (model, WAV writer and measurements swapped out): two same-text lines get four distinct seeds, the first line keeps 1 and 18, and `result.json` lists all four takes as they are made.
- GPU lock: two concurrent `run_worker` calls on a one-second stub worker never overlap (the second printed `waiting for the GPU`); `gpu_lock(wait=0)` inside a held lock fails with `GPU busy`; the lock is free again after release. Not exercised against a live model contention.
- Saved takes: a stub worker that writes one take, a partial `result.json` and exits 3 without an error gives `audio worker failed: it stopped before finishing (exit 3); 1 take(s) were saved in ...: finish them with assetforge run audio-process --input "..."`. That `audio-process --input <folder>` form ran on a folder of two WAVs: `audio.source` 2 files, `audio.finish` 2 ogg files, SUCCEEDED. `audio-process` takes at most 200 files a run, so a larger saved folder has to be finished in parts.
- Presentation runs (images in `docs/presentation/`): `doctor` READY; `probe` on the showcase sword: 21,856 triangles, 61 meshes, validation PASS, fits Roblox no; `mesh-gameready`: 16,951 triangles, glTF checks PASS=14 FAIL=0 NOT_TESTED=1, 11 s; `probe` on the result fits every budget; `sprite-render` 8 facings eevee; `pixel-art` 64 px pico8 on a top-down frame; `texture-pbr` on `source.png`. Every image was looked at.
- Release `v0.9.1`: asset SHA-256 `8f1867a9d5863d769a341fe2ac7a414045183c096731210ad3898b0968338ea3`, re-downloaded and matched; extracted, `Install.ps1 -WithImages`, `assetforge.cmd --version` 0.9.1, `doctor` exit 0.
- Not run this release: the sdist build and the showcase generator SHA-256 check from `RELEASE.md`; no new audio was generated.

## 0.9.0 textures, sprites and image to 3D — 2026-11-17

Environment: Windows 11, Python 3.14.10, Pillow 13.0.0, Blender 5.3.0, Godot 4.7.2, ImageMagick 7.1.2-34, comfy-forge 0.10.0 then 0.11.0 with SwarmUI 0.9.8.4 (ComfyUI backend on 7821), Anima model `woomixAnima_v180`, RTX 4080 SUPER shared with other jobs.

- Full suite: **364 tests OK, 2 skipped** with every provider present (the skips: symlink privilege, and one provider-absent case). New files: `test_texture` (21), `test_sprites` (28), `test_2d_recipes` (51), `test_sprite_render` (13, six on real Blender), `test_comfy_forge` (16), `test_glb_repair` (6). `test_glb_repair` failed before `repair_unit_vectors` existed.
- `texture-generate`, prompt "mossy grey cobblestone pavement, hand-painted game texture", seed 4242, 1024 px, through the running SwarmUI: 6.5 s; `TEX-SEAM` 6.69 on the render, 0.56 after folding (simple cross-fade at the time). The tiled preview showed ghosted bricks in the overlap, so the fold was changed: broad tones fade, detail switches along the least-different path. Same render after the change: 6.69 -> 0.70, no doubled bricks in the 2x2 preview (looked at). Normal, ORM and height maps looked at: mortar lines read as grooves, stones as raised.
- `sprite-generate`, "a red health potion in a round glass bottle with a cork", seed 77: SwarmUI render, cut-out 600x775 from 1024, background #ffffff removed, `CUT-BACKGROUND` PASS. Looked at on magenta: no white rim; the glass highlights inside the bottle were kept. The model drew a grey drop shadow under the bottle despite "no shadow"; it is not the background colour, so it stays part of the sprite and the anchor sits at its bottom. `pixel-art` on the result: 37x48, 12 of 16 `sweetie16` colours.
- An earlier `sprite-generate` at 768 px was refused by SwarmUI ("Something went wrong while generating images") after 8 min 48 s while other jobs held the GPU; the same prompt at 1024 px later succeeded. The failure ended the job `FAILED` with SwarmUI's message.
- `seamless=true` (`generate -Tileable`) on the Anima model: SwarmUI refused, "SwarmTileableVAE ... ctypes objects containing pointers cannot be pickled". Field report filed with comfy-forge; comfy-forge 0.11.0 now refuses `-Tileable` for transformer models itself. AssetForge leaves it off by default.
- Field report fix, `mesh-gameready` on comfy-forge's 699,928-triangle Pixal3D axe: before, `GLB-014` failed with 2 `ACCESSOR_VECTOR3_NON_UNIT` errors; after, "2 tangent(s) and 0 normal(s) that were not unit length rewritten", 17,000 triangles, official validator 0 errors 0 warnings, `engine-check` PASS (Godot 4.7.2 imported and loaded it, 1 mesh), `export --target godot` PASS.
- `sprite-render` on that game-ready axe (8 facings, workbench, 3.3 s) and the showcase sword (8 facings, eevee, 10.4 s): every facing looked at; the axe turns about its handle, the sword's emissive blade shows in eevee.
- `image-prep format=dds`: DXT5 for a picture with alpha (85.5 KiB at 256 px), header `DDS `, Pillow reads it back; `format=tga` RLE.
- `comfy-3d` live run on the generated potion picture (comfy-forge 0.11.0, pixal3d, seed 5, `timeout=2400`), while another job held the GPU at 100 %: comfy-forge's `model3d.py` reported "FAIL no completion within 2400s (raise --timeout for long XL renders)" after 40 min; the job ended `FAILED` with that message (exit 6). No model came back, so the AssetForge side past the hand-off is still proven only by the stand-in tests and by the game-ready step on the real Pixal3D axe above. Rerun on an idle GPU (about 4 min expected).
- Second `comfy-3d` attempt, `timeout=3600`, with another session's `audio-voice` batch holding about 8 GB: nothing answered on 8188 or 7820-7832, so AssetForge started comfy-forge's ComfyUI on a free port (`backend=auto`), the render ran through the shape (20 steps), refinement (12 steps at about 40 s each) and texture stages, and was in the final texture bake (4 of 5) when `model3d.py` hit its limit after 60 min. The job ended `FAILED` with that message and the temporary ComfyUI process was gone afterwards: the start/stop path for a ComfyUI started per job ran live.
- Third and fourth `comfy-3d` attempts with the same voice batch still running: the third sat in the shape decode for 70 min with VRAM full and was stopped; the fourth (about 11 GB free at its start) got through the shape stages and into the texture stage at about 16 s a step, and was stopped at the operator's request to wrap up. No model came back from any attempt. Each stop or timeout left no ComfyUI process behind. The end-to-end `comfy-3d` run needs an idle GPU (comfy-forge measured about 4 min there).
- Not run live: SwarmUI started by AssetForge for a job (`backend=auto` with nothing running, or `start`); SwarmUI was already running for other sessions. The start, port hand-off, and stop are covered by mocked tests only. The first attempt to start it in this session did come up (on the settings port, through comfy-forge's own start), so the launcher path itself works.
- Not verified: nobody judged the generated art; `TEX-DERIVED`, `GEN-VISUAL`, `CUT-VISUAL`, `PIX-VISUAL`, `SPRITE-VISUAL` stay `NOT_TESTED` in the assets.

## 0.8.2 sound batches — 2026-11-16

Environment: Windows 11, Python 3.14.10, FFmpeg 9.0.2, RTX 4080 SUPER, the 0.7.0 audio runtimes (MOSS-SoundEffect v2 and CLAP in `sfx`).

- Full suite: **229 tests OK, 2 skipped** with every provider present. New tests, each failing before its fix: a silent best take falls back to the next take (`AUDIO-TAKE`), an item with no usable take fails alone (`AUDIO-FINISH`) while the batch finishes and `validate` exits 5, a fallback take never inherits the best take's transcript, near-silent takes rank below audible ones, `audio-process` from `audio-generation.json`, missing takes in a report, the batch-scaled worker timeout, JSON `"prompt"` entries, and the exit-code message for a silent FFmpeg failure.
- Real run (`audio-sfx`, a JSON list using `"prompt"`, 3 prompts × 2 takes, 1.5 s, 2 min 30 s): `eye_open` ("the quiet faint sound of an eyelid opening") made two takes peaking at 0.0046 and 0.0039, both marked unusable; it got `AUDIO-FINISH` FAIL ("silent after trimming") and `door` and `sigh` were still finished, asset COMPLETE. `sigh`'s second take (peak 0.0061) was marked unusable and not chosen. This is the field report's failure, which in 0.8.1 failed the whole asset.
- Not reproduced: the report's "ffmpeg could not prepare" with an empty message. FFmpeg 9.0.2 wrote a header-only stage for every silent input tried (zeros, -48 dB tone, noise, spikes, at 24 and 48 kHz); the fallback handles that error the same way, and its message now names the exit code.
- Not verified: listening.

## 0.8.0 music — 2026-11-14

Environment: Windows 11, Python 3.14.10, comfy-forge 0.8.0 with ComfyUI 0.44.0 (SwarmUI's bundled backend), ACE-Step 1.5 `aio` checkpoint, RTX 4080 SUPER, FFmpeg 9.0.2, AssetForge audio runtimes from 0.7.0 (CLAP in `sfx`).

- Full suite: `python -m unittest discover -s tests` gave **190 tests OK, 2 skipped** (Blender installed; no symlink privilege). `test_audio` has 33 tests, adding:
  - **Music through the recipe:** a stub comfy-forge (its `music.py` interface), a stub ComfyUI `/system_stats` server and a stub CLAP worker cover argument passing, instrumental vs lyrics, take ranking (a full-length take beats a higher-CLAP take that stopped halfway), `AUDIO-LENGTH`, Minecraft `"stream": true` with stereo music accepted, and refusing bad key/seconds/bpm before any backend.
  - **Exit 4:** when `backend=running` finds no ComfyUI.
  - **Loops:** whole bars, a quiet outro left out, and refusing a track under 4 bars.
  - **Locating ComfyUI:** its folder found beside the interpreter.
  - **Provider names:** `comfy-forge`, with the old `COMFY_KIT_ROOT` still working.
- Real runs:
  - **45 s instrumental, nothing running.** AssetForge asked comfy-forge for its interpreter, started ComfyUI on a free port (up in 18 s) and made two takes. The kept take scored CLAP 0.44 and -15.97 LUFS. The backend was stopped, and no `main.py` process remained.
  - **40 s vocal song through the running SwarmUI backend (7821), with a lyrics file.** Two takes in 34 s. The kept take scored CLAP 0.41. Both takes ended about 5 s early, so `AUDIO-LENGTH` gave a WARNING, and `AUDIO-LYRICS` stayed NOT_TESTED.
  - **60 s at 90 bpm with `loop=true`, temporary backend.** It produced 19 bars of 2.667 s (50.7 s) from bars 1 to 20, leaving out the trailing partial bar. `AUDIO-LOOP` passed, the kept take scored CLAP 0.38, and loudness came out at -16.89 LUFS.
  - **Minecraft export of the loop.** It wrote `sounds.json` with `"stream": true` and `AUDIO-POSITIONAL PASS` (music, stereo).
- CLAP on music: two tavern takes scored 0.36 and 0.44 against their tags, and at most 0.03 against heavy metal, dark ambient and rain tags.
- Found and fixed by the real runs:
  - A loop seam metric that compared 100 ms on either side of the wrap. Since the wrap is continuous by construction, it measured the music, not the seam. It was replaced by bar-level selection.
  - Assets from text-only recipes were named after the recipe; they now take their `name`.
- Not verified: listening (tracks and loop seams), sung words, variants other than `aio`, and any game loading the files.

## 0.7.0 audio — 2026-11-13

Environment: Windows 11, Python 3.14.10, uv 0.13.5, torch 2.9.1+cu128, NVIDIA RTX 4080 SUPER (16 GB), FFmpeg 9.0.2. Runtimes built by `assetforge audio-setup` under the audio home: speech (qwen-tts 0.1.1, transformers 4.57.3), sfx (MOSS-TTS `934d682`, transformers 4.57.1, diffusers 0.37.1), kokoro (kokoro 0.9.4). All three smoke tests passed with CUDA.

- Full suite: `python -m unittest discover -s tests` → **180 tests OK, 2 skipped** (Blender installed; no symlink privilege). `test_audio` runs 23 tests. A stub runtime (a bare venv) and a stub worker cover line parsing, take scoring, runtime detection, worker errors, finishing, level checks, each recipe through the CLI, exit codes, the Minecraft, Godot and Roblox export rules, and probe routing. `RealKokoro` ran against the installed runtime.
- Real recipe runs in a fresh project:
  - **`audio-voice`, qwen3-tts.** Three lines took 2 takes each, with the voice designed from a text description (three auditions, all 100% Whisper match). Every line got `AUDIO-ASR PASS` at 100%, and loudness came out at -17.95, -17.95 and -17.75 LUFS against a -18 target. A take took 3.5 to 8 s after the models loaded.
  - **`audio-voice`, dia, no reference.** The laugh line passed. The gasp line kept babbling (Whisper heard "Oh, oh, oh...") and was correctly marked `AUDIO-ASR FAIL`.
  - **`audio-voice`, dia, with the Qwen-designed reference voice and 3 takes.** Both lines passed at 100% ("Ah! That hurt!", "Oh, you are too kind.").
  - **`audio-voice`, kokoro.** The line passed at 100%. `AUDIO-004` gave a WARNING (-19.54 LUFS) because the -1 dBTP ceiling limited the gain, and the report says so.
  - **`audio-sfx`.** Sword swing and door creak took 3 takes each with distinct seeds. CLAP was 0.49 and 0.41 for the kept takes, at about 17 s per take for 100 steps. Rain on a tin roof scored CLAP 0.29 and got an `AUDIO-CLAP WARNING`.
  - **`export --target minecraft --namespace villageprincess`.** It wrote `assets/villageprincess/sounds/princess-voice/*.ogg` and `sounds.json`, with greet1 and greet2 grouped as variants of one event, and `AUDIO-POSITIONAL PASS` (mono).
- CLAP calibration: six MOSS takes scored 0.29 to 0.49 against their own prompts and at most 0.26 (mostly under 0.18) against four unrelated prompts, which is where the 0.30 / 0.20 thresholds come from.
- Bugs found by the real runs and fixed before release:
  - MOSS ran out of VRAM, because its float32 DiT under autocast spilled past 16 GB. It now peaks near 10 GB with bf16 weights.
  - All MOSS takes were identical, because the pipeline's own `seed` was not passed.
  - torch.compile and the CUDA-graph marker failed on Python 3.14.
  - Whisper returned dots for 44.1 kHz input. Audio is now resampled to 16 kHz first.
  - huggingface_hub raced into `os.symlink` (WinError 1314) on a first download.
  - misaki's spaCy download installed into the shared Python. It was removed there and is now shipped in the runtime.
  - Minecraft resource paths were built from the timestamped asset id, which contains an uppercase `T`.
- Not verified:
  - Listening (`AUDIO-LISTEN NOT_TESTED`).
  - Any game loading the sounds.
  - The audio runtimes on Linux or macOS.

## 0.6.0 teardown — 2026-11-13

Environment: Windows 11, Node 26.13.1, teardown `a91262ac1109051e014662d42ecb0b7bc1f113b1` with `npm ci` (Playwright 1.58.2, esbuild 0.28.1, three 0.186.1), Chromium 145.0.7632.6 and its headless shell, FFmpeg 9.0.2, NVIDIA RTX 4080 SUPER through ANGLE/D3D11.

- Full suite: `python -m unittest discover -s tests` → **157 tests OK, 2 skipped** (Blender installed; no symlink privilege).
- `test_teardown`: 13 tests. The stub-provider tests cover detection, the missing `npm install` reason, a wrong `TEARDOWN_ROOT`, copying a sim with its layout, entry selection (refusing `../` and unknown names), parameter checks and exit codes. The real-provider tests built upstream `v8-live` through `teardown-build` (page over 100 KB), rendered `v8-film` to an MP4 (`ftyp` box) through `teardown-film`, wrote a review sheet with every frame recorded as an artifact, and showed that filming a `-live` page fails with a message naming the film page.
- CLI run: `teardown-film --input <teardown>/sims --set entry=strandbeest-film --set stills=1,4,7,10` → `SUCCEEDED`; the 1740x540 sheet was opened and shows four labelled frames of the walking machine. `validate` → `PAGE-001 PASS`.
- `npx playwright install chromium` stalled during extraction twice; the official archives (7-Zip integrity test passed for both: Chromium 308 files, headless shell) were extracted by hand into the folders Playwright names. Capture then launched Chromium and reported the GPU.


Environment: Windows 11, Python 3.14.10, Node 26.13.1, Blender 5.3.0 (Steam), Godot 4.7.2, glTF-Transform 4.5.1, gltf-validator 2.0.0-dev.3.10.

Upstream suites, run in the provider checkouts:

- blender-skills v1.3.0 (`3e481ad1b8e301defced7369e4254022abe0821e`): `python tools/validate_skills.py` → `OK`; `BLENDER_EXE=<Blender 5.3.0> python tools/run_tests.py` → **69 passed, 0 failed, 0 skipped**; the same run with Blender 5.2.4 LTS → **69 passed, 0 failed, 0 skipped**.
- img2threejs v2.0.1 (`0c0c49bc168e648dbaf9c8c080474de0b3a941b6`): `python -X utf8 -m unittest discover -s forge/tests -p "test_*.py"` → **1,416 tests**, 0 failures, 3 errors, 64 skipped. All 3 errors are `WinError 1314` (an unprivileged Windows process cannot create the fixtures' symlinks).

AssetForge:

- `assetforge doctor` → every provider `PASS`: blender-skills `1.3.0` and img2threejs `2.0.1` found in a declared tool root without a variable.
- `python -m unittest discover -s tests -v` → **144 tests OK, 2 skipped** (`test_missing_provider_exit_code`: Blender is installed; `test_symlink_escape_is_rejected`: no symlink privilege). The Blender pipeline, QA gate and whitelisted runner tests executed against blender-skills v1.3.0.
- Real recipe runs in a fresh project: `img2threejs-probe` SUCCEEDED; `img2threejs-codegen` SUCCEEDED with a 64,589-byte TypeScript factory from the upstream conformance spec; `blender-pipeline` SUCCEEDED (108 triangles, 0 QA errors, 0 warnings, `GLB-014 PASS`); `engine-check` on its optimized GLB → `PASS`; `glb-optimize` and `mesh-convert` on the showcase sword SUCCEEDED.
- Regression: the pipeline used to leave `blender-asset-material.blend1` in the asset; the integration test now asserts no `*.blend1` remains and passes.

## Test suite

Command:

```text
python -m unittest discover -s tests
```

Result (final 0.3.0 run):

```text
BLENDER_SKILLS_ROOT=... python -m unittest discover -s tests
Ran 97 tests in 374.271s
OK (skipped=2)
```

Without the optional Blender providers, the final 0.3.0 run is `python -m unittest discover -s tests`: `Ran 89 tests in 159.878s`, `OK (skipped=4)`. That run exercises the absent-provider behavior and the standalone image/GLB/export paths.

The two skips on the real-Blender Windows run are `test_symlink_escape_is_rejected` (no symlink privilege) and `test_missing_provider_exit_code` (Blender is available, so the absent-provider CLI case cannot be produced on this host). The symlink path runs on Linux CI; the Blender-absent path runs in CI environments without Blender. The real Blender integration tests run when both providers are available and skip cleanly otherwise.

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
- Blender QA gate: clean pass, unacknowledged warning failure, acknowledged warning pass, error failure, malformed `pass=false` without details, visual-pending and visual-approval-with-note paths.
- Full Blender pipeline: every recorded artifact size and SHA-256 matches the final file, including the immutable build/material `.blend` stages.
- Project portability: copying the completed project preserves artifact resolution, and `asset.json` contains no absolute project or machine path.
- Export excludes QA preview images from texture folders.

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

## Blender-skills integration

Upstream: [EL4CTEO/blender-skills](https://github.com/EL4CTEO/blender-skills) at revision `389f28addc79b87b28764898e38e7bf408d14b77` (v1.2.0), MIT.

- `python tools/validate_skills.py` → `OK`; 28 skill directories, all descriptions and token budgets valid.
- `BLENDER_EXE=<Steam blender> python tools/run_tests.py` → **69 passed, 0 failed, 0 skipped** in real Blender 5.2.3 LTS.
- `assetforge providers --json` detected Blender 5.2.3 and blender-skills 1.2.0 at the tested revision.
- `assetforge blender-skills --json` listed **28** skills; `--route materials` returned `blender-pbr-materials` and `blender-texturing`.
- `assetforge run blender-sample --json` → `SUCCEEDED`; 108 triangles, real Blender 5.2.3, GLB validated.
- `assetforge run blender-pipeline --json` → `SUCCEEDED`:
  - source `.blend` 88,638 bytes; material `.blend` 90,552 bytes, recorded separately so the build hash stays valid;
  - 108 triangles;
  - upstream `blender-asset-qa`: `pass=true`, `ground_z=0.0`, 0 errors, 0 warnings;
  - random and wire review sheets written (567,926 and 679,113 bytes) and visually inspected; no floating parts, z-fighting or topology defects;
  - `BLENDER-QA-RENDER=PASS` explicitly distinguishes rendering from `BLENDER-QA-VISUAL`; the default is `NOT_TESTED`, and this run used `visual_review=approved` with a recorded `approval_note`;
  - GLB exported by upstream `blender-export-pipelines` at 8,856 bytes;
  - optimized GLB 6,980 bytes;
  - `GLB-014 PASS`, official validator 0 errors/0 warnings;
  - provenance records upstream revision, version, QA numbers, project-relative review paths and the visual-review decision.
- `assetforge run blender-qa --input blend=<asset.blend> --json` → `SUCCEEDED`; 3 artifacts and `BLENDER-QA=PASS` on an existing `.blend`.
- A deliberately lifted crate produced an upstream grounding warning. Since no `warning_note` was supplied, the job ended `FAILED` with the acceptance instruction; the warning was preserved, not silently converted to a clean pass.
- Export from the same asset to Roblox, Godot and generic → `PASS`, `kind=mesh`, `engine_import=NOT_TESTED`; only the optimized GLB is packaged. QA previews are not copied into texture folders (regression test added).

### Whitelisted optimization and retopo/UV runner — 2026-11-12

The current machine's Blender install reports **5.3.0** (previous verification evidence above used 5.2.3 LTS). Upstream blender-skills remains at revision `389f28addc79b87b28764898e38e7bf408d14b77` (v1.2.0).

- `python -m unittest test_blender_skill_runner` → **6 passed**: `mesh-stats` budget reporting, `make-lods` writing `LOD1`/`LOD2`, `auto-retopo` decimate output, `uv-pack` smart-project UVs, `texel-density` report and targeted repack, all through real Blender.
- `python -m unittest discover -s tests` → **97 tests, OK (2 skipped)**.
- With Blender unavailable/unset, discovery exits **0** with the new runner class skipped as one class-level skip (`Ran 89`, `skipped=4`); no behavior changes in the standalone package.
- Fresh wheel/sdist build: **PASS**; both new recipes are present in the wheel's `data/recipes/`; installed clean environment lists `blender-optimize` and `blender-retopo-uv` and `--help` succeeds.
- `blender-optimize` and `blender-retopo-uv` are deliberately fixed-argument runners: they expose only the documented operations and documented arguments; no arbitrary skill names, script paths or shell access.
- `mesh-stats` budget is restricted to `mobile`, `roblox`, `web`, `vr`, `console`, `pc`; ratios and numeric inputs are validated before Blender starts. Mutation writes a new `.blend`, leaves the input unchanged and records the upstream JSON report in the asset.
- Commit `71b6903e1193a220ec23420a0bab0ed0ed2f1be9` pushed to `main`; hosted workflow `ci` run `43169849382` passed **7/7 jobs**. Security queries: **0** open Dependabot alerts, **0** open secret-scanning alerts; code-scanning is unavailable (`no analysis found`).

### Enchanted fire sword showcase — 2026-11-12

- User inspected and preferred the selected artisan candidate; it is intentionally project-generated low-poly work, not a reconstructed or AAA-quality hand-sculpted model.
- Showcase files: `examples/assets/enchanted-fire-sword.glb`, `examples/assets/enchanted-fire-sword.png` and `examples/generate-enchanted-fire-sword.py`; all are project-owned.
- User requested iteration after review: slimmer crossguard, less bulky profile, lower glow, cleaner blade seams and a continuous neck/finial instead of a visually disconnected pommel.
- Regenerating the GLB from the repository generator produced the same SHA-256: `2d4c4635950ba63c7409cce9fbb31a0fdbb6b7441f8a5f92ad30820f369e33db`.
- Showcase GLB inspection/validation job `20261112T074756-5d0b68` → `SUCCEEDED`: `21,856` triangles, `26,044` vertices, `12` materials, `830,584` bytes, `PASS=12`, `WARNING=0`, `FAIL=0`, `NOT_TESTED=1` (`GLB-013`, no skin/animation).
- Showcase GLB contains no third-party artwork or source files. The renderer/image is project-owned showcase output.
- Attached PNG SHA-256: `5fccfbf67a57a9107b30703aafad9d8d43ab6b6674c087dc60d37745969012d6`.
- Full suite with `BLENDER_SKILLS_ROOT` available → **97 tests, OK (2 skipped)**.
- Full suite without blender-skills available → **89 tests, OK (4 skipped)**.
- Fresh 0.3.0 wheel/sdist build → **PASS** (`assetforge-0.3.0`); examples remain outside the Python wheels as intended; release archive examples are added by the repository release packaging step.
- Wheel SHA-256: `9c6f5eabdda53c1409a200ad0ba842a95baaf0ad74e388696d2dd1761dc02140`; source distribution SHA-256: `15a6df870e3ee8420c0b3daf0744d5968a11d808d90faf7c21ab9b30b4abc908`.
- CI smoke also runs `glb-inspect` on the enchanted showcase fixture.
- Local wheel reached `assetforge --version` → `0.3.0`; the venv resolved source imports because `PYTHONPATH` is inherited, so the wheel hash, not the local import layer, is the independent artifact evidence here.

## Installer and packaging

- `Install.ps1` created a repo-local `.venv`, ran `doctor`, exited `0` at the 0.1.0 checkpoint.
- `assetforge.cmd --version` printed `assetforge 0.1.0` at that checkpoint.
- 0.2.0 source distribution built successfully and includes the same package data; its hash is reported in the handoff rather than embedded in a file it contains.
- 0.2.0 wheel built successfully; exact size and SHA-256 are reported in the handoff rather than embedded in the package evidence.
- The 0.2.0 wheel contains `data/blender/procedural_crate.py`, both Blender recipes and the Khronos bridge.
- Installed the 0.2.0 wheel into a clean virtual environment: `assetforge --version` → `0.2.0`; both Blender recipes listed; `blender-pipeline` → `SUCCEEDED`, 9 artifacts, `BLENDER-QA=PASS`, `BLENDER-QA-RENDER=PASS`, `BLENDER-QA-VISUAL=NOT_TESTED` by default.
- Verified all 9 recorded artifact sizes and SHA-256 values against disk and confirmed no absolute project path appears in `asset.json`.
- Previous 0.1.0 wheel evidence: `assetforge-0.1.0-py3-none-any.whl`, 57,942 bytes, SHA-256 `c7cb404b4c7882ff66553f26ef59e40d3033215e438eeae07e3c54af9d12f5a4`.
- Wheel installed into a clean environment; `assetforge --version` returned 0.1.0, `glb-inspect` ran against the textured fixture, `validate` returned `PASS` with `PASS=11, FAIL=0, NOT_TESTED=2` (official validator unavailable in that isolated environment, plus no rig data).
- Packaged validator bridge verified from that installed wheel in a project path containing spaces:
  - before installing the validator into the project's `.tools`, `GLB-014` was `NOT_TESTED`;
  - after installing `gltf-validator`, the installed bridge was detected and `GLB-014` returned `PASS` with `0 error(s), 0 warning(s)`;
  - the bridge path itself contained spaces and was invoked by argument list, not shell interpolation.

## Clean install from committed source

A fresh clone of the committed source was installed into a new virtual environment with `pip install ".[images]"`.

- `assetforge --version` → `assetforge 0.1.0`; recipe discovery listed the built-in recipes present at that checkpoint.
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
| Roblox Studio import | No Studio session was run. File-format support is documented; runtime/visual compatibility is `NOT_TESTED`. |
| Godot import | No editor session was run. |
| img2threejs image-to-spec reconstruction | Upstream workflow is agent-driven; only the technical probe and deterministic spec-to-Three.js codegen are automated. |
| img2threejs compilation/render/fidelity | Generated TypeScript is stored as an editable intermediate; it was not compiled, rendered or converted to a game-ready mesh. |
| AI 3D, rigging, MCP, Graphite | Planned, not implemented. |
| teardown visual quality | Frames are rendered, not reviewed; `TEARDOWN-VISUAL` stays `NOT_TESTED`. |
| Windows symlink-escape test | Skipped without symlink privilege; policy logic is covered by absolute/`../`/missing tests and runs on Linux CI. |

## blender-skills 1.3.1 (2026-11-13, AssetForge 0.7.1)

- Upstream v1.3.1 (`b1b21dfb73bc40b874ebf2aa12645931bfed3523`) in a separate worktree: `python tools/validate_skills.py` → `OK`; `BLENDER_EXE=<Blender 5.3.0> python tools/run_tests.py` → **72 passed, 0 failed, 0 skipped**.
- The declared-root clone was fast-forwarded to v1.3.1; `assetforge doctor` reports blender-skills `1.3.1` `PASS`.
- `tests/test_blender_skill_runner.py` (real Blender: LODs, auto-retopo, UV pack, texel density report and set, mesh stats) → **6 OK**. Full `python -m unittest discover -s tests` → 180 tests, 2 skipped; one run had a single transient error that did not reproduce on the next full run.
