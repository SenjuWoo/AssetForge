import json
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, make_glb, make_png

sys.path.insert(0, str(ROOT / "src"))

from assetforge.store import Job, Project, StoreError  # noqa: E402

try:
    import jsonschema
except ImportError:
    jsonschema = None


class StoreTests(unittest.TestCase):
    def test_init_and_find(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo"
            project = Project.init(root, "Demo")
            self.assertTrue((root / "assetforge.json").exists())
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            self.assertEqual(Project.find(nested).root, root.resolve())
            again = Project.init(root)
            self.assertEqual(again.data["name"], "Demo")

    def test_asset_inputs_artifacts_and_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp) / "demo", "Demo")
            source = make_png(Path(tmp) / "source.png")
            asset = project.create_asset("Test", "image-prep", {"format": "png"})
            record = asset.add_input(source, "image")
            self.assertEqual(record["kind"], "image")
            self.assertEqual(len(record["sha256"]), 64)
            self.assertFalse(Path(record["path"]).is_absolute())
            inside = project.root / record["path"]
            artifact = asset.add_artifact(inside, "image", "converted")
            self.assertEqual(artifact["media_type"], "image/png")
            asset.save()
            loaded = project.asset(asset.id)
            self.assertEqual(loaded.manifest["id"], asset.id)
            if jsonschema:
                schema = json.loads((ROOT / "schemas" / "asset.schema.json").read_text(encoding="utf-8"))
                jsonschema.validate(loaded.manifest, schema)

    def test_asset_lookup_by_prefix_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp) / "demo")
            asset = project.create_asset("Lookup")
            self.assertEqual(project.asset(asset.id[:8]).id, asset.id)
            with self.assertRaises(StoreError):
                project.asset("does-not-exist")

    def test_job_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp) / "demo")
            asset = project.create_asset("Jobbed")
            job = Job.create(project, "glb-inspect", {}, asset.id)
            job.step("glb.inspect", "OK", "done", outcome="PASS")
            job.finish("SUCCEEDED")
            loaded = Job.load(project, job.id)
            self.assertEqual(loaded.data["status"], "SUCCEEDED")
            self.assertEqual(loaded.data["steps"][0]["name"], "glb.inspect")
            self.assertEqual(Job.latest(project).id, job.id)
            self.assertTrue((job.folder / "run.log").exists())

    def test_unknown_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(Project.find(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
