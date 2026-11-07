import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT, make_glb, make_png

sys.path.insert(0, str(ROOT / "src"))

from assetforge import adapters, recipes, runner  # noqa: E402
from assetforge.glb import GlbError  # noqa: E402
from assetforge.runner import RunFailed  # noqa: E402
from assetforge.store import Job, Project  # noqa: E402


class RunnerFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Project.init(Path(self.tmp.name) / "project", "Runner Test")

    def tearDown(self):
        self.tmp.cleanup()

    def test_invalid_glb_marks_job_failed(self):
        bad = Path(self.tmp.name) / "bad.glb"
        bad.write_bytes(b"not a glb at all")
        recipe = recipes.get("glb-inspect", self.project)
        with self.assertRaises(GlbError):
            runner.execute(self.project, recipe, {"mesh": bad}, {})
        job = Job.latest(self.project)
        self.assertEqual(job.data["status"], "FAILED")
        self.assertIn("GLB", job.data["error"])

    def test_adapter_error_marks_job_failed(self):
        recipe = recipes.get("comfy-generate", self.project)
        params = recipes.resolve_params(recipe, {"prompt": "a test texture"})
        provider = {"id": "comfy-kit", "available": True, "version": "x", "path": self.tmp.name, "details": {}}
        with mock.patch("assetforge.runner.providers.get", return_value=provider), \
             mock.patch("assetforge.adapters.comfykit_generate", side_effect=adapters.AdapterError("tool exploded")):
            with self.assertRaises(adapters.AdapterError):
                runner.execute(self.project, recipe, {}, params)
        job = Job.latest(self.project)
        self.assertEqual(job.data["status"], "FAILED")
        self.assertIn("tool exploded", job.data["error"])

    def test_unexpected_exception_marks_job_failed(self):
        source = make_png(Path(self.tmp.name) / "source.png")
        recipe = recipes.get("image-prep", self.project)

        def boom(_ctx):
            raise ValueError("unexpected parser state")

        with mock.patch.dict(runner.HANDLERS, {"image.inspect": boom}):
            with self.assertRaises(RunFailed):
                runner.execute(self.project, recipe, {"image": source}, {})
        job = Job.latest(self.project)
        self.assertEqual(job.data["status"], "FAILED")
        self.assertIn("unexpected ValueError", job.data["error"])

    def test_inputs_are_copied_and_sources_are_recorded(self):
        source = make_png(Path(self.tmp.name) / "outside.png")
        recipe = recipes.get("image-prep", self.project)
        job, asset, _ = runner.execute(self.project, recipe, {"image": source}, {})
        record = asset.manifest["inputs"][0]
        self.assertFalse(Path(record["path"]).is_absolute())
        self.assertTrue((self.project.root / record["path"]).is_file())
        self.assertNotEqual(Path(record["path"]).resolve(), source.resolve())
        self.assertEqual(job.data["sources"]["image"]["original"], str(source.resolve()))
        for artifact in asset.manifest["artifacts"]:
            self.assertFalse(Path(artifact["path"]).is_absolute())

    def test_context_refuses_unowned_file(self):
        source = make_png(Path(self.tmp.name) / "outside.png")
        ctx = runner.Context(self.project, None, None, {}, {"image": source}, {}, copied={})
        with self.assertRaises(RunFailed):
            ctx.image_input()

    def test_store_error_marks_job_failed(self):
        source = make_png(Path(self.tmp.name) / "source.png")
        recipe = recipes.get("image-prep", self.project)

        def boom(_ctx):
            from assetforge.store import StoreError

            raise StoreError("artifact escaped")

        with mock.patch.dict(runner.HANDLERS, {"image.inspect": boom}):
            with self.assertRaises(Exception):
                runner.execute(self.project, recipe, {"image": source}, {})
        self.assertEqual(Job.latest(self.project).data["status"], "FAILED")

    def test_oserror_marks_job_failed(self):
        source = make_png(Path(self.tmp.name) / "source.png")
        recipe = recipes.get("image-prep", self.project)

        def boom(_ctx):
            raise OSError("disk went away")

        with mock.patch.dict(runner.HANDLERS, {"image.inspect": boom}):
            with self.assertRaises(OSError):
                runner.execute(self.project, recipe, {"image": source}, {})
        job = Job.latest(self.project)
        self.assertEqual(job.data["status"], "FAILED")
        self.assertIn("disk went away", job.data["error"])


if __name__ == "__main__":
    unittest.main()
