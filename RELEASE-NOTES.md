# AssetForge 0.7.0 — Sound

AssetForge made meshes, textures and simulator films. It now makes the sounds too: voice lines and sound effects from text, with local open-weight models and the same evidence rules as every other recipe.

## Included

- `audio-voice`:
  - Qwen3-TTS designs a voice from a description and keeps it across a whole set of lines, or clones a recording you supply.
  - Dia adds laughs, gasps and other nonverbals in the same voice.
  - Kokoro gives fast preset voices.
  - Whisper checks the words of every take.
- `audio-sfx`: MOSS-SoundEffect v2 makes 48 kHz effects from a prompt. CLAP checks every take against the prompt.
- `audio-process`: trims, levels, converts and measures audio you already have.
- `assetforge audio-setup` installs the three local runtimes with uv and smoke-tests them. All the model weights are Apache-2.0 or MIT.
- Exporting audio: the new `minecraft` target writes `sounds.json` and Ogg files, and the `godot`, `roblox` and `generic` targets now take audio.

## Verified

Windows 11, RTX 4080 SUPER, Python 3.14, PyTorch 2.9.1 (CUDA 12.8), FFmpeg 9.0.2:

- **Qwen3-TTS:** designed a voice from a description and cloned it for three lines. All three had a 100% Whisper word match and came out within 0.25 LU of -18 LUFS.
- **Dia:** given that designed voice as a reference, it spoke a gasp line and a laugh line, both at a 100% word match.
- **Kokoro:** one line at a 100% word match.
- **MOSS-SoundEffect v2:** made a sword swing and a door creak, three takes each, with CLAP 0.49 and 0.41 for the kept takes. Each take took about 17 seconds.
- **Tests:** the full AssetForge suite passed, with stub runtimes covering the contract on any machine.

## Not verified

- **Listening:** nobody listened to the generated sounds. `AUDIO-LISTEN` stays `NOT_TESTED`. Listen before you ship.
- **Loading in a game:** no Minecraft, Godot or Roblox game loaded the exported sounds.
- **Linux and macOS:** the audio runtimes were not run there. `audio-setup` resolves the top-level pins on those systems instead of the Windows lock files.
- **Music:** not covered. ACE-Step 1.5 is the planned candidate.
