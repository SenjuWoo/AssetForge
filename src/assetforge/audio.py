"""Audio runtimes, finishing and checks.

AssetForge does not ship model code. `assetforge audio-setup` builds isolated
runtimes with uv under the audio home (default `~/.assetforge/audio`, or
ASSETFORGE_AUDIO_HOME), outside AppData on purpose: a sandboxed host such as
an MSIX app redirects AppData writes, and the runtimes must be visible to
every shell. Generation runs `audio_worker.py` inside a runtime; finishing and
measuring use FFmpeg. AssetForge's own environment stays dependency-free.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

from .util import now_iso, run

TORCH = ["torch==2.9.1", "torchaudio==2.9.1"]
TORCH_INDEX = {"cuda": "https://download.pytorch.org/whl/cu128", "cpu": "https://download.pytorch.org/whl/cpu"}

# One runtime per dependency set; the pins are the set proven together on
# Python 3.14 (2026-11-13). Engines name what the worker can run in each.
RUNTIMES = {
    "speech": {
        "title": "Speech: Qwen3-TTS voice design and cloning, Dia nonverbal dialogue, Whisper transcript check",
        "packages": ["qwen-tts==0.1.1", "soundfile==0.14.0", "hf-xet==1.8.0"],
        "modules": ["qwen_tts", "transformers"],
        "engines": ["qwen3-tts", "dia", "asr"],
        "models": ["Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", "Qwen/Qwen3-TTS-12Hz-1.7B-Base", "nari-labs/Dia-1.6B-0626", "openai/whisper-large-v3-turbo"],
        "licenses": "Apache-2.0 (Qwen3-TTS, Dia); MIT (Whisper)",
    },
    "sfx": {
        "title": "Sound effects: MOSS-SoundEffect v2, CLAP prompt match",
        "packages": [
            "numpy==2.5.4", "einops==0.8.2", "pillow==13.0.0", "tqdm==4.70.1", "safetensors==0.8.0",
            "transformers==4.57.1", "diffusers==0.37.1", "ftfy==6.3.1", "regex==2026.11.9", "soundfile==0.14.0",
            "imageio==2.38.1", "descript-audiotools==0.7.2", "hf-xet==1.8.0",
        ],
        # Installed without its own pins: upstream pins numpy 1.26 and gradio,
        # which do not install on Python 3.14 and are not needed to infer.
        "no_deps": ["moss-soundeffect-v2 @ git+https://github.com/OpenMOSS/MOSS-TTS.git@934d6826b084c46a0d033402174d5f8ac4ed2519#subdirectory=moss_soundeffect_v2"],
        "modules": ["moss_soundeffect_v2", "transformers"],
        "engines": ["moss-sfx", "clap"],
        "models": ["OpenMOSS-Team/MOSS-SoundEffect-v2.0", "laion/larger_clap_general"],
        "licenses": "Apache-2.0 (MOSS-SoundEffect v2, CLAP)",
    },
    "kokoro": {
        "title": "Fast voice: Kokoro-82M preset voices",
        "packages": [
            "kokoro==0.9.4", "soundfile==0.14.0", "hf-xet==1.8.0",
            # misaki asks spaCy to download this at first use, and spaCy then
            # installs into whatever Python it finds; ship it in the runtime.
            "en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl",
        ],
        "modules": ["kokoro"],
        "engines": ["kokoro"],
        "models": ["hexgrad/Kokoro-82M"],
        "licenses": "Apache-2.0",
    },
}

ENGINE_RUNTIME = {engine: name for name, spec in RUNTIMES.items() for engine in spec["engines"]}
SPEECH_ENGINES = ("qwen3-tts", "dia", "kokoro")
AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3", ".flac", ".m4a", ".aac", ".opus", ".aif", ".aiff"}
FORMATS = {
    "ogg": ["-c:a", "libvorbis", "-q:a", "6"],
    "wav": ["-c:a", "pcm_s16le"],
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "flac": ["-c:a", "flac"],
}
MARKER = "assetforge-runtime.json"


class AudioError(RuntimeError):
    pass


def home() -> Path:
    value = os.environ.get("ASSETFORGE_AUDIO_HOME", "").strip()
    return Path(os.path.expandvars(os.path.expanduser(value))) if value else Path.home() / ".assetforge" / "audio"


def hf_home() -> Path:
    return home() / "hf"


def runtime_dir(name: str) -> Path:
    return home() / "envs" / name


def runtime_python(name: str) -> Path:
    folder = runtime_dir(name)
    return folder / "Scripts" / "python.exe" if sys.platform == "win32" else folder / "bin" / "python"


def lock_file(name: str) -> Path:
    return Path(__file__).resolve().parent / "data" / "audio" / f"{name}.txt"


def worker_path() -> Path:
    """The worker script. ASSETFORGE_AUDIO_WORKER swaps in another script that
    speaks the same request/result protocol (the tests use a stub)."""
    override = os.environ.get("ASSETFORGE_AUDIO_WORKER", "").strip()
    return Path(override) if override else Path(__file__).resolve().parent / "audio_worker.py"


def runtime_state(name: str) -> dict:
    """What `audio-setup` proved about one runtime. A runtime is available
    only after its smoke test passed and wrote the marker."""
    spec = RUNTIMES[name]
    python = runtime_python(name)
    marker = runtime_dir(name) / MARKER
    state = {
        "id": f"audio-{name}",
        "title": spec["title"],
        "kind": "runtime",
        "path": str(python) if python.exists() else None,
        "version": None,
        "available": False,
        "capabilities": [f"audio.{engine}" for engine in spec["engines"]],
        "details": {"runtime": name, "engines": spec["engines"], "models": spec["models"], "licenses": spec["licenses"], "home": str(home())},
        "reason": "",
        "use": "",
    }
    if not python.exists():
        state["reason"] = f"not installed; run `assetforge audio-setup {name}`"
        return state
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state["reason"] = f"runtime exists but its smoke test has not passed; run `assetforge audio-setup {name}`"
        return state
    state["available"] = True
    state["version"] = data.get("torch")
    state["details"].update({k: data.get(k) for k in ("cuda", "gpu", "modules", "installed", "packages")})
    if not data.get("cuda"):
        state["reason"] = "runs on CPU: generation is slow"
    return state


def uv_path() -> str | None:
    found = shutil.which("uv")
    if found:
        return found
    for candidate in (Path.home() / ".local" / "bin" / ("uv.exe" if sys.platform == "win32" else "uv"),
                      Path.home() / ".cargo" / "bin" / ("uv.exe" if sys.platform == "win32" else "uv")):
        if candidate.is_file():
            return str(candidate)
    return None


def base_python() -> str:
    """The interpreter the runtimes are built from: the one AssetForge itself
    runs on, so no second Python is downloaded."""
    return getattr(sys, "_base_executable", None) or sys.executable


def _gpu_present() -> bool:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return False
    return run([smi, "-L"], timeout=20)["returncode"] == 0


def run_worker(name: str, request: dict, work_dir: Path, timeout: float) -> dict:
    """Run one worker job in runtime `name`; return its result or raise with
    the worker's own error and the tail of its log."""
    python = runtime_python(name)
    if not python.exists():
        raise AudioError(f"audio runtime {name!r} is not installed; run `assetforge audio-setup {name}`")
    work_dir.mkdir(parents=True, exist_ok=True)
    request_path = work_dir / "request.json"
    result_path = work_dir / "result.json"
    if result_path.exists():
        result_path.unlink()
    request_path.write_text(json.dumps(request, indent=1), encoding="utf-8")
    env = {
        "HF_HOME": str(hf_home()),
        "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "TORCHDYNAMO_DISABLE": "1",
        "PYTHONIOENCODING": "utf-8",
        "TOKENIZERS_PARALLELISM": "false",
    }
    proc = run([str(python), "-I", str(worker_path()), str(request_path)], timeout=timeout, cwd=work_dir, env=env)
    (work_dir / "worker.log").write_text((proc.get("stdout") or "") + (proc.get("stderr") or ""), encoding="utf-8", errors="replace")
    if proc.get("timed_out"):
        raise AudioError(f"audio worker timed out after {timeout:g}s; see {work_dir / 'worker.log'}")
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        tail = "\n".join((proc.get("stderr") or proc.get("error") or "").strip().splitlines()[-12:])
        raise AudioError(f"audio worker wrote no result (exit {proc.get('returncode')}): {tail}") from None
    if not result.get("ok"):
        raise AudioError(f"audio worker failed: {result.get('error')}; see {work_dir / 'worker.log'}")
    return result


