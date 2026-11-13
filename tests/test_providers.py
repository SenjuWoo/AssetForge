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

    def test_img2threejs_version_comes_from_its_skill_frontmatter(self):
        # img2threejs ships no VERSION file; its release number is in SKILL.md.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "img2threejs"
            (root / "forge" / "stage1_intake").mkdir(parents=True)
            (root / "SKILL.md").write_text("---\nname: img2threejs\nlicense: Apache-2.0\nversion: 2.0.1\n---\n# x\n", encoding="utf-8")
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
            self.assertEqual(item["version"], "2.0.1")

    @unittest.skipUnless(os.name == "nt", "Windows .cmd shim")
    def test_blender_shim_version_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            shim = Path(tmp) / "blender.cmd"
            shim.write_text("@echo off\r\necho Blender 4.2.0\r\n", encoding="utf-8")
            old = os.environ.get("BLENDER")
            old_exe = os.environ.pop("BLENDER_EXE", None)
            os.environ["BLENDER"] = str(shim)
            try:
                item = providers.get("blender")
            finally:
                if old is None:
                    os.environ.pop("BLENDER", None)
                else:
                    os.environ["BLENDER"] = old
                if old_exe is not None:
                    os.environ["BLENDER_EXE"] = old_exe
            self.assertTrue(item["available"])
            self.assertEqual(item["version"], "4.2.0")

    def test_a_profile_wrapper_named_blender_is_never_probed(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = Path(tmp) / "blender.bat"
            wrapper.write_text("@echo off\r\nhermes -p blender %*\r\n", encoding="utf-8")
            real = Path(tmp) / "blender.cmd"
            real.write_text("@echo off\r\necho Blender 4.2.0\r\n", encoding="utf-8")
            self.assertTrue(providers._is_profile_wrapper(wrapper))
            self.assertFalse(providers._is_profile_wrapper(real))
            saved = {name: os.environ.pop(name, None) for name in ("BLENDER_EXE", "BLENDER")}
            which = providers.shutil.which
            providers.shutil.which = lambda name: str(wrapper) if name == "blender" else which(name)
            try:
                self.assertNotIn(wrapper, providers.blender_candidates())
                os.environ["BLENDER_EXE"] = str(wrapper)
                self.assertNotIn(wrapper, providers.blender_candidates())
            finally:
                providers.shutil.which = which
                os.environ.pop("BLENDER_EXE", None)
                for name, value in saved.items():
                    if value is not None:
                        os.environ[name] = value

    def test_blender_is_found_in_a_declared_tool_root_and_the_variable_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            portable = Path(tmp) / "tools" / "blender-5.2-windows-x64" / "blender.exe"
            portable.parent.mkdir(parents=True)
            portable.write_bytes(b"")
            chosen = Path(tmp) / "mine" / "blender.exe"
            chosen.parent.mkdir()
            chosen.write_bytes(b"")
            saved = {name: os.environ.pop(name, None) for name in ("BLENDER_EXE", "BLENDER", "ASSETFORGE_ROOTS")}
            os.environ["ASSETFORGE_ROOTS"] = str(Path(tmp) / "tools")
            try:
                self.assertIn(portable, providers.blender_candidates())
                os.environ["BLENDER_EXE"] = str(chosen)
                self.assertEqual(providers.blender_candidates()[0], chosen)
            finally:
                for name in ("BLENDER_EXE", "ASSETFORGE_ROOTS"):
                    os.environ.pop(name, None)
                for name, value in saved.items():
                    if value is not None:
                        os.environ[name] = value

    def test_a_missing_blender_says_where_it_looked(self):
        saved = {name: os.environ.pop(name, None) for name in ("BLENDER_EXE", "BLENDER")}
        original = providers.blender_candidates
        providers.blender_candidates = lambda project=None: []
        try:
            item = providers.get("blender")
        finally:
            providers.blender_candidates = original
            for name, value in saved.items():
                if value is not None:
                    os.environ[name] = value
        self.assertFalse(item["available"])
        self.assertIn("BLENDER_EXE", item["reason"])
        self.assertIn("Steam", item["reason"])

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
