import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT

sys.path.insert(0, str(ROOT / "src"))

from assetforge import adapters  # noqa: E402


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