def setup(names: list[str], device: str = "auto", log=print) -> list[dict]:
    """Create or update runtimes with uv, then smoke-test each. Idempotent:
    uv only changes what differs from the pins."""
    uv = uv_path()
    if not uv:
        raise AudioError("uv is not on PATH; install uv (https://docs.astral.sh/uv/) and run audio-setup again")
    if device == "auto":
        device = "cuda" if _gpu_present() else "cpu"
    results = []
    for name in names:
        spec = RUNTIMES[name]
        folder = runtime_dir(name)
        python = runtime_python(name)
        steps = []
        if not python.exists():
            steps.append(("create the runtime", [uv, "venv", "--python", base_python(), str(folder)]))
        steps.append((f"torch for {device}", [uv, "pip", "install", "--python", str(python), *TORCH, "--index-url", TORCH_INDEX[device]]))
        # On Windows the full frozen set that was proven together is installed;
        # elsewhere uv resolves the top-level pins.
        lock = lock_file(name)
        if sys.platform == "win32" and lock.is_file():
            steps.append((f"packages from {lock.name}", [uv, "pip", "install", "--python", str(python), "-r", str(lock)]))
        else:
            steps.append(("packages", [uv, "pip", "install", "--python", str(python), *spec["packages"]]))
        if spec.get("no_deps"):
            steps.append(("pinned source packages", [uv, "pip", "install", "--python", str(python), "--no-deps", *spec["no_deps"]]))
        entry = {"runtime": name, "path": str(folder), "device": device, "ok": False}
        for label, cmd in steps:
            log(f"[{name}] {label}")
            proc = run(cmd, timeout=3600)
            if proc["returncode"] != 0:
                tail = "\n".join((proc.get("stderr") or proc.get("error") or "").strip().splitlines()[-15:])
                entry["error"] = f"{label} failed: {tail}"
                break
        else:
            try:
                smoke = run_worker(name, {"job": "smoke", "engine": name, "modules": spec["modules"]}, folder / "smoke", timeout=600)
            except AudioError as exc:
                entry["error"] = str(exc)
            else:
                marker = {k: smoke.get(k) for k in ("torch", "cuda", "gpu", "modules")}
                marker.update({"installed": now_iso(), "device": device, "packages": spec["packages"] + spec.get("no_deps", [])})
                (folder / MARKER).write_text(json.dumps(marker, indent=1), encoding="utf-8")
                entry.update(ok=True, **marker)
        results.append(entry)
    return results


