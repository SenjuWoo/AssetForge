"""AssetForge audio worker.

Runs inside one of the isolated audio runtimes that `assetforge audio-setup`
creates, never inside AssetForge's own environment, and never imports the
assetforge package: it is started as `<runtime python> -I audio_worker.py
REQUEST.json` with an argument list. The request names the engine, the items
to make and where each WAV goes; the worker loads each model once, makes every
take, scores the takes it can score, and writes RESULT.json beside the request.

Engines and the model each one loads (licences checked 2026-11-13):
  qwen3-tts  Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign + -Base   Apache-2.0  voice design, cloning, 10 languages
  dia        nari-labs/Dia-1.6B-0626                       Apache-2.0  dialogue and nonverbals: (laughs) (gasps)
  kokoro     hexgrad/Kokoro-82M                            Apache-2.0  fast preset voices, CPU-capable
  moss-sfx   OpenMOSS-Team/MOSS-SoundEffect-v2.0           Apache-2.0  text to sound effect, 48 kHz, up to 30 s
  asr        openai/whisper-large-v3-turbo                 MIT         transcript check for speech takes
  clap       laion/larger_clap_general                     Apache-2.0  prompt/audio similarity for SFX takes
"""

from __future__ import annotations

import gc
import json
import math
import os
import re
import sys
import time
import traceback
from difflib import SequenceMatcher
from pathlib import Path

MODELS = {
    "qwen3-tts-design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "qwen3-tts-base": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    "dia": "nari-labs/Dia-1.6B-0626",
    "kokoro": "hexgrad/Kokoro-82M",
    "moss-sfx": "OpenMOSS-Team/MOSS-SoundEffect-v2.0",
    "asr": "openai/whisper-large-v3-turbo",
    "clap": "laion/larger_clap_general",
}

NONVERBAL = re.compile(r"\([^)]*\)|\[[^\]]*\]")


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def device() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def free(*objects) -> None:
    for item in objects:
        del item
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def prime_hf_cache() -> None:
    """huggingface_hub caches its symlink test per model folder and marks the
    folder capable before testing, so the first parallel snapshot download of
    a new model can race into os.symlink on Windows without the privilege
    (WinError 1314). Test once at the cache root; if symlinks do not work
    there, answer no for every folder so files are copied instead."""
    try:
        import huggingface_hub.file_download as fd
        from huggingface_hub import constants
    except ImportError:
        return
    if not fd.are_symlinks_supported(constants.HF_HUB_CACHE):
        fd.are_symlinks_supported = lambda cache_dir=None: False


def eager_compile() -> None:
    """MOSS decorates a helper with torch.compile at import time. torch
    refuses torch.compile on Python 3.14 and there is no Triton on Windows,
    so the decorator becomes the identity and inference runs eagerly."""
    import torch

    def _eager(fn=None, **_kwargs):
        return fn if fn is not None else (lambda inner: inner)

    torch.compile = _eager
    # Each sampling step also marks a CUDA-graph boundary, which imports the
    # inductor compiler stack; on torch 2.9 under Python 3.14 that import
    # fails. Without compiled graphs the marker has nothing to do.
    torch.compiler.cudagraph_mark_step_begin = lambda: None


def seed_all(seed: int) -> None:
    import random

    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)


def to_mono(audio, sr: int):
    import numpy as np

    data = audio
    if hasattr(data, "detach"):
        data = data.detach().float().cpu().numpy()
    data = np.asarray(data, dtype=np.float32)
    data = np.squeeze(data)
    if data.ndim == 2:
        # (channels, samples) or (samples, channels): average the short axis.
        data = data.mean(axis=0) if data.shape[0] < data.shape[1] else data.mean(axis=1)
    return data.reshape(-1).astype(np.float32), int(sr)


def write_wav(path: str, audio, sr: int) -> None:
    import soundfile as sf

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, sr, subtype="PCM_16" if audio.ndim == 1 else "PCM_16")


