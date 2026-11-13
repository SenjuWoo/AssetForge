import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, make_glb, run_cli

sys.path.insert(0, str(ROOT / "src"))

from assetforge import adapters, cli, providers  # noqa: E402

GODOT = providers.get("godot")


class ToolDetection(unittest.TestCase):
    """Godot, FFmpeg and ImageMagick are found by their own version output."""

    def _shim(self, folder: Path, name: str, line: str) -> Path:
        shim = folder / f"{name}.cmd"
        shim.write_text(f"@echo off\r\necho {line}\r\n", encoding="utf-8")
        return shim

    def _with_env(self, name: str, value: str, provider_id: str) -> dict:
        saved = os.environ.get(name)
        os.environ[name] = value
        try:
            return providers.get(provider_id)
        finally:
            if saved is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = saved

    @unittest.skipUnless(os.name == "nt", "Windows .cmd shim")
    def test_each_tool_is_selected_by_its_variable_and_reports_its_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            godot = self._with_env("GODOT_EXE", str(self._shim(folder, "godot", "4.9.1.stable.official.abcdef")), "godot")
            self.assertTrue(godot["available"])
            self.assertEqual(godot["version"], "4.9.1")
            ffmpeg = self._with_env("FFMPEG_EXE", str(self._shim(folder, "ffmpeg", "ffmpeg version 9.9-test Copyright")), "ffmpeg")
            self.assertEqual((ffmpeg["available"], ffmpeg["version"]), (True, "9.9-test"))
            magick = self._with_env("MAGICK_EXE", str(self._shim(folder, "magick", "Version: ImageMagick 7.9.9-12 Q16")), "imagemagick")
            self.assertEqual((magick["available"], magick["version"]), (True, "7.9.9-12"))

    @unittest.skipUnless(os.name == "nt", "Windows .cmd shim")
    def test_a_program_that_names_no_version_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            impostor = self._shim(Path(tmp), "godot", "hello from something else")
            self.assertNotEqual(self._with_env("GODOT_EXE", str(impostor), "godot").get("path"), str(impostor))

    def test_every_provider_says_what_it_is_for(self):
        for provider_id in ("godot", "ffmpeg", "imagemagick"):
            item = providers.get(provider_id)
            self.assertTrue(item["capabilities"], provider_id)
            self.assertTrue(item["use"], provider_id)
            if not item["available"]:
                self.assertIn("EXE", item["reason"], "a missing tool names the variable that selects it")


class EngineCheckCommand(unittest.TestCase):
    def test_usage_errors_have_their_own_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertEqual(run_cli(["engine-check", "missing.glb"], folder).returncode, cli.EXIT_NOT_FOUND)
            (folder / "notes.txt").write_text("x", encoding="utf-8")
            wrong = run_cli(["engine-check", "notes.txt"], folder)
            self.assertEqual(wrong.returncode, cli.EXIT_USAGE)
            self.assertIn("mesh-convert", wrong.stderr)

    def test_a_missing_engine_is_a_provider_error_not_a_pass(self):
        original = providers.get
        providers.get = lambda provider_id, project=None: {"id": provider_id, "available": False, "reason": "Godot 4 was not found"}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                glb = make_glb(Path(tmp) / "triangle.glb")
                self.assertEqual(cli.main(["engine-check", str(glb)]), cli.EXIT_PROVIDER)
        finally:
            providers.get = original

    @unittest.skipUnless(GODOT["available"], "Godot 4 is not installed")
    def test_godot_imports_and_loads_a_real_glb(self):
        with tempfile.TemporaryDirectory() as tmp:
            glb = make_glb(Path(tmp) / "triangle.glb")
            before = glb.read_bytes()
            done = run_cli(["engine-check", str(glb), "--json"], Path(tmp))
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            report = json.loads(done.stdout)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["engine"], "godot")
            self.assertEqual(report["meshes"], 1)
            self.assertIn("rendering", report["not_tested"])
            self.assertEqual(glb.read_bytes(), before, "the source file is never modified")
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["triangle.glb"], "nothing is left beside it")

    @unittest.skipUnless(GODOT["available"], "Godot 4 is not installed")
    def test_a_file_godot_cannot_import_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.glb"
            broken.write_bytes(b"this is not a glb at all" * 8)
            done = run_cli(["engine-check", str(broken), "--json"], Path(tmp))
            self.assertEqual(done.returncode, cli.EXIT_VALIDATION, done.stdout + done.stderr)
            self.assertEqual(json.loads(done.stdout)["status"], "FAIL")

    @unittest.skipUnless(GODOT["available"], "Godot 4 is not installed")
    def test_the_temporary_project_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            glb = make_glb(Path(tmp) / "triangle.glb")
            leftovers = set(Path(tempfile.gettempdir()).glob("assetforge-godot-*"))
            adapters.godot_import_check(GODOT, glb)
            self.assertEqual(set(Path(tempfile.gettempdir()).glob("assetforge-godot-*")), leftovers)


if __name__ == "__main__":
    unittest.main()
