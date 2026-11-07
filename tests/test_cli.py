import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, make_glb, make_png, make_textured_glb, run_cli

sys.path.insert(0, str(ROOT / "src"))

from assetforge import providers  # noqa: E402
from assetforge.glb import inspect_glb  # noqa: E402
from assetforge.util import sha256_file  # noqa: E402


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        result = run_cli(["init", str(self.root), "--name", "CLI Test"], Path(self.tmp.name))
        self.assertEqual(result.returncode, 0, result.stderr)

    def tearDown(self):
        self.tmp.cleanup()

    def _json(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_version_and_doctor(self):
        result = run_cli(["--version"], self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("assetforge", result.stdout)
        report = self._json(run_cli(["doctor", "--json"], self.root))
        self.assertIn(report["state"], ("READY", "DEGRADED"))
        self.assertTrue(any(item["id"] == "python" for item in report["checks"]))

    def test_recipes_list_is_json(self):
        items = self._json(run_cli(["recipes", "list", "--json"], self.root))
        self.assertTrue(any(item["id"] == "image-prep" for item in items))

    def test_image_prep_end_to_end(self):
        source = make_png(Path(self.tmp.name) / "source.png")
        result = run_cli(["run", "image-prep", "--input", str(source), "--set", "width=64", "--json"], self.root)
        report = self._json(result)
        self.assertEqual(report["job"]["status"], "SUCCEEDED")
        self.assertTrue(report["asset"]["artifacts"])
        self.assertTrue(any(item["role"] == "preview" for item in report["asset"]["artifacts"]))
        job = self._json(run_cli(["status", "--last", "--json"], self.root))
        self.assertEqual(job["id"], report["job"]["id"])

    def test_glb_inspect_validate_and_exports(self):
        glb = make_glb(Path(self.tmp.name) / "triangle.glb")
        report = self._json(run_cli(["run", "glb-inspect", "--input", str(glb), "--json"], self.root))
        asset_id = report["asset"]["id"]
        validation = self._json(run_cli(["validate", asset_id, "--json"], self.root))
        self.assertEqual(validation["summary"]["FAIL"], 0)
        for target in ("godot", "roblox", "generic"):
            exported = self._json(run_cli(["export", asset_id, "--target", target, "--json"], self.root))
            self.assertIn(exported["status"], ("PASS", "WARNING"))
            self.assertEqual(exported["engine_import"], "NOT_TESTED")
            self.assertTrue(Path(exported["out_dir"]).exists())

    def test_dry_run_writes_nothing(self):
        source = make_png(Path(self.tmp.name) / "source.png")
        before = list((self.root / "assets").iterdir())
        report = self._json(run_cli(["run", "image-prep", "--input", str(source), "--dry-run", "--json"], self.root))
        self.assertTrue(report["dry_run"])
        self.assertEqual(list((self.root / "assets").iterdir()), before)

    def test_missing_provider_exit_code(self):
        result = run_cli(["run", "blender-sample"], self.root, env={"BLENDER": ""})
        if result.returncode == 0:
            self.skipTest("Blender is available on this machine")
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)

    def test_unknown_recipe_is_usage_error(self):
        result = run_cli(["run", "nope"], self.root)
        self.assertEqual(result.returncode, 2)

    def test_glb_optimize_end_to_end(self):
        if not providers.get("gltf-transform").get("available"):
            self.skipTest("gltf-transform is not installed")
        source = make_glb(Path(self.tmp.name) / "triangle.glb")
        before = inspect_glb(source)
        report = self._json(run_cli(["run", "glb-optimize", "--input", str(source), "--json"], self.root))
        self.assertEqual(report["job"]["status"], "SUCCEEDED")
        asset = report["asset"]
        primary = asset["primary"]["mesh"]
        self.assertTrue(primary.endswith("-optimized.glb"), primary)
        primary_path = self.root / primary
        self.assertTrue(primary_path.is_file())
        after = inspect_glb(primary_path)
        self.assertEqual(after["nodes"], before["nodes"])
        self.assertEqual(after["triangles"], before["triangles"])
        labels = {item["label"] for item in asset["artifacts"]}
        self.assertIn("optimized", labels)
        self.assertIn("source", labels)
        self.assertTrue(any("comparison" in item["path"] for item in asset["artifacts"]))

        exported = self._json(run_cli(["export", asset["id"], "--target", "generic", "--json"], self.root))
        self.assertIn(exported["status"], ("PASS", "WARNING"))
        mesh_file = next(item for item in exported["files"] if item["path"].endswith(".glb"))
        self.assertEqual(mesh_file["sha256"], sha256_file(primary_path))
        self.assertEqual(exported["engine_import"], "NOT_TESTED")

    def test_textured_multi_node_scene_preserved_after_optimize(self):
        if not providers.get("gltf-transform").get("available"):
            self.skipTest("gltf-transform is not installed")
        source = make_textured_glb(Path(self.tmp.name) / "textured.glb")
        before = inspect_glb(source)
        report = self._json(run_cli(["run", "glb-optimize", "--input", str(source), "--json"], self.root))
        self.assertEqual(report["job"]["status"], "SUCCEEDED")
        asset = report["asset"]
        primary_path = self.root / asset["primary"]["mesh"]
        after = inspect_glb(primary_path)
        self.assertEqual(after["nodes"], before["nodes"])
        self.assertEqual(after["meshes"], before["meshes"])
        self.assertEqual(after["materials"], before["materials"])
        self.assertEqual(after["images"], before["images"])
        self.assertEqual(after["triangles"], before["triangles"])
        exported = self._json(run_cli(["export", asset["id"], "--target", "godot", "--json"], self.root))
        mesh_file = next(item for item in exported["files"] if item["path"].endswith(".glb"))
        self.assertEqual(mesh_file["sha256"], sha256_file(primary_path))


    def test_texture_pack_and_sprite_atlas(self):
        from PIL import Image

        workspace = Path(self.tmp.name)
        maps = {}
        for name, value in (("occlusion", 64), ("roughness", 128), ("metallic", 255)):
            path = workspace / f"{name}.png"
            Image.new("L", (32, 32), value).save(path)
            maps[name] = path
        result = run_cli([
            "run", "texture-pack",
            "--input", f"occlusion={maps['occlusion']}",
            "--input", f"roughness={maps['roughness']}",
            "--input", f"metallic={maps['metallic']}",
            "--json",
        ], self.root)
        report = self._json(result)
        self.assertEqual(report["job"]["status"], "SUCCEEDED")
        self.assertTrue(any(item["label"] == "orm" for item in report["asset"]["artifacts"]))
        self.assertTrue(report["asset"]["primary"]["image"].endswith("-orm.png"))

        frames = workspace / "frames"
        frames.mkdir()
        for index, color in enumerate([(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]):
            Image.new("RGBA", (16, 16), color).save(frames / f"{index}.png")
        result = run_cli(["run", "sprite-atlas", "--input", str(frames), "--set", "columns=2", "--json"], self.root)
        report = self._json(result)
        self.assertEqual(report["job"]["status"], "SUCCEEDED")
        atlas = next(item for item in report["asset"]["artifacts"] if item["label"] == "atlas")
        metadata = next(item for item in report["asset"]["artifacts"] if item["label"] == "atlas-metadata")
        with Image.open(self.root / atlas["path"]) as image:
            self.assertEqual(image.size, (38, 38))
        data = json.loads((self.root / metadata["path"]).read_text(encoding="utf-8-sig"))
        self.assertEqual(data["columns"], 2)
        self.assertEqual(len(data["frames"]), 4)
        self.assertEqual(len(report["job"]["sources"]["source_frames"]), 4)
        self.assertEqual(len(report["asset"]["inputs"]), 4)
        for item in report["job"]["sources"]["source_frames"]:
            self.assertEqual(len(item["sha256"]), 64)
            self.assertTrue((self.root / item["input"]).exists())

    def test_sprite_atlas_rejects_zero_columns(self):
        from PIL import Image

        frames = Path(self.tmp.name) / "zero-columns"
        frames.mkdir()
        for index in range(2):
            Image.new("RGBA", (4, 4), (index, 0, 0, 255)).save(frames / f"{index}.png")
        result = run_cli(["run", "sprite-atlas", "--input", str(frames), "--set", "columns=0"], self.root)
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertIn("positive integer", result.stdout + result.stderr)

    def test_sprite_atlas_rejects_65_frames(self):
        from PIL import Image

        frames = Path(self.tmp.name) / "too-many"
        frames.mkdir()
        for index in range(65):
            Image.new("RGBA", (4, 4), (index, 0, 0, 255)).save(frames / f"{index:03d}.png")
        result = run_cli(["run", "sprite-atlas", "--input", str(frames)], self.root)
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertIn("at most 64", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
