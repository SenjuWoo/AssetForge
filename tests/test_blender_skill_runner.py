import json
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

sys.path.insert(0, str(ROOT / "src"))

from assetforge import providers, recipes, runner  # noqa: E402
from assetforge.store import Project  # noqa: E402
from assetforge.util import run  # noqa: E402


class BlenderSkillRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blender = providers.get("blender")
        cls.skills = providers.get("blender-skills")
        if not cls.blender.get("available") or not cls.skills.get("available"):
            raise unittest.SkipTest("real Blender and blender-skills are required")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.blend = Path(cls.tmp.name) / "input.blend"
        expression = (
            "import bpy\n"
            "bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))\n"
            "obj = bpy.context.object\n"
            "obj.name = 'AuditCube'\n"
            "bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n"
            "bpy.ops.object.mode_set(mode='EDIT')\n"
            "bpy.ops.mesh.select_all(action='SELECT')\n"
            "bpy.ops.uv.smart_project(angle_limit=1.151, island_margin=0.01)\n"
            "bpy.ops.object.mode_set(mode='OBJECT')\n"
            f"bpy.ops.wm.save_as_mainfile(filepath={json.dumps(str(cls.blend))})\n"
        )
        result = run(
            [cls.blender["path"], "-b", "--factory-startup", "--python-exit-code", "1", "--python-expr", expression],
            timeout=120,
        )
        if result["returncode"] != 0:
            raise RuntimeError((result["stderr"] or result["stdout"])[-1000:])

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_make_lods_writes_layered_blend(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp), "Make LODs")
            recipe = recipes.get("blender-optimize", project)
            params = recipes.resolve_params(
                recipe, {"operation": "make-lods", "objects": "AuditCube", "ratios": "0.5 0.25", "cleanup": True}
            )
            job, asset, _ = runner.execute(project, recipe, {"blend": self.blend}, params)
            self.assertEqual(job.data["status"], "SUCCEEDED")
            output = next(
                asset.resolve_artifact(item["path"])
                for item in asset.manifest["artifacts"]
                if item.get("label") == "blender-make-lods"
            )
            self.assertGreater(output.stat().st_size, 1000)
            report = next(
                asset.resolve_artifact(item["path"])
                for item in asset.manifest["artifacts"]
                if item.get("label") == "blender-make-lods.json"
            )
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"])
            self.assertIn("LOD1", data["lods"]["AuditCube"])
            self.assertIn("LOD2", data["lods"]["AuditCube"])

    def test_auto_retopo_writes_low_resolution_blend(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp), "Auto Retopo")
            recipe = recipes.get("blender-retopo-uv", project)
            params = recipes.resolve_params(
                recipe, {"operation": "auto-retopo", "objects": "AuditCube", "method": "decimate", "tris": 4}
            )
            job, asset, _ = runner.execute(project, recipe, {"blend": self.blend}, params)
            self.assertEqual(job.data["status"], "SUCCEEDED")
            output = next(
                asset.resolve_artifact(item["path"])
                for item in asset.manifest["artifacts"]
                if item.get("label") == "blender-auto-retopo"
            )
            self.assertGreater(output.stat().st_size, 1000)
            report = next(
                asset.resolve_artifact(item["path"])
                for item in asset.manifest["artifacts"]
                if item.get("label") == "blender-auto-retopo.json"
            )
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"])
            self.assertEqual(data["objects"]["AuditCube"]["low"], "AuditCube_low")
            self.assertLessEqual(data["objects"]["AuditCube"]["tris_after"], data["objects"]["AuditCube"]["faces_before"])

    def test_uv_pack_writes_uv_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp), "UV Pack")
            recipe = recipes.get("blender-retopo-uv", project)
            params = recipes.resolve_params(
                recipe, {"operation": "uv-pack", "objects": "AuditCube", "method": "smart", "res": 512}
            )
            job, asset, _ = runner.execute(project, recipe, {"blend": self.blend}, params)
            self.assertEqual(job.data["status"], "SUCCEEDED")
            output = next(
                asset.resolve_artifact(item["path"])
                for item in asset.manifest["artifacts"]
                if item.get("label") == "blender-uv-pack"
            )
            self.assertGreater(output.stat().st_size, 1000)
            report = next(
                asset.resolve_artifact(item["path"])
                for item in asset.manifest["artifacts"]
                if item.get("label") == "blender-uv-pack.json"
            )
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"])
            self.assertEqual(data["method"], "smart")
            self.assertIn("UVMap", data["objects"]["AuditCube"]["uv_maps"])

    def test_texel_density_reports_per_object_density(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp), "Texel Density")
            recipe = recipes.get("blender-retopo-uv", project)
            params = recipes.resolve_params(recipe, {"operation": "texel-density", "objects": "AuditCube", "res": 512})
            job, asset, _ = runner.execute(project, recipe, {"blend": self.blend}, params)
            self.assertEqual(job.data["status"], "SUCCEEDED")
            report = next(
                asset.resolve_artifact(item["path"])
                for item in asset.manifest["artifacts"]
                if item.get("label") == "blender-texel-density.json"
            )
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"])
            self.assertIn("px_per_m", data["objects"]["AuditCube"])

    def test_texel_density_set_writes_scaled_blend(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp), "Texel Density Set")
            recipe = recipes.get("blender-retopo-uv", project)
            params = recipes.resolve_params(recipe, {"operation": "texel-density", "objects": "AuditCube", "res": 512, "target": "512"})
            job, asset, _ = runner.execute(project, recipe, {"blend": self.blend}, params)
            self.assertEqual(job.data["status"], "SUCCEEDED")
            output = next(
                asset.resolve_artifact(item["path"])
                for item in asset.manifest["artifacts"]
                if item.get("label") == "blender-texel-density"
            )
            self.assertGreater(output.stat().st_size, 1000)
            report = next(
                asset.resolve_artifact(item["path"])
                for item in asset.manifest["artifacts"]
                if item.get("label") == "blender-texel-density.json"
            )
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"])
            self.assertIn("after", data["objects"]["AuditCube"])

    def test_mesh_stats_reports_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp), "Mesh Stats")
            recipe = recipes.get("blender-optimize", project)
            params = recipes.resolve_params(
                recipe, {"operation": "mesh-stats", "objects": "AuditCube", "budget": "roblox"}
            )
            job, asset, _ = runner.execute(project, recipe, {"blend": self.blend}, params)
            self.assertEqual(job.data["status"], "SUCCEEDED")
            report = next(
                asset.resolve_artifact(item["path"])
                for item in asset.manifest["artifacts"]
                if item.get("label") == "blender-mesh-stats.json"
            )
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"])
            self.assertEqual(data["budget"]["name"], "roblox")
            self.assertTrue(data["budget"]["pass"])
            self.assertGreater(data["total_tris"], 0)


if __name__ == "__main__":
    unittest.main()
