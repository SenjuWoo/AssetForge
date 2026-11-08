import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

sys.path.insert(0, str(ROOT / "src"))

from assetforge import providers, recipes, runner  # noqa: E402
from assetforge.store import Project  # noqa: E402
from assetforge.util import run  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BlenderPipelineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blender = providers.get("blender")
        cls.skills = providers.get("blender-skills")
        if not cls.blender.get("available") or not cls.skills.get("available"):
            raise unittest.SkipTest("real Blender and blender-skills are required")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.project = Project.init(Path(cls.tmp.name) / "project", "Blender Integration")
        recipe = recipes.get("blender-pipeline", cls.project)
        params = recipes.resolve_params(recipe, {})
        cls.job, cls.asset, _ = runner.execute(cls.project, recipe, {}, params)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_pipeline_artifacts_are_final_and_manifest_is_portable(self):
        self.assertEqual(self.job.data["status"], "SUCCEEDED")
        checks = {item["id"]: item for item in self.asset.manifest["validation"]}
        self.assertEqual(checks["BLENDER-QA"]["status"], "PASS")
        self.assertEqual(checks["BLENDER-QA-RENDER"]["status"], "PASS")
        self.assertEqual(checks["BLENDER-QA-VISUAL"]["status"], "NOT_TESTED")

        for item in self.asset.manifest["artifacts"]:
            path = self.asset.resolve_artifact(item["path"])
            self.assertEqual(path.stat().st_size, item["bytes"], item["path"])
            self.assertEqual(sha256(path), item["sha256"], item["path"])

        manifest_text = self.asset.manifest_path.read_text(encoding="utf-8")
        self.assertNotIn(str(self.project.root), manifest_text)
        self.assertNotIn("C:\\", manifest_text)
        provenance = self.asset.manifest["provenance"]["blender_skills"]
        self.assertTrue(provenance["reviews"])
        for review in provenance["reviews"]:
            self.assertFalse(Path(review["path"]).is_absolute())
            self.assertTrue((self.project.root / review["path"]).is_file())

        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "portable"
            shutil.copytree(self.project.root, copied)
            moved = Project(copied)
            asset = moved.assets()[0]
            for item in asset.manifest["artifacts"]:
                self.assertTrue(asset.resolve_artifact(item["path"]).is_file(), item["path"])
            self.assertTrue(asset.primary("mesh").is_file())

    def test_unacknowledged_qa_warning_fails(self):
        material = next(
            self.project.root / item["path"]
            for item in self.asset.manifest["artifacts"]
            if item.get("label") == "blend-material"
        )
        with tempfile.TemporaryDirectory() as tmp:
            warning_blend = Path(tmp) / "warn.blend"
            shutil.copy2(material, warning_blend)
            command = [
                self.blender["path"], "-b", str(warning_blend), "--python-exit-code", "1",
                "--python-expr",
                "import bpy; o=bpy.data.objects['SM_Crate']; o.location.z += 1.0; "
                f"bpy.ops.wm.save_as_mainfile(filepath=r'{warning_blend}')",
            ]
            result = run(command, timeout=120)
            self.assertEqual(result["returncode"], 0, result["stderr"][-500:])

            project = Project.init(Path(tmp) / "qa-project", "Warning QA")
            recipe = recipes.get("blender-qa", project)
            params = recipes.resolve_params(recipe, {})
            with self.assertRaises(runner.RunFailed) as caught:
                runner.execute(project, recipe, {"blend": warning_blend}, params)
            self.assertIn("warning", str(caught.exception).lower())
            jobs = list(project.jobs_dir.iterdir())
            failed = json.loads((jobs[-1] / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(failed["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