# --------------------------------------------------------------------- lines
LINE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]{0,63})\s*[:=|]\s*(.+?)\s*$")


def _item_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return cleaned[:64] or "line"


def load_lines(path: Path | None, text: str = "", name: str = "") -> list[dict]:
    """Lines to make: a JSON object {name: text}, a JSON list of {name, text},
    a text file of `name: text` lines (plain lines are numbered), or one
    `--set text=...`. Names become file names, so they must be unique."""
    items: list[dict] = []
    if path is not None:
        raw = path.read_text(encoding="utf-8-sig")
        if path.suffix.lower() == ".json":
            data = json.loads(raw)
            if isinstance(data, dict):
                items = [{"name": str(k), "text": str(v)} for k, v in data.items()]
            elif isinstance(data, list):
                for index, entry in enumerate(data, 1):
                    if isinstance(entry, str):
                        items.append({"name": f"line{index:02d}", "text": entry})
                    elif isinstance(entry, dict) and entry.get("text"):
                        items.append({"name": str(entry.get("name") or f"line{index:02d}"), "text": str(entry["text"])})
            else:
                raise AudioError(f"{path.name}: expected a JSON object or list")
        else:
            for index, line in enumerate((l for l in raw.splitlines() if l.strip() and not l.lstrip().startswith("#")), 1):
                match = LINE.match(line)
                items.append({"name": match.group(1), "text": match.group(2)} if match else {"name": f"line{index:02d}", "text": line.strip()})
    if text.strip():
        items.append({"name": name or "line01", "text": text.strip()})
    if not items:
        raise AudioError("nothing to make: pass --set text=... (or prompt=...) or an input file of lines")
    if len(items) > 200:
        raise AudioError("at most 200 lines per run")
    seen = set()
    for item in items:
        item["name"] = _item_name(item["name"])
        if item["name"] in seen:
            raise AudioError(f"duplicate line name {item['name']!r}")
        seen.add(item["name"])
        if len(item["text"]) > 600:
            raise AudioError(f"line {item['name']!r} is longer than 600 characters; split it")
    return items


