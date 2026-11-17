# AssetForge 0.8.2 — Sound batches survive a bad take

A fix release for generated audio. Nothing was removed and no format changed.

## Fixed

- **One bad take no longer fails the batch.** In `audio-voice`, `audio-sfx` and `audio-music`, a chosen take that cannot be finished (silent after trimming, or refused by FFmpeg) is replaced by the next-best take of the same item, reported as `AUDIO-TAKE` `WARNING` with that take's own score. An item with no usable take is marked `AUDIO-FINISH` `FAIL` and every other item is still finished. Before, one such take failed the whole asset after the generation had already run.
- **Silent takes are not picked.** A take whose loudest sample is under -40 dBFS never wins while another take has sound, even when it matched a prompt like "a quiet sigh" better.
- **Long batches are not cut off at one hour.** Left at its default, the worker timeout grows with the number of takes; a timeout you set is kept.
- **No silently dropped prompts.** JSON prompt lists accept `"prompt"` as well as `"text"`; an entry with neither is an error instead of being skipped.
- **Clearer FFmpeg errors.** A failure that prints nothing names the exit code; a take trimmed to nothing is reported as silent.

## New

- **Finish again without generating:** `assetforge run audio-process --input source=<asset>/outputs/audio-generation.json` (or `music-generation.json`) finishes the existing takes with new settings, keeping their CLAP or transcript evidence.

## Verified

Windows 11, Python 3.14, FFmpeg 9.0.2 and the audio runtimes: the full suite passed with every provider present, including new tests that failed before the fixes (a silent best take, an item with no usable take, take ranking, resume from the generation report, prompt-list parsing).

## Not verified

No person listened to the generated audio. No engine other than Godot was launched, and rendering in Godot is not tested.
