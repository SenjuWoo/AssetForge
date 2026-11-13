"""Audio: runtimes, the worker protocol, finishing, checks and sound export.

A stub runtime (a bare venv) and a stub worker that writes tones stand in for
the model runtimes, so the contract is tested everywhere. Tests that need
FFmpeg skip without it; the real-model tests run only where
`assetforge audio-setup` has installed the runtimes.
"""

import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

from helpers import ROOT, run_cli

sys.path.insert(0, str(ROOT / "src"))

from assetforge import audio, audio_worker, providers  # noqa: E402

FFMPEG = providers.get("ffmpeg").get("path")


def write_tone(path: Path, seconds: float = 1.0, lead: float = 0.4, tail: float = 0.4, rate: int = 24000,
               amplitude: float = 0.3, channels: int = 1) -> Path:
    """A 440 Hz tone with silence before and after."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    total = int((lead + seconds + tail) * rate)
    for n in range(total):
        t = n / rate
        value = amplitude * math.sin(2 * math.pi * 440 * t) if lead <= t < lead + seconds else 0.0
        sample = struct.pack("<h", int(value * 32767))
        frames += sample * channels
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(bytes(frames))
    return path


# Speaks the worker protocol: reads request.json, writes tones, writes result.json.
STUB_WORKER = r'''
import json, math, struct, sys, wave
from pathlib import Path

def tone(path, seconds=0.8, rate=24000):
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for n in range(int((0.3 + seconds + 0.3) * rate)):
        t = n / rate
        v = 0.25 * math.sin(2 * math.pi * 330 * t) if 0.3 <= t < 0.3 + seconds else 0.0
        frames += struct.pack("<h", int(v * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(frames))

req_path = Path(sys.argv[1])
req = json.loads(req_path.read_text(encoding="utf-8"))
res = {"ok": True, "engine": req.get("engine"), "items": [], "request": req}
job = req["job"]
if job == "smoke":
    res.update(torch="stub", cuda=False, gpu=None, modules={m: "stub" for m in req.get("modules", [])})
elif job in ("speech", "sfx"):
    out = Path(req["out_dir"])
    if job == "speech" and req["engine"] == "qwen3-tts" and not req.get("ref_audio"):
        ref = out / "reference.wav"; tone(ref, 1.5)
        res["reference"] = {"path": str(ref), "seed": 1000, "designed": True}
        res["reference_audio"] = str(ref)
    for item in req["items"]:
        takes = []
        for k in range(int(req.get("takes") or 1)):
            p = out / "takes" / f"{item['name']}-take{k + 1}.wav"; tone(p)
            takes.append({"seed": k + 1, "path": str(p), "score": float(k)})
        entry = {"name": item["name"], "text": item["text"], "best": takes[-1]["path"], "seed": takes[-1]["seed"], "score": 1.0, "takes": takes}
        if job == "speech" and req.get("asr"):
            entry.update(asr_text=item["text"], asr_similarity=None if item["text"].startswith("(") else 0.95)
        if job == "sfx" and req.get("clap"):
            entry["clap"] = 0.42
        res["items"].append(entry)
    res["asr"] = bool(req.get("asr")); res["clap"] = bool(req.get("clap"))
elif job == "transcribe":
    for item in req["items"]:
        res["items"].append({"name": item["name"], "text": item["text"], "asr_text": "something else entirely", "asr_similarity": 0.2})
else:
    res = {"ok": False, "error": f"unknown job {job}"}
(req_path.with_name("result.json")).write_text(json.dumps(res), encoding="utf-8")
'''


def make_runtime(home: Path, name: str, marker: bool = True) -> Path:
    """A real but empty venv standing in for one audio runtime."""
    folder = home / "envs" / name
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(folder)], check=True, capture_output=True)
    if marker:
        (folder / audio.MARKER).write_text(json.dumps({"torch": "stub", "cuda": True, "gpu": "stub GPU"}), encoding="utf-8")
    return folder


class Lines(unittest.TestCase):
    def test_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "a.json").write_text(json.dumps({"greet 1": "Hello.", "bye": "Goodbye."}), encoding="utf-8")
            self.assertEqual([i["name"] for i in audio.load_lines(tmp / "a.json")], ["greet_1", "bye"])
            (tmp / "b.json").write_text(json.dumps(["One.", {"name": "two", "text": "Two."}]), encoding="utf-8")
            self.assertEqual([i["name"] for i in audio.load_lines(tmp / "b.json")], ["line01", "two"])
            (tmp / "c.txt").write_text("# comment\nhurt1: (gasps) Ah!\nJust a plain line\n", encoding="utf-8")
            items = audio.load_lines(tmp / "c.txt")
            self.assertEqual(items[0], {"name": "hurt1", "text": "(gasps) Ah!"})
            self.assertEqual(items[1]["name"], "line02")
            self.assertEqual(audio.load_lines(None, "Hi there.", "hi"), [{"name": "hi", "text": "Hi there."}])

    def test_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            with self.assertRaises(audio.AudioError):
                audio.load_lines(None, "")
            (tmp / "d.txt").write_text("a: one\na: two\n", encoding="utf-8")
            with self.assertRaisesRegex(audio.AudioError, "duplicate"):
                audio.load_lines(tmp / "d.txt")
            with self.assertRaisesRegex(audio.AudioError, "600"):
                audio.load_lines(None, "x" * 601)


class WorkerHelpers(unittest.TestCase):
    """The worker's scoring is plain Python; it imports no model at module level."""

    def test_transcript_similarity_ignores_nonverbal_tags(self):
        self.assertEqual(audio_worker.transcript_similarity("(laughs) Hello there!", "hello there"), 1.0)
        self.assertIsNone(audio_worker.transcript_similarity("(gasps)", "ah"))
        self.assertLess(audio_worker.transcript_similarity("Begone, wretch!", "be gone, rich"), 0.6)

    def test_speech_score_prefers_the_take_that_says_the_words(self):
        stats = {"seconds": 1.5, "quiet": 0.1, "clipped": 0.0, "f0": 220.0}
        good = audio_worker.speech_score({"text": "Hello there traveler", "asr_similarity": 1.0}, stats, 220.0)
        bad = audio_worker.speech_score({"text": "Hello there traveler", "asr_similarity": 0.3}, stats, 220.0)
        self.assertGreater(good, bad)


