# Changelog

## 0.9.1 — 2026-11-25

Two field reports from long sound batches, plus a new README.

Fixes:

- Lines with the same text in one `audio-voice` or `audio-sfx` run came out identical: every line seeded take k with the same number, so four variants of one prompt were four copies (correlation 1.000) and every check passed them. A line that repeats an earlier line's text is now shifted to its own seeds. Runs without repeated text keep their seeds and therefore their audio.
- Two audio jobs started at once (two projects, two sessions) shared the GPU with no coordination: two MOSS workers filled a 16 GB card and stalled, and a third job ran a live batch out of memory. Audio workers now queue on an operating-system file lock in the audio home (`gpu.lock`, released when the holder exits or dies). A waiting job prints `waiting for the GPU` and waits up to `ASSETFORGE_AUDIO_GPU_WAIT` seconds (default four hours; `0` fails at once with `GPU busy`). The lock orders AssetForge's own audio workers only, not ComfyUI or other programs. Tested with stub workers (two concurrent runs never overlap); not exercised on a live GPU contention.
- A batch that died part-way left `result.json` with no items, so its saved takes looked lost. The worker now records each take as it is written, and the error names how many takes were saved, where, and the `audio-process` command that finishes them.

Also:

- README rewritten around real runs: a doctor and probe shot, the showcase sword through `mesh-gameready` and `sprite-render`, and the images that run produced. The capability table, provider table, Blender and comfy-forge workflows, recipe list and security boundaries moved to `docs/CAPABILITIES.md` unchanged.
- The README called the showcase sword low-poly and a reference for Roblox-style games; as shipped it is 21,856 triangles, over the 20,000 game cap and over the Roblox budget. It now says so, and that `mesh-gameready` brings it to 16,951 triangles, after which it fits every budget.
- `AGENTS.md` listed the export targets without `minecraft`.
- CI runs with a read-only token (code scanning: missing workflow permissions).

## 0.9.0 — 2026-11-17

Textures, sprites and image-to-3D for an agent that can only write text and code. Eleven new recipes; every one of them is a single command.

New recipes:

- `texture-generate`: a prompt becomes a tileable PBR material. comfy-forge renders the surface, the picture is made to repeat, the seam is measured, and base colour, normal, height, roughness, occlusion, metallic, the packed ORM texture and `material.json` are written.
- `texture-tileable`: any picture is made to repeat without a seam. Each edge is folded over the opposite one: broad tones fade across the fold, and detail switches along the line where the two sides differ least, so bricks and planks do not ghost. `TEX-SEAM` measures the wrap-around edge against the inside of the picture; a picture that already tiles is kept as it is. A 2x2 tiled preview is written.
- `texture-pbr`: a colour map becomes a map set. The normal map is `opengl` (glTF, Godot, Blender, Unity) or `directx` (Unreal, the Bethesda engines); `tileable=auto` wraps the maps when the picture tiles. The maps are estimates from brightness and are recorded as such (`TEX-DERIVED` stays `NOT_TESTED`).
- `image-cutout`: a subject on a plain background becomes a sprite with real transparency. The background colour is read off the border and removed from the border inwards, so the same colour inside the subject stays. Edge pixels get their coverage as alpha and lose the background's tint; transparent pixels take the subject's edge colour so a filtered texture does not show a rim. The result is trimmed and its anchor recorded.
- `sprite-generate`: a prompt becomes a cut-out sprite (comfy-forge render, then `image-cutout`).
- `pixel-art`: a picture is scaled down onto a palette (`pico8`, `db16`, `sweetie16`, `cga`, `gameboy`, `1bit`, a `.hex`/`.gpl`/image palette file, or colours picked from the picture), with on-or-off alpha and an enlarged preview.
- `sprite-slice`: a sheet is cut into frames, by grid or by finding each separate island of pixels.
- `sprite-render`: Blender renders a GLB as sprites: 1, 4, 8 or 16 facings at a fixed camera pitch (30 for 2:1 isometric), every animation in the file or the ones named, all frames at one scale. It writes the frames, one sheet and a JSON with each frame's rectangle and anchor. The facings turn about the model's origin when the model stands on it. Engines: `workbench` (shaded), `flat` (base colour only), `eevee` (lit).
- `comfy-3d`: one picture becomes a game-ready GLB: comfy-forge's image-to-3D (its `TOOLS/model3d.py`, comfy-forge 0.11.0 or later), then the same collapse and validation as `mesh-gameready`. The sculpt is kept as the source mesh.

