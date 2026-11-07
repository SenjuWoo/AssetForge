import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

sys.path.insert(0, str(ROOT / "src"))

from assetforge import providers  # noqa: E402


class ProviderTests(unittest.TestCase):
    def test_owner_detection_from_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "comfy-kit"
            (root / "TOOLS").mkdir(parents=True)
            (root / "presets").mkdir()
            (root / "TOOLS" / "image-stack.ps1").write_text("# stub", encoding="utf-8")
            (root / "presets" / "presets.json").write_text(json.dumps({"A": {}, "B": {}}), encoding="utf-8")
            (root / "VERSION").write_text("9.9.9\n", encoding="utf-8")
            old = os.environ.get("COMFY_KIT_ROOT")
            os.environ["COMFY_KIT_ROOT"] = str(root)
            try:
                item = providers.get("comfy-kit")
            finally:
                if old is None:
                    os.environ.pop("COMFY_KIT_ROOT", None)
                else:
                    os.environ["COMFY_KIT_ROOT"] = old
            self.assertTrue(item["available"])
            self.assertEqual(item["version"], "9.9.9")
            self.assertEqual(item["details"]["presets"], 2)

    def test_img2threejs_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "img2threejs"
            (root / "forge" / "stage1_intake").mkdir(parents=True)
            (root / "SKILL.md").write_text("# stub", encoding="utf-8")
            (root / "forge" / "stage1_intake" / "probe_image.py").write_text("print('{}')", encoding="utf-8")
            old = os.environ.get("IMG2THREEJS_ROOT")
            os.environ["IMG2THREEJS_ROOT"] = str(root)
            try:
                item = providers.get("img2threejs")
            finally:
                if old is None:
                    os.environ.pop("IMG2THREEJS_ROOT", None)
                else:
                    os.environ["IMG2THREEJS_ROOT"] = old
            self.assertTrue(item["available"])

    @unittest.skipUnless(os.name == "nt", "Windows .cmd shim")
    def test_blender_shim_version_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            shim = Path(tmp) / "blender.cmd"
            shim.write_text("@echo off\r\necho Blender 4.2.0\r\n", encoding="utf-8")
            old = os.environ.get("BLENDER")
            os.environ["BLENDER"] = str(shim)
            try:
                item = providers.get("blender")
            finally:
                if old is None:
                    os.environ.pop("BLENDER", None)
                else:
                    os.environ["BLENDER"] = old
            self.assertTrue(item["available"])
            self.assertEqual(item["version"], "4.2.0")

    def test_missing_provider_reports_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("IMG2THREEJS_ROOT")
            os.environ["IMG2THREEJS_ROOT"] = str(Path(tmp) / "nope")
            try:
                item = providers.get("img2threejs")
            finally:
                if old is None:
                    os.environ.pop("IMG2THREEJS_ROOT", None)
                else:
                    os.environ["IMG2THREEJS_ROOT"] = old
            self.assertFalse(item["available"])
            self.assertTrue(item["reason"])


if __name__ == "__main__":
    unittest.main()
