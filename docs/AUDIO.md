# Audio

AssetForge makes voice lines, sound effects and music with local open-weight models, then trims, levels, encodes and measures them. It can also finish audio you already have. Nothing is sent to a hosted service.

| Recipe | What it makes | Engine |
| --- | --- | --- |
| `audio-voice` | Voice lines from text, one line or a whole lines file | Qwen3-TTS (default), Dia, Kokoro |
| `audio-sfx` | Sound effects from text prompts | MOSS-SoundEffect v2 |
| `audio-music` | Songs and instrumentals from style tags, with optional lyrics | ACE-Step 1.5 through comfy-forge |
| `audio-process` | Trimmed, levelled, converted copies of existing audio | FFmpeg only |

`export --target minecraft` packages finished sounds for a resource pack or mod, with a `sounds.json`. The `godot`, `roblox` and `generic` targets also take audio.

## Setup

```bat
assetforge.cmd audio-setup            :: all three runtimes
assetforge.cmd audio-setup speech     :: or one: speech, sfx, kokoro
assetforge.cmd audio-setup --list     :: what is installed; changes nothing
```

`audio-setup` uses [uv](https://docs.astral.sh/uv/) to build one isolated Python environment per runtime under `~/.assetforge/audio/envs/` (or the folder in `ASSETFORGE_AUDIO_HOME`). It uses the Python AssetForge itself runs on and does not download another one. It installs the exact package set that was proven together (`src/assetforge/data/audio/*.txt` on Windows) and PyTorch from the PyTorch index (CUDA when `nvidia-smi` works, otherwise CPU; force it with `--device`). Then it runs a smoke test in each runtime, and only a runtime that passes counts as installed.

Model weights download on first use into `~/.assetforge/audio/hf`. Expect about 4 GB per Qwen3-TTS model, 3 GB for Dia, 1.6 GB for Whisper, 5 GB for MOSS-SoundEffect v2 and its text encoder, and 0.3 GB for Kokoro.

The home sits outside `AppData` on purpose. Sandboxed hosts, such as an MSIX-packaged desktop app, redirect writes to `AppData`, and a runtime written there would be invisible to every other shell.

| Runtime | Engines | Models | Licences |
| --- | --- | --- | --- |
| `speech` | `qwen3-tts`, `dia`, Whisper check | Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign and -Base, nari-labs/Dia-1.6B-0626, openai/whisper-large-v3-turbo | Apache-2.0, Apache-2.0, MIT |
| `sfx` | `moss-sfx`, CLAP check | OpenMOSS-Team/MOSS-SoundEffect-v2.0, laion/larger_clap_general | Apache-2.0 |
| `kokoro` | `kokoro` | hexgrad/Kokoro-82M | Apache-2.0 |

All the model weights above allow commercial use. Clone only voices you have the rights to.

## Voice lines

```bat
assetforge.cmd run audio-voice --input lines=princess.txt --set "voice=A young woman with a warm, bright, slightly haughty voice, like a pampered village princess."
assetforge.cmd run audio-voice --set engine=dia --input lines=grunts.txt --input reference=princess-reference.wav --set "ref_text=Hello there. This is how I sound..."
assetforge.cmd run audio-voice --set engine=kokoro --set "text=Welcome to my village." --set name=welcome
```

A lines file is a text file with one `name: text` line per sound. A JSON object (`{"greet1": "Hello."}`) or a JSON list also works, and plain lines are numbered. Names become file names.

- **`qwen3-tts`** (default). Describe the voice in `voice`. AssetForge designs a reference voice from that description, auditions a few seeds, keeps the one Whisper hears most clearly, and then clones that reference for every line. A whole set of lines keeps one voice. To clone a recording you have instead, pass `--input reference=<wav>` with `ref_text` set to its exact words. Ten languages are supported (`language`).
- **`dia`**. Use it for nonverbal sounds written in parentheses: `(laughs)`, `(gasps)`, `(sighs)`, `(screams)`, `(coughs)`. It takes a reference the same way, so a voice designed by Qwen3-TTS can carry over (the `reference.wav` in the voice asset's `work/voice/` folder). Dia's takes vary more than Qwen3-TTS's, so give it more takes.
- **`kokoro`**. Use it for fast preset voices such as `af_heart`, `af_bella`, `bf_emma` and `am_adam`. The first letter of the voice name sets the accent (`a` American, `b` British). It runs on a CPU, so it fits quick placeholders and narration.

Each line gets `takes` attempts (default 3; 1 for Kokoro). Whisper transcribes every take, and the take whose words match the text best wins. Length, dead air, clipping and pitch distance from the reference break ties. All takes stay in the asset as `audio-take` artifacts, so a person can pick a different one.

## Sound effects

```bat
assetforge.cmd run audio-sfx --set "prompt=A heavy wooden door creaking open slowly in a stone hall" --set name=door --set seconds=3
assetforge.cmd run audio-sfx --input prompts=sfx.txt --set takes=4
```

Describe the sound the way a caption would: the source, the action, the space, and how long it lasts. MOSS-SoundEffect v2 writes 48 kHz audio up to 30 seconds long. It always denoises a full 30-second window and then crops it, so a take costs the same whatever its length: about 17 seconds at 100 steps on an RTX 4080 SUPER, with peak VRAM near 10 GB. `steps` (default 100) trades speed for detail, and `cfg` (default 4.0) controls how closely it follows the prompt. CLAP scores every take against its prompt, and the take with the best score is kept.

## Music

```bat
assetforge.cmd run audio-music --set "tags=medieval village tavern music, lute, wooden flute, light hand drums, cheerful" --set seconds=60 --set bpm=100 --set "key=D major" --set name=tavern
assetforge.cmd run audio-music --input song.txt --set "tags=medieval folk song, female vocals, lute, tambourine, upbeat" --set seconds=90
```

Music comes from [comfy-forge](https://github.com/SenjuWoo/comfy-forge) 0.8.0 or later. It owns ACE-Step 1.5 and its ComfyUI; install the weights there with `TOOLS\Install-MusicModels.ps1 -Set aio`. AssetForge sends the job, keeps every take, scores each against the tags with CLAP (when the `sfx` runtime is installed), and finishes the best one to -16 LUFS stereo at 48 kHz.

- **Backend.** By default AssetForge uses a ComfyUI that is already running (SwarmUI's backend counts). If none is, it starts comfy-forge's ComfyUI headless on a free local port for the job and stops it afterwards. Startup took 18 s in testing. `--set backend=running` refuses to start one.
- **Lyrics.** Use a lyrics file or `--set lyrics=...` with `[Verse]` and `[Chorus]` tags. With no lyrics, the track is instrumental. The sung words are not checked (`AUDIO-LYRICS NOT_TESTED`): speech recognition is unreliable on singing.
- **Length.** ACE-Step sometimes ends a song before the asked length and fills the rest with silence. Takes that fill the length are preferred, and `AUDIO-LENGTH` warns when the kept take is under 90% of the request. Run more takes, or pass `trim=false` to keep the silence.
- **Loops.** `--set loop=true` turns the track into a seamless loop for game music, using `bpm` and `time_signature` to find the bars. The loop runs from the first to the last bar at full level, so a quiet intro or a fading outro is left out. Its last bar is crossfaded into its first, so playback wraps without a gap or a click. `AUDIO-LOOP` reports which bars were kept, and warns when quiet bars sit inside the loop. The loop needs at least 4 full bars.
- **Speed.** On an RTX 4080 SUPER with the `aio` variant, a 40 s song took about 15 s per take through a running backend.

## Finishing

Every audio recipe ends with the same step:

1. Trim silence from both ends (below -50 dB) and fade the cut ends by a few milliseconds.
2. Apply one fixed gain to reach `loudness` (voice default -18 LUFS, music -16 LUFS; SFX and processing default `peak`), never passing the `true_peak` ceiling (default -1 dBTP). No compressor or limiter touches the sound. When the ceiling stops the gain early, AUDIO-004 says the file came out quieter.
3. Convert to `sample_rate` (default 44100) and `channels` (default 1, mono), and encode to `format`: `ogg` (default), `wav`, `mp3` or `flac`.

## Checks

| ID | Meaning |
| --- | --- |
| AUDIO-001 | The file decodes; codec, rate, channels and length |
| AUDIO-002 | It is not silent |
| AUDIO-003 | True peak is under the ceiling; FAIL above -0.1 dBTP (clipping) |
| AUDIO-004 | Integrated loudness is within 1.5 LU of the target; NOT_TESTED for clips too short to measure |
| AUDIO-005 | Edge silence: WARNING above 0.25 s before or 0.6 s after |
| AUDIO-006 | Sample rate and channels are as requested |
| AUDIO-ASR | Whisper's transcript against the line: PASS from 85% word match, WARNING from 60%, otherwise FAIL. NOT_TESTED for a line with no words |
| AUDIO-CLAP | CLAP similarity between prompt and sound: PASS from 0.30, WARNING from 0.20, otherwise FAIL. In calibration on 2026-11-13, six MOSS takes scored 0.29 to 0.49 against their own prompts and at most 0.26 (mostly under 0.18) against unrelated ones |
| AUDIO-LENGTH | Music: PASS when the finished take is at least 90% of the asked length (not used for loops) |
| AUDIO-LOOP | Music with `loop=true`: the bars kept and the intro or outro bars left out. WARNING when quiet bars (more than 6 dB under the median bar) sit inside the loop |
| AUDIO-LYRICS | Music with lyrics: always NOT_TESTED, because the sung words are not checked |
| AUDIO-LISTEN | Always NOT_TESTED: no person listened |

These checks show the file is well-formed, sits at sane levels, and says the words or roughly fits the prompt. They do not show that it sounds good or fits the game. Listen before you ship. A FAIL on AUDIO-ASR usually means the model babbled or swallowed a word: run more takes, or rephrase the line.

## Export

```bat
assetforge.cmd export ASSET --target minecraft --namespace villageprincess
assetforge.cmd export ASSET --target roblox --dry-run
```

- **minecraft**: writes `assets/<namespace>/sounds/<asset>/*.ogg` and `assets/<namespace>/sounds.json`. Numbered files (`greet1`, `greet2`) become variants of one event (`<asset>.greet`), and the game picks one at random. Music and anything over 10 seconds is marked `"stream": true`, so the game streams it from disk instead of loading it whole. Music keeps its stereo. The target accepts Ogg only, and a stereo file gets a WARNING because Minecraft plays stereo without distance falloff.
- **roblox**: accepts `.mp3`, `.ogg`, `.wav` and `.flac` under 20 MB and 7 minutes, at most 48 kHz (Creator Hub, checked 2026-11-13).
- **godot**: accepts WAV, Ogg Vorbis and MP3. Godot suggests WAV for short repeated effects and Ogg for music, speech and long effects.

Engine import stays NOT_TESTED: an export launches no game.

## Known limits

- A loop's crossfade is equal-power, which suits two different bars of music. Nobody listened to the seams, so check a loop by ear before shipping it.
- MOSS-SoundEffect v2 runs eagerly. Upstream compiles its sampler with `torch.compile` and CUDA graphs, which PyTorch does not support on Python 3.14 and which need Triton, absent on Windows. The worker turns both off and stores the DiT weights in bf16 so the 30-second window fits in about 10 GB of VRAM. Generation is slower than upstream's published numbers.
- Dia sometimes keeps talking after the line ends, or turns a short gasp into repeated sounds. In testing this happened without a reference voice. With the Qwen-designed reference, both test lines passed at a 100% word match. The transcript check catches the worst cases, and more takes help.
- Whisper can hallucinate on nonverbal-only audio. Lines with no words are not scored on words.

## Alternatives considered (2026-11-13)

- **Dia2 (1B/2B, Apache-2.0)**: streaming successor to Dia, English only. Its voices vary per generation without a prefix, and its CLI and server are still listed as upcoming. Dia 1.6B in transformers was kept.
- **Chatterbox (MIT)**: good cloning, but every output carries Resemble's PerTh watermark. Qwen3-TTS covers cloning without one and adds voice design.
- **MOSS-TTS family (8B, Apache-2.0)**: strong, but 8B models are heavy for one GPU next to a game. Only its 1.3B sound-effect model is used.
- **Stable Audio Open / Stable Audio 3.0 SFX**: Stability AI Community licence, free only under a revenue threshold. MOSS-SoundEffect v2 (Apache-2.0) was chosen.
- **soundbox**: a desktop app wrapping many audio models, with an MCP server. It was not adopted: the Windows installer is unsigned, the local API has no authentication, and the project is young. Recheck if it ships signed releases.