def signal_stats(audio, sr: int) -> dict:
    """Cheap health numbers for one take: length, peak, clipped share,
    share of near-silent 50 ms windows, and median pitch of voiced frames."""
    import numpy as np

    n = len(audio)
    seconds = n / sr if sr else 0.0
    peak = float(np.max(np.abs(audio))) if n else 0.0
    clipped = float(np.mean(np.abs(audio) > 0.985)) if n else 0.0
    win = max(1, int(0.05 * sr))
    if n >= win:
        env = np.convolve(np.abs(audio), np.ones(win) / win, "same")
        quiet = float(np.mean(env < 0.01))
    else:
        quiet = 1.0
    return {"seconds": round(seconds, 3), "peak": round(peak, 4), "clipped": round(clipped, 5), "quiet": round(quiet, 3), "f0": round(median_f0(audio, sr), 1)}


def median_f0(audio, sr: int) -> float:
    import numpy as np

    hop, win = int(0.02 * sr), int(0.04 * sr)
    if win <= 0 or len(audio) < win * 2:
        return 0.0
    lo, hi = int(sr / 500), int(sr / 70)
    found = []
    step = max(hop, (len(audio) - win) // 400)  # at most ~400 frames per take
    window = np.hanning(win)
    for start in range(0, len(audio) - win, step):
        frame = audio[start:start + win] * window
        if np.sqrt(np.mean(frame ** 2)) < 0.02:
            continue
        ac = np.correlate(frame, frame, "full")[win - 1:]
        if hi >= len(ac):
            continue
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[0] > 0 and ac[k] > 0.35 * ac[0]:
            found.append(sr / k)
    return float(np.median(found)) if len(found) >= 5 else 0.0


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", NONVERBAL.sub(" ", text.lower()))


def transcript_similarity(expected: str, heard: str) -> float | None:
    want = words(expected)
    if not want:
        return None  # nonverbal-only line: nothing to compare
    return round(SequenceMatcher(None, want, words(heard)).ratio(), 3)


def speech_score(item: dict, stats: dict, ref_f0: float) -> float:
    """Higher is better. Transcript match dominates when it exists; length,
    dead air, clipping and pitch distance from the reference break ties."""
    score = 0.0
    similarity = item.get("asr_similarity")
    if similarity is not None:
        score += similarity * 10.0
    spoken = max(1, len(words(item["text"])))
    expected = 0.33 * spoken + 0.45 * len(NONVERBAL.findall(item["text"])) + 0.35
    score -= abs(math.log(max(stats["seconds"], 0.1) / expected)) * 2.0
    score -= stats["quiet"] * 2.0
    score -= stats["clipped"] * 50.0
    if ref_f0 and stats["f0"]:
        score -= abs(math.log(stats["f0"] / ref_f0)) * 4.0
    return round(score, 3)


# --------------------------------------------------------------------- engines
class QwenTTS:
    def __init__(self, request: dict):
        self.request = request
        self.model = None
        self.kind = None

    def load(self, kind: str):
        if self.kind == kind:
            return self.model
        import torch
        from qwen_tts import Qwen3TTSModel

        if self.model is not None:
            free(self.model)
            self.model = None
        repo = MODELS["qwen3-tts-design" if kind == "design" else "qwen3-tts-base"]
        log(f"loading {repo}")
        kwargs = {"device_map": "cuda:0" if device() == "cuda" else "cpu", "dtype": torch.bfloat16 if device() == "cuda" else torch.float32}
        try:
            import flash_attn  # noqa: F401

            kwargs["attn_implementation"] = "flash_attention_2"
        except ImportError:
            kwargs["attn_implementation"] = "sdpa"
        self.model = Qwen3TTSModel.from_pretrained(repo, **kwargs)
        self.kind = kind
        return self.model

    def design(self, text: str, seed: int):
        model = self.load("design")
        seed_all(seed)
        wavs, sr = model.generate_voice_design(text=text, language=self.request.get("language") or "English", instruct=self.request["voice"])
        return to_mono(wavs[0], sr)

    def clone(self, text: str, seed: int, ref_audio: str, ref_text: str):
        model = self.load("base")
        seed_all(seed)
        prompt = getattr(self, "_prompt", None)
        if prompt is None:
            self._prompt = prompt = model.create_voice_clone_prompt(ref_audio=ref_audio, ref_text=ref_text)
        wavs, sr = model.generate_voice_clone(text=text, language=self.request.get("language") or "English", voice_clone_prompt=prompt)
        return to_mono(wavs[0], sr)


class Dia:
    SR = 44100

    def __init__(self, request: dict):
        import torch
        from transformers import AutoProcessor, DiaForConditionalGeneration

        log(f"loading {MODELS['dia']}")
        self.torch = torch
        self.dev = device()
        self.proc = AutoProcessor.from_pretrained(MODELS["dia"])
        dtype = torch.float16 if self.dev == "cuda" else torch.float32
        self.model = DiaForConditionalGeneration.from_pretrained(MODELS["dia"], torch_dtype=dtype).to(self.dev).eval()

    @staticmethod
    def script(text: str) -> str:
        return text if text.lstrip().startswith("[S1]") or text.lstrip().startswith("[S2]") else f"[S1] {text}"

    def generate(self, text: str, seed: int, ref_audio=None, ref_text: str = ""):
        import numpy as np
        import soundfile as sf

        seed_all(seed)
        line = self.script(text)
        if ref_audio:
            audio, sr = sf.read(ref_audio, dtype="float32")
            audio, sr = to_mono(audio, sr)
            if sr != self.SR:
                import torchaudio

                audio = torchaudio.functional.resample(self.torch.from_numpy(audio), sr, self.SR).numpy()
            prompt = self.script(ref_text) + " " + line
            inputs = self.proc(text=[prompt], audio=[audio], padding=True, return_tensors="pt").to(self.dev)
            prompt_len = self.proc.get_audio_prompt_len(inputs["decoder_attention_mask"])
        else:
            inputs = self.proc(text=[line], padding=True, return_tensors="pt").to(self.dev)
            prompt_len = None
        budget = int(86 * (2.5 + 0.09 * len(line)))
        with self.torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=budget, guidance_scale=3.0, temperature=1.8, top_p=0.90, top_k=45)
        decoded = self.proc.batch_decode(out, audio_prompt_len=prompt_len) if prompt_len is not None else self.proc.batch_decode(out)
        return to_mono(np.asarray(decoded[0].float().cpu().numpy() if hasattr(decoded[0], "cpu") else decoded[0]), self.SR)


