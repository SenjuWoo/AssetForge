# AssetForge 0.8.1 — Audit fixes

A maintenance release from a full audit of 0.8.0. Nothing was removed and no format changed; results that were wrong or silently weaker are now correct.

## Fixed

- **`blender-qa` on your own `.blend`:** an empty `object` now checks every mesh, as documented. It used to look for the pipeline's `SM_Crate` and fail on any other file.
- **Validation keeps the run's evidence:** `validate` and `export` no longer drop checks only the run can make (Blender QA and visual review, teardown render and review, transcript, CLAP, length, loop and lyrics). An asset with a pending review or an early-ending song is no longer reported as a plain `PASS`.
- **Malformed GLB files** get a `GLB-001 FAIL` report instead of a Python traceback.
- **Truer mesh numbers:** triangle strips and fans are counted, so they can no longer slip under a triangle budget; percent-encoded image URIs resolve.
- **No silent defaults:** a misspelt boolean (`loop=ture`) is an error, not `false`; an explicit `audio-music url=` that does not answer is an error, not a quiet switch to another ComfyUI; `true_peak=0` is respected.
- **Dry runs** list every provider a recipe calls, including teardown's and the optional checkers.
- **Jobs:** Ctrl+C ends a job `CANCELLED` instead of `RUNNING`; `status --last` is exact within one second; ids that are paths are refused.
- **Windows:** a global npm `gltf-transform.cmd` is detected; the installer's activate scripts point at `.venv`; `Update.ps1` stops on uncommitted changes.

## Faster

- Providers are detected once per command instead of on every lookup: a `glb-inspect` run drops from about 4 s to about 1.6 s.
- `probe` stops reading a large folder at its 5,000-file cap.

## Verified

Windows 11, Python 3.14, Blender 5.3.0, Godot 4.7.2, FFmpeg 9.0.2, glTF-Transform 4.5.1, the Khronos validator, teardown, and the three audio runtimes: the full suite passed with every provider present, plus 30 new regression tests that failed before their fixes. `Install.ps1` was run twice in a copy of the release in a folder whose name has spaces, parentheses and `!`.

## Not verified

The limits of 0.8.0 stand: no engine other than Godot was launched, no person listened to generated audio, and rendering in Godot is not tested.
