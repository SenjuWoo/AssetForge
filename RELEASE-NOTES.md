# AssetForge 0.9.1 — Sound batches that share a GPU

A patch release for long voice and sound-effect batches. Nothing was removed and no format changed.

## Fixed

- **Variants are variants.** Lines with the same text in one `audio-voice` or `audio-sfx` run used to come out as identical copies. Each repeat now gets its own seeds; runs without repeated text make exactly the audio they made before.
- **One audio job on the GPU at a time.** Two AssetForge audio jobs started together no longer fill the card and stall: the second waits for the first (`ASSETFORGE_AUDIO_GPU_WAIT`, default four hours; `0` fails at once with `GPU busy`). The lock is released when its holder exits or is killed. It covers AssetForge's own audio workers, not ComfyUI or other programs.
- **Saved takes are not lost.** A batch that dies part-way now says how many takes it saved, where, and the `audio-process` command that finishes them.

## Also

- A new README with real terminal runs and the images a real pipeline run produced. Capability and provider detail moved to `docs/CAPABILITIES.md`.

## Verified

Windows 11, Python 3.14, Blender 5.3: the full local suite with every provider present, including new tests for the seeds, the lock (two concurrent stub workers never overlap; a zero wait fails with `GPU busy`) and the saved-takes message from a worker that dies mid-batch.

## Not verified

The GPU lock was not exercised against a live model contention, and no new audio was generated for this release.
