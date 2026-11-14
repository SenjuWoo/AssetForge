# AssetForge 0.8.0 — Music

0.7.0 added voices and sound effects. This release adds music. Describe a style, optionally add lyrics, and `audio-music` renders the track with ACE-Step 1.5 through comfy-forge. Then it is checked, levelled and packaged like every other sound.

## Included

- **`audio-music`:** songs and instrumentals from style tags, with optional lyrics.
  - It runs on comfy-forge's ComfyUI: a running one (SwarmUI's backend counts), or one AssetForge starts for the job and stops afterwards.
  - Several takes are made. The one that fills the asked length and best matches the tags (CLAP) is kept, then finished to -16 LUFS stereo.
- **Loops for game music:** `loop=true` cuts the track to whole bars, leaves out a quiet intro or outro, and crossfades the last bar into the first so it repeats without a seam.
- **`AUDIO-LENGTH`:** says when the model ended a song early.
- **Minecraft export:** music is streamed (`"stream": true`) and keeps its stereo.
- **comfy-forge naming:** the provider uses comfy-forge's current name, and the old comfy-kit variable and keys still work.
- Everything from 0.7.x: Qwen3-TTS, Dia and Kokoro voices; MOSS-SoundEffect v2 effects; `audio-process`; blender-skills v1.3.1.

## Verified

Windows 11, RTX 4080 SUPER, comfy-forge 0.8.0, ComfyUI 0.44.0, ACE-Step 1.5 `aio`:

- **Instrumental, temporary ComfyUI:** 45 s asked. The backend started in 18 s and was stopped afterwards. Two takes; the kept one scored CLAP 0.44 and -15.97 LUFS.
- **Vocal song, running SwarmUI backend:** 40 s asked with a lyrics file, done in 34 s for two takes. The kept take scored CLAP 0.41. Both takes ended about 5 s early, which `AUDIO-LENGTH` reported as a WARNING.
- **Loop:** 60 s at 90 bpm with `loop=true` gave a 50.7 s loop of 19 bars from bars 1 to 20. The fading partial bar at the end was left out, and the kept take scored CLAP 0.38.
- **CLAP on music:** the right tags scored 0.36 to 0.44, and unrelated tags at most 0.03.
- **Tests:** the full suite passed. Stub comfy-forge and stub ComfyUI tests cover the music contract on any machine.

## Not verified

- **Listening and lyrics:** nobody listened to the tracks or the loop seams, and the sung words were not checked.
- **Loading in a game:** no game loaded the exported files.
- **Other variants:** only `aio` was rendered; the others need their weights installed in comfy-forge.