class Runtimes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "audio home"
        self.env = mock_env = {"ASSETFORGE_AUDIO_HOME": str(self.home)}
        self._old = {k: os.environ.get(k) for k in mock_env}
        os.environ.update(mock_env)

    def tearDown(self):
        for key, value in self._old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def test_missing_runtime_says_what_to_run(self):
        state = audio.runtime_state("speech")
        self.assertFalse(state["available"])
        self.assertIn("assetforge audio-setup speech", state["reason"])

    def test_runtime_without_smoke_marker_is_not_available(self):
        make_runtime(self.home, "sfx", marker=False)
        state = audio.runtime_state("sfx")
        self.assertFalse(state["available"])
        self.assertIn("smoke test", state["reason"])

    def test_runtime_with_marker_is_a_provider(self):
        make_runtime(self.home, "kokoro")
        item = providers.get("audio-kokoro")
        self.assertTrue(item["available"])
        self.assertIn("kokoro", item["details"]["engines"])

    def test_worker_errors_surface(self):
        make_runtime(self.home, "speech")
        stub = Path(self.tmp.name) / "stub.py"
        stub.write_text(STUB_WORKER, encoding="utf-8")
        os.environ["ASSETFORGE_AUDIO_WORKER"] = str(stub)
        try:
            with self.assertRaisesRegex(audio.AudioError, "unknown job"):
                audio.run_worker("speech", {"job": "nope"}, Path(self.tmp.name) / "work", timeout=60)
        finally:
            os.environ.pop("ASSETFORGE_AUDIO_WORKER", None)

    def test_cli_lists_runtimes_without_installing(self):
        result = run_cli(["audio-setup", "--list", "--json"], Path(self.tmp.name), self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual([item["id"] for item in data["runtimes"]], ["audio-speech", "audio-sfx", "audio-kokoro"])
        self.assertEqual(Path(data["home"]), self.home)
        self.assertFalse((self.home / "envs").exists())


@unittest.skipUnless(FFMPEG, "ffmpeg is not available")
class Finishing(unittest.TestCase):
    def test_finish_trims_levels_and_encodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = write_tone(tmp / "raw.wav", amplitude=0.1)
            target = tmp / "out" / "line.ogg"
            applied = audio.finish(FFMPEG, source, target, fmt="ogg", loudness="-18", true_peak=-1.0, sample_rate=44100, channels=1)
            self.assertTrue(target.is_file())
            checks, info = audio.checks(FFMPEG, target, loudness="-18", true_peak=-1.0, sample_rate=44100, channels=1)
            by_id = {c["id"]: c for c in checks}
            self.assertEqual(by_id["AUDIO-001"]["status"], "PASS")
            self.assertEqual(by_id["AUDIO-002"]["status"], "PASS")
            self.assertEqual(by_id["AUDIO-005"]["status"], "PASS", by_id["AUDIO-005"]["detail"])
            self.assertEqual(by_id["AUDIO-006"]["status"], "PASS")
            self.assertNotEqual(by_id["AUDIO-003"]["status"], "FAIL")
            self.assertLess(info["seconds"], 1.3)  # 0.8 s of edge silence trimmed
            self.assertIn(applied["mode"], ("loudness", "loudness (peak-limited)"))

    def test_peak_mode_reaches_the_ceiling(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            target = tmp / "fx.wav"
            audio.finish(FFMPEG, write_tone(tmp / "raw.wav", amplitude=0.05), target, fmt="wav", loudness="peak", true_peak=-1.0)
            _, info = audio.checks(FFMPEG, target)
            self.assertAlmostEqual(info["true_peak"], -1.0, delta=0.6)

    def test_silence_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            with self.assertRaisesRegex(audio.AudioError, "silent"):
                audio.finish(FFMPEG, write_tone(tmp / "raw.wav", amplitude=0.0), tmp / "x.ogg")

    def test_wrong_channel_count_fails_the_format_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            stereo = write_tone(tmp / "s.wav", channels=2)
            checks, _ = audio.checks(FFMPEG, stereo, channels=1)
            self.assertEqual({c["id"]: c["status"] for c in checks}["AUDIO-006"], "FAIL")


@unittest.skipUnless(FFMPEG, "ffmpeg is not available")
class Recipes(unittest.TestCase):
    """Whole recipes through the CLI with the stub runtime and worker."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "audio home"
        stub = self.root / "stub_worker.py"
        stub.write_text(STUB_WORKER, encoding="utf-8")
        for name in ("speech", "sfx", "kokoro"):
            make_runtime(self.home, name)
        self.env = {"ASSETFORGE_AUDIO_HOME": str(self.home), "ASSETFORGE_AUDIO_WORKER": str(stub)}
        self.project = self.root / "project"
        self.assertEqual(run_cli(["init", str(self.project), "--name", "T"], self.root, self.env).returncode, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def run_recipe(self, *args):
        result = run_cli(["run", *args, "--json"], self.project, self.env)
        return result, (json.loads(result.stdout) if result.stdout.strip().startswith("{") else {})

    def manifest(self, payload):
        asset = payload["asset"]["id"] if isinstance(payload.get("asset"), dict) else payload["asset"]
        folder = next((self.project / "assets").glob(f"{asset}*"))
        return json.loads((folder / "asset.json").read_text(encoding="utf-8")), folder

    def test_voice_lines_become_checked_ogg_files(self):
        lines = self.root / "lines in a folder!" / "princess.txt"
        lines.parent.mkdir()
        lines.write_text("greet1: Hello there.\ngreet2: Welcome, dear.\nhurt1: (gasps)\n", encoding="utf-8")
        result, payload = self.run_recipe("audio-voice", "--input", str(lines), "--set", "voice=a warm princess", "--set", "takes=2")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, folder = self.manifest(payload)
        sounds = [a for a in manifest["artifacts"] if a["role"] == "audio"]
        self.assertEqual(sorted(Path(a["path"]).name for a in sounds), ["greet1.ogg", "greet2.ogg", "hurt1.ogg"])
        self.assertEqual(len([a for a in manifest["artifacts"] if a["role"] == "audio-take"]), 6)
        self.assertTrue(any(a["role"] == "audio-reference" for a in manifest["artifacts"]))
        checks = manifest["validation"]
        asr = {c["artifact"]: c["status"] for c in checks if c["id"] == "AUDIO-ASR"}
        self.assertEqual(asr, {"greet1.ogg": "PASS", "greet2.ogg": "PASS", "hurt1.ogg": "NOT_TESTED"})
        self.assertTrue(any(c["id"] == "AUDIO-LISTEN" and c["status"] == "NOT_TESTED" for c in checks))
        request = json.loads((folder / "work" / "voice" / "request.json").read_text(encoding="utf-8"))
        self.assertEqual(request["voice"], "a warm princess")
        self.assertTrue(request["asr"])

    def test_qwen_needs_a_voice_or_a_reference(self):
        result, _ = self.run_recipe("audio-voice", "--set", "text=Hello.")
        self.assertEqual(result.returncode, 6)
        self.assertIn("describe the voice", result.stderr + result.stdout)

    def test_reference_needs_its_transcript(self):
        ref = write_tone(self.root / "ref.wav")
        result, _ = self.run_recipe("audio-voice", "--input", f"reference={ref}", "--set", "text=Hello.")
        self.assertEqual(result.returncode, 6)
        self.assertIn("ref_text", result.stderr + result.stdout)

    def test_kokoro_is_checked_by_the_speech_runtime(self):
        result, payload = self.run_recipe("audio-voice", "--set", "engine=kokoro", "--set", "text=Welcome to my village.", "--set", "name=welcome")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, folder = self.manifest(payload)
        asr = [c for c in manifest["validation"] if c["id"] == "AUDIO-ASR"]
        self.assertEqual(asr[0]["status"], "FAIL")  # the stub transcriber hears other words
        self.assertTrue((folder / "work" / "voice" / "asr" / "result.json").is_file())

    def test_sfx_records_prompt_match(self):
        result, payload = self.run_recipe("audio-sfx", "--set", "prompt=a wooden door creaks open", "--set", "name=door", "--set", "format=wav")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, _ = self.manifest(payload)
        clap = [c for c in manifest["validation"] if c["id"] == "AUDIO-CLAP"]
        self.assertEqual(clap[0]["status"], "PASS")
        self.assertEqual(manifest["primary"]["audio"].rsplit("/", 1)[-1], "door.wav")

    def test_missing_runtime_is_exit_4(self):
        shutil.rmtree(self.home / "envs" / "sfx")
        result, _ = self.run_recipe("audio-sfx", "--set", "prompt=rain")
        self.assertEqual(result.returncode, 4)

    def test_process_a_folder_then_export_for_minecraft(self):
        source = self.root / "raw sounds"
        write_tone(source / "greet1.wav")
        write_tone(source / "greet2.wav", seconds=0.6)
        write_tone(source / "hurt.wav", channels=2)
        (source / "notes.txt").write_text("not audio", encoding="utf-8")
        result, payload = self.run_recipe("audio-process", "--input", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, folder = self.manifest(payload)
        asset = manifest["id"]
        self.assertEqual(len([a for a in manifest["artifacts"] if a["role"] == "audio"]), 3)
        validate = run_cli(["validate", asset, "--json"], self.project, self.env)
        self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
        bad = run_cli(["export", asset, "--target", "minecraft", "--namespace", "Bad Name", "--json"], self.project, self.env)
        self.assertNotEqual(bad.returncode, 0)
        export = run_cli(["export", asset, "--target", "minecraft", "--namespace", "villageprincess", "--json"], self.project, self.env)
        self.assertEqual(export.returncode, 0, export.stdout + export.stderr)
        out = folder / "exports" / "minecraft"
        sounds = json.loads((out / "assets" / "villageprincess" / "sounds.json").read_text(encoding="utf-8"))
        group = "raw-sounds-audio-process"  # the asset's name, lowercased; never the timestamped id
        self.assertEqual(sorted(sounds), [f"{group}.greet", f"{group}.hurt"])
        self.assertEqual(len(sounds[f"{group}.greet"]["sounds"]), 2)
        self.assertEqual(sounds[f"{group}.greet"]["sounds"][0]["name"], f"villageprincess:{group}/greet1")
        self.assertTrue((out / "assets" / "villageprincess" / "sounds" / group / "greet1.ogg").is_file())
        for event in sounds.values():
            for entry in event["sounds"]:
                self.assertRegex(entry["name"], r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")
        self.assertIn("NOT_TESTED", (out / "IMPORT.md").read_text(encoding="utf-8"))

    def test_roblox_refuses_a_format_it_does_not_take(self):
        source = write_tone(self.root / "x.wav")
        result, payload = self.run_recipe("audio-process", "--input", str(source), "--set", "format=wav")
        self.assertEqual(result.returncode, 0, result.stderr)
        asset = self.manifest(payload)[0]["id"]
        plan = run_cli(["export", asset, "--target", "godot", "--dry-run", "--json"], self.project, self.env)
        self.assertEqual(plan.returncode, 0, plan.stderr)
        mc = run_cli(["export", asset, "--target", "minecraft", "--dry-run", "--json"], self.project, self.env)
        self.assertEqual(json.loads(mc.stdout)["status"], "FAIL")

    def test_probe_routes_audio(self):
        wav = write_tone(self.root / "probe me.wav")
        result = run_cli(["probe", str(wav), "--json"], self.root, self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["kind"], "audio")
        self.assertEqual(report["recommend"][0]["recipe"], "audio-process")


def _real(runtime: str) -> bool:
    if os.environ.get("ASSETFORGE_SKIP_REAL_AUDIO"):
        return False
    return bool(FFMPEG) and audio.runtime_state(runtime)["available"]


@unittest.skipUnless(_real("kokoro"), "kokoro runtime is not installed (assetforge audio-setup kokoro)")
class RealKokoro(unittest.TestCase):
    def test_kokoro_speaks_a_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "p"
            run_cli(["init", str(project), "--name", "T"], Path(tmp))
            result = run_cli(["run", "audio-voice", "--set", "engine=kokoro", "--set", "text=Welcome to my village.",
                              "--set", "name=welcome", "--set", "check=false", "--json"], project)
            self.assertEqual(result.returncode, 0, result.stderr)
            out = next((project / "assets").glob("*/outputs/welcome.ogg"))
            checks, info = audio.checks(FFMPEG, out, loudness="-18")
            self.assertGreater(info["seconds"], 0.8)
            self.assertEqual({c["id"]: c["status"] for c in checks}["AUDIO-002"], "PASS")


if __name__ == "__main__":
    unittest.main()