comfy-forge images:

- `comfy-generate` (and the two recipes built on it) no longer needs SwarmUI started by hand. A running SwarmUI is used as it is; when none answers, comfy-forge's SwarmUI is started without a browser on a free port for the job and stopped afterwards (`backend=auto`; `running` never starts one, `start` always does).
- `steps` and `cfg` are passed through. `seed=-1` picks a seed and records it, so every render can be repeated.
- `negative`, `lora`, `transparent`, `upscale`, `seamless` and image to image (`--input init=<picture>` with `creativity`) are passed to a comfy-forge that has them. The installed script is asked which options it declares; an older one is refused with that message before anything renders.
- Generated files are named after `name`, or the first words of the prompt, instead of SwarmUI's prompt-and-model file name.
- Messages say comfy-forge, not comfy-kit.

Fixes:

- `mesh-gameready` output passes the official validator on meshes whose collapse leaves a triangle without UV area. Blender wrote a zero-length tangent there and `GLB-014` failed the run (found on a Pixal3D mesh). Normals and tangents that are not unit length are rewritten in the exported file and the step says how many.
- `export` ships the records an engine needs beside a picture: `atlas.json` was left out of every atlas export, so a packed atlas arrived without its frame rectangles. Sheets, cut-outs, pixel sprites and materials ship theirs too (artifact role `data`), and `validate` checks that each record is readable and names a picture the asset holds (`DATA-001`).
- A second `export` of a mesh or texture asset no longer leaves the first export's files in the folder beside a record that does not list them.
- `export` refuses two pictures with the same file name instead of letting one overwrite the other.
- `image-prep`: a negative `width` or `height`, a size above 16384 px or a `quality` outside 1-100 is an error, not a Pillow traceback or a multi-gigabyte allocation; a one-sided resize never rounds the other side to zero.
- `sprite-atlas` takes up to 256 frames (was 64); the 8192 px side limit still holds.
- `run --input name=path` with a path that does not exist says which input and which path, and exits 2. It used to report the input as not given at all, and a missing input exited 6 (run failure) instead of 2 (usage).

Also:

- `image-prep --set format=dds` writes DXT1 or DXT5 with mipmaps through ImageMagick, which now has a job; `format=tga` writes RLE TGA.
- `probe` routes pictures: a subject on a plain background to `image-cutout` and `comfy-3d`, a surface to `texture-tileable` and `texture-pbr` (with its measured seam), a cut-out sprite to `pixel-art` and `sprite-slice`; a GLB is offered `sprite-render`.
- Provider detection reads glTF-Transform's version from its package instead of starting Node: every command is about 0.7 s faster.
- Pillow 10.3 or later is needed for the new image recipes.

## 0.8.2 — 2026-11-16

One bad take no longer fails a whole batch of generated sounds.

- `audio-voice`, `audio-sfx` and `audio-music`: when the chosen take cannot be finished (silent after trimming, or refused by FFmpeg), the next-best take of that item is finished instead and `AUDIO-TAKE` `WARNING` names it, with that take's own CLAP or transcript evidence. An item with no finishable take gets `AUDIO-FINISH` `FAIL` and the rest of the batch is still finished; the run fails only when nothing could be finished. A single unfinishable take used to fail the whole asset after the generation had run, keeping one output.
- A take whose loudest sample is under -40 dBFS is never chosen while another take of the item has sound (speech, sfx and voice-design auditions). Prompts such as "a quiet sigh" made MOSS write near-silent takes that still won on CLAP score.
- `audio-process --input source=<asset>/outputs/audio-generation.json` (or `music-generation.json`) finishes the takes already made again, with their evidence, without running a model.
- The audio worker's timeout, when left at its 3600 s default, grows to 120 s per take, so a long prompt list is not killed at the hour mark. A timeout you set is kept.
- A JSON prompt list entry with `"prompt"` instead of `"text"` is read; an entry with neither, or a non-string value, is an error. Such entries used to be dropped without a word.
- An FFmpeg failure that prints nothing now names its exit code instead of ending the message with an empty reason; a take trimmed to nothing is reported as silent.

## 0.8.1 — 2026-11-15

Audit release: wrong results and silent failures fixed, nothing removed.