# --------------------------------------------------------------------- ffmpeg
def ffprobe_for(ffmpeg: str) -> str | None:
    sibling = Path(ffmpeg).with_name("ffprobe.exe" if ffmpeg.lower().endswith(".exe") else "ffprobe")
    if sibling.is_file():
        return str(sibling)
    return shutil.which("ffprobe")


def probe(ffprobe: str, path: Path) -> dict:
    proc = run([ffprobe, "-v", "error", "-show_entries", "format=duration,format_name:stream=codec_type,codec_name,sample_rate,channels",
                "-of", "json", str(path)], timeout=60)
    if proc["returncode"] != 0:
        return {"ok": False, "error": (proc.get("stderr") or proc.get("error") or "").strip()[-300:]}
    data = json.loads(proc["stdout"] or "{}")
    stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not stream:
        return {"ok": False, "error": "no audio stream"}
    duration = float((data.get("format") or {}).get("duration") or 0)
    return {"ok": duration > 0, "codec": stream.get("codec_name"), "sample_rate": int(stream.get("sample_rate") or 0),
            "channels": int(stream.get("channels") or 0), "seconds": round(duration, 3), "container": (data.get("format") or {}).get("format_name")}


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number or number in (float("inf"), float("-inf")) else round(number, 2)


def measure(ffmpeg: str, path: Path, silence_db: float = -50.0) -> dict:
    """One decode pass: edge silence, mean/max volume, integrated loudness,
    true peak and loudness range."""
    chain = f"silencedetect=n={silence_db}dB:d=0.05,volumedetect,loudnorm=I=-16:TP=-1:LRA=11:print_format=json"
    proc = run([ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af", chain, "-f", "null", "-"], timeout=300)
    err = proc.get("stderr") or ""
    if proc["returncode"] != 0:
        raise AudioError(f"ffmpeg could not decode {path.name}: {err.strip()[-300:]}")
    result: dict = {}
    block = err[err.rfind("{"):err.rfind("}") + 1] if "{" in err else ""
    try:
        data = json.loads(block) if block else {}
    except ValueError:
        data = {}
    result["lufs"] = _number(data.get("input_i"))
    result["true_peak"] = _number(data.get("input_tp"))
    result["lra"] = _number(data.get("input_lra"))
    mean = re.search(r"mean_volume:\s*(-?[\d.]+|-inf) dB", err)
    peak = re.search(r"max_volume:\s*(-?[\d.]+|-inf) dB", err)
    result["mean_db"] = _number(mean.group(1)) if mean else None
    result["max_db"] = _number(peak.group(1)) if peak else None
    if result["lufs"] is not None and result["lufs"] <= -69:
        result["lufs"] = None  # gated out: too short or too quiet to measure
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*(-?[\d.]+)", err)]
    result["silence"] = list(zip(starts, ends + [None] * (len(starts) - len(ends))))
    return result


def edge_silence(silence: list, seconds: float) -> tuple[float, float]:
    lead = trail = 0.0
    for start, end in silence:
        if start <= 0.01 and end is not None:
            lead = end
        if end is None or end >= seconds - 0.01:
            trail = seconds - start
    return round(max(lead, 0.0), 3), round(max(trail, 0.0), 3)


def bar_levels(ffmpeg: str, path: Path, bar_seconds: float) -> list[float]:
    """RMS level (dB) of each whole bar, measured by FFmpeg in one pass."""
    samples = max(1, round(48000 * bar_seconds))
    result = run([ffmpeg, "-hide_banner", "-nostats", "-loglevel", "error", "-i", str(path), "-af",
                  f"aresample=48000,asetnsamples=n={samples}:p=0,astats=metadata=1:reset=1,"
                  "ametadata=mode=print:key=lavfi.astats.Overall.RMS_level:file=-",
                  "-f", "null", "-"], timeout=300)
    text = (result.get("stdout") or "") + (result.get("stderr") or "")
    levels = []
    for value in re.findall(r"RMS_level=(-?[\d.]+|-inf)", text):
        levels.append(-120.0 if value == "-inf" else float(value))
    return levels


def make_loop(ffmpeg: str, source: Path, target: Path, bar_seconds: float) -> dict:
    """Make a seamless loop from whole bars. The loop runs from the first to
    the last bar at full level, so a quiet intro or a fading outro is left
    out. Its last bar is crossfaded into its first: playback wraps from where
    the body ends straight into the blend that begins with that same audio."""
    ffprobe = ffprobe_for(ffmpeg)
    seconds = (probe(ffprobe, source) if ffprobe else {}).get("seconds") or 0.0
    whole = int(seconds // bar_seconds) if bar_seconds > 0 else 0
    levels = bar_levels(ffmpeg, source, bar_seconds)[:whole]
    if len(levels) < 4:
        raise AudioError(f"{seconds:.1f} s is under 4 bars of {bar_seconds:.2f} s; make the track longer or the tempo faster to loop it")
    ordered = sorted(levels)
    median = ordered[len(ordered) // 2]
    full = [index for index, level in enumerate(levels) if level >= median - 6.0]
    first, last = full[0], full[-1]
    if last - first + 1 < 4:
        raise AudioError(f"only {last - first + 1} bars of {bar_seconds:.2f} s are at full level; make the track longer to loop it")
    start, end, fade = first * bar_seconds, (last + 1) * bar_seconds, bar_seconds
    graph = (
        f"[0:a]asplit=3[a][b][c];"
        f"[a]atrim={start:.6f}:{start + fade:.6f},asetpts=PTS-STARTPTS,afade=t=in:st=0:d={fade:.6f}:curve=qsin[head];"
        f"[b]atrim={end - fade:.6f}:{end:.6f},asetpts=PTS-STARTPTS,afade=t=out:st=0:d={fade:.6f}:curve=qsin[tail];"
        f"[c]atrim={start + fade:.6f}:{end - fade:.6f},asetpts=PTS-STARTPTS[body];"
        f"[head][tail]amix=inputs=2:normalize=0:duration=first[seam];"
        f"[seam][body]concat=n=2:v=0:a=1[out]"
    )
    result = run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-filter_complex", graph,
                  "-map", "[out]", "-c:a", "pcm_f32le", str(target)], timeout=300)
    if result["returncode"] != 0 or not target.is_file():
        raise AudioError(f"ffmpeg could not build the loop: {(result.get('stderr') or result.get('error') or '').strip()[-300:]}")
    kept = levels[first:last + 1]
    return {"bars": last - first, "bar_seconds": round(bar_seconds, 4), "seconds": round(end - start - fade, 3),
            "first_bar": first, "last_bar": last, "source_bars": len(levels), "source_seconds": round(seconds, 3),
            "quiet_inside": [first + i for i, level in enumerate(kept) if level < median - 6.0],
            "median_db": round(median, 1)}


def finish(ffmpeg: str, source: Path, target: Path, fmt: str = "ogg", loudness="peak", true_peak: float = -1.0,
           sample_rate: int = 44100, channels: int = 1, trim: bool = True, highpass: int = 0, work: Path | None = None,
           loop_bar: float = 0.0) -> dict:
    """Trim edge silence, fade the cut ends, then apply one fixed gain that
    reaches the loudness target without passing the true-peak ceiling, and
    encode. No compressor or limiter touches the sound. With loop_bar (the
    length of one bar in seconds) the file is made into a seamless loop
    instead: only trailing silence is trimmed, so the bar grid that starts at
    0 s stays put, and no edge fades are applied."""
    if fmt not in FORMATS:
        raise AudioError(f"format must be one of {', '.join(FORMATS)}")
    work = work or target.parent
    work.mkdir(parents=True, exist_ok=True)
    stage = work / f"{target.stem}.stage.wav"
    filters = []
    if highpass:
        filters.append(f"highpass=f={int(highpass)}")
    edge = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.03"
    if loop_bar:
        if trim:
            filters += ["areverse", edge.replace("0.03", "0.08"), "areverse"]
        filters = filters or ["anull"]
    else:
        if trim:
            filters += [edge, "areverse", edge.replace("0.03", "0.08"), "areverse"]
        filters += ["afade=t=in:d=0.004", "areverse", "afade=t=in:d=0.015", "areverse"]
    first = run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-af", ",".join(filters),
                 "-ac", str(channels), "-ar", str(sample_rate), "-c:a", "pcm_f32le", str(stage)], timeout=300)
    if first["returncode"] != 0 or not stage.is_file():
        raise AudioError(f"ffmpeg could not prepare {source.name}: {(first.get('stderr') or first.get('error') or '').strip()[-300:]}")
    looped = None
    if loop_bar:
        loop_stage = work / f"{target.stem}.loop.wav"
        try:
            looped = make_loop(ffmpeg, stage, loop_stage, float(loop_bar))
        finally:
            stage.unlink(missing_ok=True)
        stage = loop_stage
    before = measure(ffmpeg, stage)
    if before.get("max_db") is None or before["max_db"] <= -60:
        stage.unlink(missing_ok=True)
        raise AudioError(f"{source.name} is silent after trimming")
    peak = before["true_peak"] if before.get("true_peak") is not None else before["max_db"]
    mode = "peak"
    gain = true_peak - peak
    if loudness not in (None, "", "peak") and before.get("lufs") is not None:
        wanted = float(loudness) - before["lufs"]
        mode = "loudness" if wanted <= gain else "loudness (peak-limited)"
        gain = min(wanted, gain)
    target.parent.mkdir(parents=True, exist_ok=True)
    second = run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(stage), "-af", f"volume={gain:.2f}dB",
                  "-ac", str(channels), "-ar", str(sample_rate), *FORMATS[fmt], str(target)], timeout=300)
    stage.unlink(missing_ok=True)
    if second["returncode"] != 0 or not target.is_file():
        raise AudioError(f"ffmpeg could not encode {target.name}: {(second.get('stderr') or second.get('error') or '').strip()[-300:]}")
    return {"gain_db": round(gain, 2), "mode": mode, "before": {k: before.get(k) for k in ("lufs", "true_peak", "max_db")}, "loop": looped}


