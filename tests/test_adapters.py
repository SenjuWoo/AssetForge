import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT

sys.path.insert(0, str(ROOT / "src"))

from assetforge import adapters  # noqa: E402


class Img2ThreeJsAdapterTests(unittest.TestCase):
    def test_codegen_runs_generator_and_verifies_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "img2threejs"
            script = root / "forge" / "stage3_build" / "generate_threejs_factory.py"
            script.parent.mkdir(parents=True)
            script.write_text("# fake upstream generator\n", encoding="utf-8")
            spec = Path(tmp) / "spec.json"
            spec.write_text("{}", encoding="utf-8")
            out = Path(tmp) / "out" / "factory.ts"

            def fake_run(command, **kwargs):
                target = Path(command[command.index("--out") + 1])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("export const factory = () => null;\n" * 20, encoding="utf-8")
                return {"returncode": 0, "stdout": "", "stderr": ""}

            with mock.patch("assetforge.adapters.run", side_effect=fake_run):
                result = adapters.img2threejs_codegen(root, spec, out)
            self.assertEqual(result["returncode"], 0)
            self.assertTrue(out.exists())
            self.assertIn(str(script), result["command"])

    def test_codegen_rejects_missing_upstream_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(adapters.AdapterError):
                adapters.img2threejs_codegen(Path(tmp), Path(tmp) / "spec.json", Path(tmp) / "out.ts")


class ComfyKitAdapterTests(unittest.TestCase):
    def _call(self, params, side_effect=None):
        with mock.patch("assetforge.adapters.shutil.which", return_value="powershell"), \
             mock.patch("assetforge.adapters.run", side_effect=side_effect) as run:
            if side_effect is None:
                run.return_value = {"returncode": 0, "stdout": "ok", "stderr": ""}
            adapters.comfykit_generate(Path("C:/comfy-kit"), params, Path("C:/out"), timeout=30)
            return run.call_args[0][0]

    def test_empty_preset_is_omitted(self):
        command = self._call({"prompt": "x", "preset": "", "width": 512, "height": 512})
        self.assertNotIn("-Preset", command)
        self.assertIn("-Out", command)

    def test_preset_is_forwarded(self):
        command = self._call({"prompt": "x", "preset": "Anima - Author Daily (Euler + SGM)", "width": 512, "height": 512})
        self.assertIn("-Preset", command)
        self.assertIn("Anima - Author Daily (Euler + SGM)", command)

    def test_empty_prompt_is_rejected(self):
        with mock.patch("assetforge.adapters.shutil.which", return_value="powershell"):
            with self.assertRaises(adapters.AdapterError):
                adapters.comfykit_generate(Path("C:/comfy-kit"), {"prompt": ""}, Path("C:/out"))

    def test_nonzero_exit_raises(self):
        with mock.patch("assetforge.adapters.shutil.which", return_value="powershell"), \
             mock.patch("assetforge.adapters.run", return_value={"returncode": 3, "stdout": "", "stderr": "bad"}):
            with self.assertRaises(adapters.AdapterError):
                adapters.comfykit_generate(Path("C:/comfy-kit"), {"prompt": "x"}, Path("C:/out"))

    def test_timeout_raises(self):
        with mock.patch("assetforge.adapters.shutil.which", return_value="powershell"), \
             mock.patch("assetforge.adapters.run", return_value={"returncode": None, "timed_out": True, "stdout": "", "stderr": ""}):
            with self.assertRaises(adapters.AdapterError):
                adapters.comfykit_generate(Path("C:/comfy-kit"), {"prompt": "x"}, Path("C:/out"))


if __name__ == "__main__":
    unittest.main()