- `blender-qa` checks every mesh when `object` is empty, as documented. It used to look for `SM_Crate` (the pipeline's crate) in any `.blend` and fail with "objects not found". `object` also takes several names.
- `validate` and `export` keep the evidence only the run can make (`BLENDER-QA*`, `TEARDOWN-*`, `AUDIO-ASR/CLAP/LENGTH/LOOP/LYRICS/LISTEN`). They used to drop most of it, so an asset with a pending visual review or a song that ended early read as a plain `PASS`. Checks recomputed from the files (`GLB-*`, `IMG-*`, `AUDIO-001`–`006`, `PAGE-001`, `VIDEO-001`) are replaced, not duplicated.
- The structural GLB validator reports `GLB-001 FAIL` for JSON that parses but is not shaped like glTF, instead of crashing with a Python traceback (`validate`, `probe`, `glb-inspect`).
- Percent-encoded external image URIs (`my%20tex.png`) resolve; `GLB-012` no longer fails them.
- Triangle strips and fans are counted (n − 2 triangles). They counted as 0, so a strip mesh passed every triangle budget.
- A boolean `--set` value that is not `true/false/yes/no/on/off/1/0` is a usage error. `loop=ture` used to mean `false` silently.
- `--dry-run` lists the providers of every step: teardown recipes listed none, and the Khronos validator, Pillow and CLAP were missing.
- `audio-music --set url=...` uses only that ComfyUI. A dead explicit URL is an error (exit 4) instead of quietly sending the job to another server on a default port.
- A global npm `gltf-transform.cmd` on Windows is detected; it was reported as not installed.
- `true_peak=0` is honoured by `validate` instead of being read as unset.
- Ctrl+C during a run ends the job `CANCELLED` (the reserved state) instead of leaving it `RUNNING`.
- `status --last` returns the job started last even when several start within one second (`created_ns` in the job record, strictly increasing even where the system clock ticks in 15 ms steps).
- `inspect` and `status` refuse an id that is a path (`../x`, an absolute path) instead of reading outside the project.
- Providers are detected once per command or recipe run instead of on every lookup (about 1.3 s each); a `glb-inspect` run went from about 4 s to about 1.6 s.
- `probe` on a folder stops reading at its 5,000-file cap instead of listing and sorting the whole tree first.
- `Install.ps1` points the activate scripts and `pyvenv.cfg` at `.venv`, not the `.venv.new` staging folder, and no longer leaves a `pip.exe` that names a deleted path.
- `Update.ps1` stops on uncommitted changes, as its header always said.
- Removed unused helpers (`util.sha256_bytes`, `util.clamp_int`, `util.which`, `images.write_report`, `cli._print`, `providers._tree_size_files`).
- README: update and uninstall notes; typed `--set` values.

## 0.8.0 — 2026-11-14

- Add `audio-music`: songs and instrumentals from style tags, with optional lyrics, rendered by ACE-Step 1.5 through comfy-forge 0.8.0's `TOOLS/music.py`.
  - Each take gets its own seed. A take that fills the asked length beats one that stops early, CLAP breaks ties (when the sfx runtime is installed), and the kept take is finished to -16 LUFS stereo at 48 kHz.
  - New checks: `AUDIO-LENGTH` warns when the model ended the song early, and `AUDIO-LYRICS` stays `NOT_TESTED`.
- `loop=true` makes game-ready loops. It uses `bpm` and `time_signature` to cut the track to whole bars, keeps the first through the last full-level bar (dropping a quiet intro or fading outro), and crossfades the last bar into the first. `AUDIO-LOOP` reports the bars kept and warns about quiet bars inside the loop.
- Music needs no manual server start. `backend=auto` uses a running ComfyUI (`COMFYUI_URL`, 8188, or SwarmUI's 7820-7832). Otherwise it starts comfy-forge's own ComfyUI headless on a free local port for the job and stops it, process tree included, afterwards. `backend=running` and `backend=start` force either path.
- The comfy provider is now `comfy-forge` (the project renamed itself from comfy-kit):
  - `COMFY_FORGE_ROOT` and `integrations.comfy_forge` select it, and the old `COMFY_KIT_ROOT` / `comfy_kit` still work.
  - `providers.get("comfy-kit")` answers with it.
  - It reports `music.generate.delegated` when comfy-forge has its music generator.
  - The capability `comfy-kit-generation` is now `comfy-forge-images`.
- Minecraft export marks music and anything over 10 seconds `"stream": true` in `sounds.json`, and treats stereo music as correct rather than as a positional-sound warning.
- A recipe run with `--set name=...` names its asset after that name, instead of after the input file or the recipe.

## 0.7.1 — 2026-11-13

- blender-skills provider re-verified at **v1.3.1** (`b1b21df`): upstream validation and 72/72 headless tests pass on Blender 5.3.0, and AssetForge's real-Blender runner tests (LODs, auto-retopo, UV pack, texel density, mesh stats) pass against it. v1.3.1 tries voxel remesh first in auto-retopo, adds a review grid to QA shots and warns about UV seams; the command lines AssetForge passes did not change.

## 0.7.0 — 2026-11-13

- Add audio. `audio-voice` makes voice lines from one line or a lines file, `audio-sfx` makes sound effects from text prompts, and `audio-process` trims, levels, converts and measures audio you already have. Details: `docs/AUDIO.md`.
- `audio-voice` engines:
  - **Qwen3-TTS** (default): designs a voice from a description, auditions it and clones the best audition for every line, so a set keeps one voice. It also clones a supplied recording (`--input reference=` with `ref_text`).
  - **Dia 1.6B**: nonverbals such as `(laughs)` and `(gasps)`, and it takes the same reference voice.
  - **Kokoro**: fast preset voices.
- Every take is transcribed by Whisper, and the closest match to the text is kept (`AUDIO-ASR`).
- `audio-sfx` uses MOSS-SoundEffect v2 (48 kHz, up to 30 s). CLAP scores every take against its prompt and the best is kept (`AUDIO-CLAP`, calibrated on matching and mismatched prompts).
- Finishing trims edge silence, applies one fixed gain to a loudness target (voice -18 LUFS) or peak level under a -1 dBTP ceiling, and encodes to ogg, wav, mp3 or flac. Checks `AUDIO-001` to `AUDIO-006` cover decoding, silence, true peak, loudness, edge silence and format. `AUDIO-LISTEN` stays `NOT_TESTED`.
- `assetforge audio-setup [speech|sfx|kokoro]` builds one isolated uv runtime per dependency set under `~/.assetforge/audio` (or `ASSETFORGE_AUDIO_HOME`). It reuses AssetForge's own Python, installs the package set proven together on Windows, and smoke-tests each runtime. `--list` shows the state. The home avoids `AppData`, which sandboxed hosts redirect. Models download from Hugging Face on first use. All weights are Apache-2.0 or MIT.
- `doctor` and `providers` report `audio-speech`, `audio-sfx` and `audio-kokoro`, each with its engines, models and licences. A missing runtime names the setup command, and a recipe that needs it exits `4`.
- New export target `minecraft` packages finished sounds as `assets/<namespace>/sounds/<asset>/*.ogg` plus a `sounds.json` that groups numbered variants into one event. `--namespace` names the mod or pack. Stereo files get a positional-sound warning.
- `godot`, `roblox` and `generic` now export audio, with format, length, size and sample-rate rules from each engine's documentation.
- `validate` re-measures audio deliverables. `probe` reads audio files and folders and recommends `audio-process`.
- Engine fixes made inside the worker, without patching upstream:
  - MOSS's float32 DiT is stored in bf16. Under autocast it overflowed a 16 GB card at its native 30 s window; it now peaks near 10 GB.
  - MOSS's `seed` is passed through, so takes differ.
  - MOSS's compile and CUDA-graph calls run eagerly on Python 3.14.
  - Whisper input is resampled to 16 kHz first. transformers 4.57 otherwise returned dots for 44.1 kHz audio.
  - huggingface_hub's per-folder symlink race on Windows is settled before any download.

## 0.6.0 — 2026-11-13

- Add `teardown-build`: a teardown simulator folder (main.js and its imports) becomes one offline HTML page through upstream [teardown](https://github.com/elvarofficial/teardown), with three.js and fonts inlined. The folder is copied into the asset with its layout; links are refused and the copy is capped at 2,000 files / 512 MiB. A folder of sims takes `--set entry=NAME`, which is how upstream's own pages import their shared parts.
- Add `teardown-film`: the page rendered frame by frame in headless Chromium to an MP4 (encoded with the FFmpeg AssetForge found) or, with `stills`, to a labelled review sheet. `to`, `fps`, `size` and `stills` are checked before anything runs. `TEARDOWN-RENDER` passes only when frames were rendered; `TEARDOWN-VISUAL` stays `NOT_TESTED` until someone looks.
- teardown is a detected provider (`TEARDOWN_ROOT`, standard skill folders, declared tool roots). It is available only after `npm install` in its checkout, and a missing Chromium is reported with the command that installs it.
- `validate` checks pages and videos: `PAGE-001` (one file, has a script, loads nothing from the network) and `VIDEO-001` (a real MP4 container). A page-only asset no longer fails `ASSET-001`.
- `capabilities` lists `teardown-build` and `teardown-film` instead of the planned `teardown-simulation`; FFmpeg is now used by a recipe.

## 0.5.1 — 2026-11-13

- Providers brought up to date and re-verified: blender-skills **v1.3.0** (Blender 5.3 support; upstream validation and 69/69 headless tests pass on Blender 5.3.0) and img2threejs **v2.0.1** (upstream suite has no assertion failures; probe and codegen recipes succeed). glTF-Transform 4.5.1 and gltf-validator 2.0.0-dev.3.10 are already the latest releases.
- blender-skills is found in a declared tool root (`ASSETFORGE_ROOTS`, the profile's tool roots, a project's integration roots) like comfy-kit and img2threejs. Before this a plain clone beside other tools was reported missing unless `BLENDER_SKILLS_ROOT` was set.
- blender-skills reports its release from the upstream plugin manifest; v1.3.0 shipped with 1.2.0 per-skill metadata and was shown as 1.2.0. The per-skill value is kept as `details.skill_version`.
- img2threejs reports its version from its `SKILL.md`; it was always shown as unknown.
- A set `COMFY_KIT_ROOT` or `IMG2THREEJS_ROOT` that points at the wrong folder is now reported with the markers it lacks. Before this, detection quietly used another copy it found elsewhere.
- Fix: `blender-pipeline` left Blender's save backup `blender-asset-material.blend1` in the asset's outputs. Backups from saving over a project-owned `.blend` are removed; the pre-step file is already its own artifact.
- CI uses `actions/checkout@v7` and `actions/setup-python@v7`; Dependabot proposes Action updates monthly.
- `docs/UPSTREAM-EVALUATIONS.md` records the 2026-11-13 recheck and decisions for new companion tools (CLI-Anything, MCP for Unity, Unity-MCP, awesome-gamedev-agent-skills, OBS MCP and others). None is vendored.

## 0.5.0 — 2026-11-12

- Add `assetforge engine-check FILE.glb`: a real engine import. Godot 4 runs headless against a throwaway project, imports the GLB, then loads and instantiates the imported scene and reports the node classes, meshes, skeletons and animation names it found. `PASS` needs at least one mesh and no engine error line; a file Godot cannot import fails with exit 5. Rendering, on-screen materials, animation playback and physics are listed as not tested. The source file is copied, never modified, and the temporary project is removed.
- Godot, FFmpeg and ImageMagick are detected providers. `doctor`, `providers` and `capabilities` report each with its version, path and what it is for. Godot is found through `GODOT_EXE`, PATH, the winget package folder, the Godot install folders, Steam and declared tool roots; FFmpeg and ImageMagick through `FFMPEG_EXE` / `MAGICK_EXE`, PATH and their usual install folders. A program is accepted only when its own version output names it.
- FFmpeg and ImageMagick are reported as detected only: no recipe calls them yet. `AGENTS.md` and `docs/PROVIDERS.md` say what an agent uses each for and give the commands.
- `AGENTS.md` gains the tool map: which external program does which job, and what to ask the user to install when one is missing.

## 0.4.1 — 2026-11-12

- Blender is found wherever it was installed: every Steam library (not only the default one), the folder the Windows uninstall registry records, the Blender Foundation folders under any `ProgramFiles`, and a portable copy under a declared tool root (`ASSETFORGE_ROOTS`, the profile's tool roots, a project's integration roots). `BLENDER_EXE` still wins.
- A `blender.bat` that starts a Hermes profile is no longer probed as Blender. Hermes writes one wrapper per profile, named after the profile, into a folder on PATH; a profile called `blender` made the doctor start a chat client and wait out the timeout before it tried the real program.
- When Blender is missing the doctor says where it looked and names `BLENDER_EXE`, instead of "not installed or not on PATH".

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