def checks(ffmpeg: str, path: Path, loudness=None, true_peak: float = -1.0, sample_rate: int | None = None,
           channels: int | None = None) -> tuple[list[dict], dict]:
    """Structural and level checks for one finished file. They prove the file
    decodes and sits at sane levels, not that it sounds right."""
    ffprobe = ffprobe_for(ffmpeg)
    name = path.name
    out: list[dict] = []
    info = probe(ffprobe, path) if ffprobe else {"ok": True, "seconds": None}
    if not info.get("ok"):
        out.append({"artifact": name, "id": "AUDIO-001", "status": "FAIL", "detail": f"does not decode: {info.get('error')}"})
        return out, info
    out.append({"artifact": name, "id": "AUDIO-001", "status": "PASS",
                "detail": f"{info.get('codec')} {info.get('sample_rate')} Hz {info.get('channels')} ch {info.get('seconds')} s" if ffprobe else "decodes (ffprobe not found)"})
    level = measure(ffmpeg, path)
    seconds = info.get("seconds") or 0.0
    if level.get("max_db") is None or level["max_db"] <= -40:
        out.append({"artifact": name, "id": "AUDIO-002", "status": "FAIL", "detail": f"silent: max {level.get('max_db')} dB"})
    else:
        out.append({"artifact": name, "id": "AUDIO-002", "status": "PASS", "detail": f"max {level['max_db']} dB, mean {level.get('mean_db')} dB"})
    tp = level.get("true_peak")
    if tp is None:
        out.append({"artifact": name, "id": "AUDIO-003", "status": "NOT_TESTED", "detail": "true peak not measurable"})
    elif tp > -0.1:
        out.append({"artifact": name, "id": "AUDIO-003", "status": "FAIL", "detail": f"true peak {tp} dBTP: clips"})
    elif tp > true_peak + 0.6:
        out.append({"artifact": name, "id": "AUDIO-003", "status": "WARNING", "detail": f"true peak {tp} dBTP above the {true_peak} ceiling"})
    else:
        out.append({"artifact": name, "id": "AUDIO-003", "status": "PASS", "detail": f"true peak {tp} dBTP"})
    lufs = level.get("lufs")
    if loudness in (None, "", "peak"):
        out.append({"artifact": name, "id": "AUDIO-004", "status": "PASS" if lufs is not None else "NOT_TESTED",
                    "detail": (f"{lufs} LUFS integrated (peak-normalized, no loudness target)" if lufs is not None else "too short to measure integrated loudness")})
    elif lufs is None:
        out.append({"artifact": name, "id": "AUDIO-004", "status": "NOT_TESTED", "detail": "too short to measure integrated loudness"})
    else:
        delta = lufs - float(loudness)
        status = "PASS" if abs(delta) <= 1.5 else "WARNING"
        why = "" if status == "PASS" else ("; quieter because the true-peak ceiling limited the gain" if delta < 0 else "")
        out.append({"artifact": name, "id": "AUDIO-004", "status": status, "detail": f"{lufs} LUFS (target {float(loudness):g}){why}"})
    lead, trail = edge_silence(level["silence"], seconds)
    out.append({"artifact": name, "id": "AUDIO-005", "status": "WARNING" if lead > 0.25 or trail > 0.6 else "PASS",
                "detail": f"{lead} s silence before, {trail} s after"})
    wrong = []
    if sample_rate and info.get("sample_rate") and info["sample_rate"] != sample_rate:
        wrong.append(f"{info['sample_rate']} Hz (wanted {sample_rate})")
    if channels and info.get("channels") and info["channels"] != channels:
        wrong.append(f"{info['channels']} ch (wanted {channels})")
    if sample_rate or channels:
        out.append({"artifact": name, "id": "AUDIO-006", "status": "FAIL" if wrong else "PASS", "detail": "; ".join(wrong) or "sample rate and channels as requested"})
    info.update(level)
    return out, info
