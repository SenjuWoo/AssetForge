import json
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, make_glb

sys.path.insert(0, str(ROOT / "src"))

from assetforge import exporters, official  # noqa: E402
from assetforge.glb import validate_glb  # noqa: E402
from assetforge.store import Project  # noqa: E402
from assetforge.util import sha256_file  # noqa: E402

try:
    import jsonschema
except ImportError:
    jsonschema = None


class ExporterTests(unittest.TestCase):
    def _asset(self, tmp: Path):
        project = Project.init(tmp / "project", "Export Test")
        asset = project.create_asset("Triangle", "glb-inspect", {})
        glb = make_glb(tmp / "triangle.glb")
        record = asset.add_input(glb, "mesh")
        inside = project.root / record["path"]
        asset.add_artifact(inside, "mesh", "source")
        asset.set_primary("mesh", inside)
        return project, asset

    def test_validate_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, asset = self._asset(Path(tmp))
            report = exporters.validate_asset(project, asset)
            self.assertEqual(report["status"], "PASS")
            self.assertGreater(report["summary"]["PASS"], 0)

    def test_export_generic_and_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, asset = self._asset(Path(tmp))
            result = exporters.export(project, asset, "generic")
            out = Path(result["out_dir"])
            self.assertTrue((out / "export.json").exists())
            self.assertTrue((out / "IMPORT.md").exists())
            self.assertTrue(any(item["path"].endswith(".glb") for item in result["files"]))
            record = json.loads((out / "export.json").read_text(encoding="utf-8"))
            self.assertEqual(record["engine_import"], "NOT_TESTED")
            if jsonschema:
                schema = json.loads((ROOT / "schemas" / "export.schema.json").read_text(encoding="utf-8"))
                jsonschema.validate(record, schema)
            reloaded = project.asset(asset.id)
            self.assertEqual(reloaded.manifest["exports"][0]["target"], "generic")

    def test_dry_run_writes_no_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, asset = self._asset(Path(tmp))
            result = exporters.export(project, asset, "godot", dry_run=True)
            self.assertTrue(result["dry_run"] if "dry_run" in result else True)
            self.assertFalse((asset.folder / "exports" / "godot").exists())

    def test_asset_without_mesh_cannot_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp) / "project")
            asset = project.create_asset("Empty")
            with self.assertRaises(exporters.ExportError):
                exporters.export(project, asset, "generic")

    def test_unknown_profile(self):
        with self.assertRaises(exporters.ExportError):
            exporters.load_profile("nope")

    def test_budget_states(self):
        checks = []
        exporters._budget(checks, "triangles", 10, 100)
        exporters._budget(checks, "triangles", 200, 100)
        exporters._budget(checks, "vertices", 5, 0)
        self.assertEqual([item["status"] for item in checks], ["PASS", "FAIL", "NOT_TESTED"])

    def test_primary_deliverable_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp) / "project")
            asset = project.create_asset("Pick")
            source = make_glb(asset.path("outputs", "source.glb"), node_name="Source")
            optimized = make_glb(asset.path("outputs", "optimized.glb"), node_name="Optimized-Deliverable")
            # Deliberately reversed order: primary must win, not the last record.
            asset.add_artifact(optimized, "mesh", "optimized")
            asset.add_artifact(source, "mesh", "source")
            asset.set_primary("mesh", optimized)
            result = exporters.export(project, asset, "generic")
            exported = Path(result["out_dir"]) / f"{asset.id}.glb"
            self.assertEqual(sha256_file(exported), sha256_file(optimized))
            check = [item for item in result["checks"] if item["id"] == "PRIMARY-001"][0]
            self.assertEqual(check["status"], "PASS")

    def test_artifact_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp) / "project")
            asset = project.create_asset("Escape")
            outside = make_glb(Path(tmp) / "outside.glb")
            asset.manifest["artifacts"].append({
                "path": "../outside.glb",
                "role": "mesh",
                "media_type": "model/gltf-binary",
                "bytes": outside.stat().st_size,
                "sha256": sha256_file(outside),
            })
            asset.save()
            report = exporters.validate_asset(project, asset)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any(item["id"] == "ASSET-002" for item in report["checks"]))
            with self.assertRaises(exporters.ExportError):
                exporters.export(project, asset, "generic")

    def test_absolute_and_missing_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp) / "project")
            asset = project.create_asset("BadPaths")
            outside = make_glb(Path(tmp) / "outside.glb")
            for value in (str(outside), "assets/does-not-exist.glb"):
                with self.subTest(value=value):
                    asset.manifest["artifacts"] = [{"path": value, "role": "mesh", "media_type": "model/gltf-binary"}]
                    asset.manifest["primary"] = {"mesh": value}
                    asset.save()
                    report = exporters.validate_asset(project, asset)
                    self.assertEqual(report["status"], "FAIL")
                    self.assertTrue(any(item["id"] in ("ASSET-002", "ASSET-001") for item in report["checks"]))

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp) / "project")
            asset = project.create_asset("LinkEscape")
            outside = make_glb(Path(tmp) / "outside.glb")
            link = project.root / "link.glb"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("this platform does not allow symlink creation")
            asset.manifest["artifacts"] = [{"path": "link.glb", "role": "mesh", "media_type": "model/gltf-binary"}]
            asset.manifest["primary"] = {"mesh": "link.glb"}
            asset.save()
            report = exporters.validate_asset(project, asset)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any(item["id"] == "ASSET-002" for item in report["checks"]))
            with self.assertRaises(exporters.ExportError):
                exporters.export(project, asset, "generic")

    def test_official_validator_is_separate_from_structural(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp) / "project")
            asset = project.create_asset("Official")
            record = asset.add_input(make_glb(Path(tmp) / "tri.glb"), "mesh")
            inside = project.root / record["path"]
            asset.add_artifact(inside, "mesh", "source")
            asset.set_primary("mesh", inside)
            structural = validate_glb(inside)
            structural_check = [item for item in structural["checks"] if item["id"] == "GLB-014"][0]
            self.assertEqual(structural_check["status"], "NOT_TESTED")
            report = exporters.validate_asset(project, asset)
            official_check = [item for item in report["checks"] if item["id"] == "GLB-014"][0]
            if official.available(project):
                self.assertEqual(official_check["status"], "PASS")
                self.assertIn("official validator", official_check["detail"])
            else:
                self.assertEqual(official_check["status"], "NOT_TESTED")


if __name__ == "__main__":
    unittest.main()