class Kokoro:
    def __init__(self, request: dict):
        from kokoro import KPipeline

        voice = request.get("voice") or "af_heart"
        lang = request.get("kokoro_lang") or voice[0]
        log(f"loading {MODELS['kokoro']} voice {voice}")
        self.voice = voice
        self.pipe = KPipeline(lang_code=lang, repo_id=MODELS["kokoro"])

    def generate(self, text: str, seed: int, speed: float = 1.0):
        import numpy as np

        seed_all(seed)
        parts = [audio for _, _, audio in self.pipe(text, voice=self.voice, speed=speed) if audio is not None]
        if not parts:
            raise RuntimeError(f"kokoro produced no audio for {text!r}")
        return to_mono(np.concatenate([p.numpy() if hasattr(p, "numpy") else np.asarray(p) for p in parts]), 24000)


class MossSFX:
    def __init__(self, request: dict):
        import torch

        eager_compile()
        from moss_soundeffect_v2 import MossSoundEffectPipeline

        log(f"loading {MODELS['moss-sfx']}")
        self.torch = torch
        dev = device()
        self.pipe = MossSoundEffectPipeline.from_pretrained(MODELS["moss-sfx"], torch_dtype=torch.bfloat16 if dev == "cuda" else torch.float32, device=dev)
        if dev == "cuda":
            # The DiT loads in float32 and runs under bf16 autocast, which
            # re-casts every weight on every step: on a 16 GB card the 30 s
            # window overflowed into shared memory and stalled. Storing the
            # float weights in bf16 (complex RoPE buffers untouched) peaks
            # near 10 GB at about 0.2 s per step (measured 2026-11-13).
            for param in self.pipe.transformer.parameters():
                if param.is_floating_point():
                    param.data = param.data.to(torch.bfloat16)
            torch.cuda.empty_cache()

    def generate(self, prompt: str, seed: int, seconds: float, steps: int, cfg: float):
        seed_all(seed)
        with self.torch.inference_mode():
            # The pipeline seeds its own noise; without seed= every take is identical.
            audio = self.pipe(prompt=prompt, seconds=seconds, num_inference_steps=steps, cfg_scale=cfg, seed=seed)
        if hasattr(audio, "audios"):
            audio = audio.audios
        sr = getattr(self.pipe, "sample_rate", 48000)
        data = audio[0] if getattr(audio, "ndim", 0) == 3 else audio
        return to_mono(data, sr)


class Whisper:
    def __init__(self):
        import torch
        from transformers import pipeline

        log(f"loading {MODELS['asr']}")
        dev = device()
        self.pipe = pipeline("automatic-speech-recognition", model=MODELS["asr"], dtype=torch.float16 if dev == "cuda" else torch.float32, device=0 if dev == "cuda" else -1)

    def hear(self, audio, sr: int, language: str = "english") -> str:
        # Resample here: given 44.1 kHz input, the transformers 4.57 pipeline
        # returns a run of dots instead of words (seen 2026-11-13).
        if sr != 16000:
            import torch
            import torchaudio

            audio = torchaudio.functional.resample(torch.from_numpy(audio), sr, 16000).numpy()
            sr = 16000
        result = self.pipe({"raw": audio, "sampling_rate": sr}, generate_kwargs={"language": language.lower(), "task": "transcribe"})
        return (result.get("text") or "").strip()


class Clap:
    SR = 48000

    def __init__(self):
        from transformers import ClapModel, ClapProcessor

        log(f"loading {MODELS['clap']}")
        self.dev = device()
        self.model = ClapModel.from_pretrained(MODELS["clap"]).to(self.dev).eval()
        self.proc = ClapProcessor.from_pretrained(MODELS["clap"])

    def similarity(self, prompt: str, audio, sr: int) -> float:
        import torch

        if sr != self.SR:
            import torchaudio

            audio = torchaudio.functional.resample(torch.from_numpy(audio), sr, self.SR).numpy()
        inputs = self.proc(text=[prompt], audios=[audio], sampling_rate=self.SR, return_tensors="pt", padding=True).to(self.dev)
        with torch.inference_mode():
            text = self.model.get_text_features(input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"])
            sound = self.model.get_audio_features(input_features=inputs["input_features"], is_longer=inputs.get("is_longer"))
        text = text / text.norm(dim=-1, keepdim=True)
        sound = sound / sound.norm(dim=-1, keepdim=True)
        return round(float((text * sound).sum()), 4)


# --------------------------------------------------------------------- jobs
def speech_job(request: dict, result: dict) -> None:
    engine = request["engine"]
    items = request["items"]
    takes = max(1, min(int(request.get("takes") or 1), 8))
    base_seed = int(request.get("seed") or 0)
    ref_audio = request.get("ref_audio") or ""
    ref_text = request.get("ref_text") or ""
    out_dir = Path(request["out_dir"])
    takes_dir = out_dir / "takes"
    language = request.get("language") or "English"

    if engine == "qwen3-tts":
        generator = QwenTTS(request)
        if not ref_audio and not request.get("voice"):
            raise RuntimeError("qwen3-tts needs a voice description (--set voice=...) or a reference recording")
    elif engine == "dia":
        generator = Dia(request)
    elif engine == "kokoro":
        generator = Kokoro(request)
    else:
        raise RuntimeError(f"unknown speech engine {engine}")

    asr = None
    if request.get("asr"):
        try:
            asr = Whisper()
        except Exception as exc:  # the check is optional; its absence is reported
            result["asr_error"] = f"{type(exc).__name__}: {exc}"

    if engine == "qwen3-tts" and not ref_audio:
        # Design one reference voice from the description, then clone it for
        # every line, so a whole set of lines keeps one voice. The auditions
        # are scored like takes; the best becomes reference.wav.
        ref_text = request.get("reference_text") or "Hello there. This is how I sound when I speak, calm and clear, and sometimes a little louder."
        auditions = []
        for k in range(max(2, min(takes + 1, 6))):
            seed = base_seed + 1000 + k
            audio, sr = generator.design(ref_text, seed)
            stats = signal_stats(audio, sr)
            path = takes_dir / f"reference-{seed}.wav"
            write_wav(str(path), audio, sr)
            audition = {"seed": seed, "path": str(path), "stats": stats, "text": ref_text}
            if asr:
                audition["asr_text"] = asr.hear(audio, sr, language)
                audition["asr_similarity"] = transcript_similarity(ref_text, audition["asr_text"])
            audition["score"] = speech_score(audition, stats, 0.0)
            auditions.append((audition, audio, sr))
            log(f"reference audition seed {seed}: score {audition['score']} {stats} {audition.get('asr_text', '')!r}")
        best, audio, sr = max(auditions, key=lambda a: a[0]["score"])
        ref_audio = str(out_dir / "reference.wav")
        write_wav(ref_audio, audio, sr)
        result["reference"] = dict(best, path=ref_audio, designed=True)
        result["auditions"] = [a[0] for a in auditions]

    ref_f0 = 0.0
    if ref_audio:
        import soundfile as sf

        data, sr = sf.read(ref_audio, dtype="float32")
        data, sr = to_mono(data, sr)
        ref_f0 = median_f0(data, sr)

    for item in items:
        candidates = []
        for k in range(takes):
            seed = base_seed + 17 * k + 1
            t0 = time.time()
            if engine == "qwen3-tts":
                audio, sr = generator.clone(item["text"], seed, ref_audio, ref_text)
            elif engine == "dia":
                audio, sr = generator.generate(item["text"], seed, ref_audio or None, ref_text)
            else:
                audio, sr = generator.generate(item["text"], seed, float(request.get("speed") or 1.0))
            stats = signal_stats(audio, sr)
            take = {"seed": seed, "stats": stats, "seconds_to_make": round(time.time() - t0, 2), "text": item["text"]}
            if asr:
                take["asr_text"] = asr.hear(audio, sr, language)
                take["asr_similarity"] = transcript_similarity(item["text"], take["asr_text"])
            take["score"] = speech_score(take, stats, ref_f0)
            path = takes_dir / f"{item['name']}-take{k + 1}.wav"
            write_wav(str(path), audio, sr)
            take["path"] = str(path)
            candidates.append(take)
            log(f"{item['name']} take {k + 1}: score {take['score']} {stats} {take.get('asr_text', '')!r}")
        best = max(candidates, key=lambda c: c["score"])
        result["items"].append({"name": item["name"], "text": item["text"], "best": best["path"], "seed": best["seed"], "score": best["score"],
                                "asr_text": best.get("asr_text"), "asr_similarity": best.get("asr_similarity"), "stats": best["stats"], "takes": candidates})
    result["asr"] = bool(asr)
    result["reference_audio"] = ref_audio or None
    result["reference_text"] = ref_text or None


def sfx_job(request: dict, result: dict) -> None:
    items = request["items"]
    takes = max(1, min(int(request.get("takes") or 1), 8))
    base_seed = int(request.get("seed") or 0)
    seconds = max(0.5, min(float(request.get("seconds") or 3), 30.0))
    steps = max(4, min(int(request.get("steps") or 100), 200))
    cfg = float(request.get("cfg") or 4.0)
    takes_dir = Path(request["out_dir"]) / "takes"
    made = []
    engine = MossSFX(request)
    for item in items:
        for k in range(takes):
            seed = base_seed + 17 * k + 1
            t0 = time.time()
            audio, sr = engine.generate(item["text"], seed, seconds, steps, cfg)
            path = takes_dir / f"{item['name']}-take{k + 1}.wav"
            write_wav(str(path), audio, sr)
            made.append((item, {"seed": seed, "path": str(path), "stats": signal_stats(audio, sr), "seconds_to_make": round(time.time() - t0, 2)}, audio, sr))
            log(f"{item['name']} take {k + 1}: {made[-1][1]['stats']}")
    free(engine)
    clap = None
    if request.get("clap"):
        try:
            clap = Clap()
        except Exception as exc:
            result["clap_error"] = f"{type(exc).__name__}: {exc}"
    by_item: dict[str, list[dict]] = {}
    for item, take, audio, sr in made:
        if clap:
            take["clap"] = clap.similarity(item["text"], audio, sr)
        stats = take["stats"]
        # A whoosh or a click is mostly silence by nature, so quiet share only
        # counts when the take is nearly empty; prompt match decides.
        take["score"] = round(take.get("clap", 0.0) * 10.0 - (5.0 if stats["quiet"] > 0.98 else 0.0) - stats["clipped"] * 50.0, 3)
        by_item.setdefault(item["name"], []).append(take)
    for item in items:
        candidates = by_item[item["name"]]
        best = max(candidates, key=lambda c: c["score"])
        result["items"].append({"name": item["name"], "text": item["text"], "best": best["path"], "seed": best["seed"], "score": best["score"],
                                "clap": best.get("clap"), "stats": best["stats"], "takes": candidates})
    result["clap"] = bool(clap)


def transcribe_job(request: dict, result: dict) -> None:
    """Whisper check for files made elsewhere (Kokoro runs in its own runtime)."""
    import soundfile as sf

    asr = Whisper()
    language = request.get("language") or "English"
    for item in request["items"]:
        data, sr = sf.read(item["path"], dtype="float32")
        data, sr = to_mono(data, sr)
        heard = asr.hear(data, sr, language)
        result["items"].append({"name": item["name"], "text": item["text"], "asr_text": heard, "asr_similarity": transcript_similarity(item["text"], heard)})


def smoke(request: dict, result: dict) -> None:
    """Import check for `audio-setup`: proves the runtime loads its packages
    and sees the GPU, without downloading weights."""
    import torch

    result["torch"] = torch.__version__
    result["cuda"] = torch.cuda.is_available()
    result["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    eager_compile()
    for module in request.get("modules") or []:
        mod = __import__(module)
        result.setdefault("modules", {})[module] = getattr(mod, "__version__", "present")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: audio_worker.py REQUEST.json", file=sys.stderr)
        return 2
    request_path = Path(sys.argv[1])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    result_path = request_path.with_name("result.json")
    result: dict = {"ok": False, "engine": request.get("engine"), "models": {}, "items": []}
    os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")  # MOSS wraps its DiT in torch.compile; Triton is absent on Windows
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    started = time.time()
    try:
        prime_hf_cache()
        kind = request.get("job")
        if kind == "smoke":
            smoke(request, result)
        elif kind == "speech":
            speech_job(request, result)
        elif kind == "sfx":
            sfx_job(request, result)
        elif kind == "transcribe":
            transcribe_job(request, result)
        else:
            raise RuntimeError(f"unknown job {kind!r}")
        result["ok"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()[-4000:]
    result["models"] = {k: v for k, v in MODELS.items()}
    result["seconds"] = round(time.time() - started, 2)
    result_path.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
