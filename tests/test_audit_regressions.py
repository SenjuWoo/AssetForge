"""Regressions found by the 0.8.1 audit. Each test failed before its fix."""

import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT, make_glb, run_cli

sys.path.insert(0, str(ROOT / "src"))

from assetforge import comfybackend, exporters, glb, probe, providers, recipes, runner  # noqa: E402
from assetforge.store import Job, Project, StoreError  # noqa: E402


def write_glb(path: Path, doc, binary: bytes = b"\x00\x00\x00\x00") -> Path:
    text = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    while len(text) % 4:
        text += b" "
    with open(path, "wb") as handle:
        handle.write(struct.pack("<III", 0x46546C67, 2, 28 + len(text) + len(binary)))
        handle.write(struct.pack("<II", len(text), 0x4E4F534A) + text)
        handle.write(struct.pack("<II", len(binary), 0x004E4942) + binary)
    return path


def reparse(path: Path):
    doc, binary, _ = glb._parse(path)
    return doc, binary


class Temp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()


class BooleanParameters(unittest.TestCase):
    def test_a_typo_is_an_error_not_false(self):
        spec = {"type": "boolean"}
        for raw, expected in (("true", True), ("YES", True), ("1", True), ("on", True),
                              ("false", False), ("No", False), ("0", False), ("off", False)):
            self.assertIs(recipes.parse_value("loop", raw, spec), expected, raw)
        for raw in ("ture", "flase", "", "2"):
            with self.assertRaises(recipes.RecipeError, msg=raw):
                recipes.parse_value("loop", raw, spec)

    def test_python_booleans_still_pass(self):
        self.assertIs(recipes.parse_value("cleanup", True, {"type": "boolean"}), True)
        self.assertIs(recipes.parse_value("cleanup", False, {"type": "boolean"}), False)


class MalformedGlb(Temp):
    DOCS = {
        "root-list": [],
        "meshes-dict": {"asset": {"version": "2.0"}, "meshes": {}},
        "bytelength-text": {"asset": {"version": "2.0"}, "buffers": [{"byteLength": "x"}], "meshes": []},
        "accessors-null": {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 4}], "accessors": None,
                           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}]},
        "primitives-text": {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 4}], "meshes": [{"primitives": "x"}]},
        "nodes-numbers": {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 4}], "nodes": [1, 2], "meshes": []},
        "view-negative-buffer": {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 4}],
                                 "bufferViews": [{"buffer": -7, "byteLength": 4}], "meshes": []},
    }

    def test_validate_reports_fail_instead_of_raising(self):
        for name, doc in self.DOCS.items():
            with self.subTest(name=name):
                report = glb.validate_glb(write_glb(self.tmp / f"{name}.glb", doc))
                self.assertEqual(report["status"], "FAIL")
                self.assertTrue(all(isinstance(item["detail"], str) for item in report["checks"]))

    def test_inspect_raises_the_documented_error(self):
        for name in ("root-list", "accessors-null", "primitives-text"):
            with self.subTest(name=name):
                with self.assertRaises(glb.GlbError):
                    glb.inspect_glb(write_glb(self.tmp / f"{name}.glb", self.DOCS[name]))

    def test_probe_and_cli_validate_do_not_crash(self):
        path = write_glb(self.tmp / "bad.glb", self.DOCS["accessors-null"])
        report = probe.probe(path)
        self.assertTrue(any(item["status"] == "FAIL" for item in report["findings"]))
        result = run_cli(["probe", str(path), "--json"], self.tmp)
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class GlbCounts(Temp):
    def test_percent_encoded_external_image_resolves(self):
        (self.tmp / "my tex.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", 4, 4) + b"\x00" * 8)
        doc, binary = reparse(make_glb(self.tmp / "base.glb"))
        doc["images"] = [{"uri": "my%20tex.png"}]
        doc["textures"] = [{"source": 0}]
        report = glb.validate_glb(write_glb(self.tmp / "external.glb", doc, binary))
        check = next(item for item in report["checks"] if item["id"] == "GLB-012")
        self.assertEqual(check["status"], "PASS", check)

    def test_a_missing_external_image_still_fails(self):
        doc, binary = reparse(make_glb(self.tmp / "base.glb"))
        doc["images"] = [{"uri": "gone%20tex.png"}]
        report = glb.validate_glb(write_glb(self.tmp / "external.glb", doc, binary))
        self.assertEqual(next(item for item in report["checks"] if item["id"] == "GLB-012")["status"], "FAIL")

    def test_strips_and_fans_count_their_triangles(self):
        for mode, expected in ((4, 1), (5, 1), (6, 1), (1, 0), (0, 0)):
            with self.subTest(mode=mode):
                doc, binary = reparse(make_glb(self.tmp / "base.glb"))
                doc["meshes"][0]["primitives"][0]["mode"] = mode
                self.assertEqual(glb.inspect_glb(write_glb(self.tmp / f"mode{mode}.glb", doc, binary))["triangles"], expected)

    def test_a_long_strip_counts_n_minus_two(self):
        doc, binary = reparse(make_glb(self.tmp / "base.glb"))
        doc["accessors"][2]["count"] = 3
        primitive = doc["meshes"][0]["primitives"][0]
        primitive["mode"] = 5
        del primitive["indices"]
        doc["accessors"][0]["count"] = 3
        self.assertEqual(glb._primitive_triangles(dict(doc, accessors=[{"count": 10}]), {"mode": 5, "attributes": {"POSITION": 0}}), 8)
        self.assertEqual(glb._primitive_triangles(dict(doc, accessors=[{"count": 2}]), {"mode": 6, "attributes": {"POSITION": 0}}), 0)


class ValidationKeepsRunEvidence(Temp):
    def _asset(self):
        project = Project.init(self.tmp / "project", "Evidence")
        asset = project.create_asset("Crate", "blender-pipeline", {})
        mesh = make_glb(asset.path("outputs", "crate.glb"))
        asset.add_artifact(mesh, "mesh", "deliverable")
        asset.set_primary("mesh", mesh)
        return project, asset

    def test_checks_only_the_run_can_make_survive_validate(self):
        project, asset = self._asset()
        asset.set_validation([
            {"artifact": "crate.blend", "id": "BLENDER-QA", "status": "PASS", "detail": "108 tris"},
            {"artifact": "crate.blend", "id": "BLENDER-QA-VISUAL", "status": "NOT_TESTED", "detail": "pending"},
            {"artifact": "track.ogg", "id": "AUDIO-LENGTH", "status": "WARNING", "detail": "ended early"},
            {"artifact": "page.html", "id": "TEARDOWN-VISUAL", "status": "NOT_TESTED", "detail": "not reviewed"},
            {"artifact": "crate.glb", "id": "GLB-001", "status": "FAIL", "detail": "stale result from an older file"},
        ])
        report = exporters.validate_asset(project, asset)
        kept = {item["id"]: item["status"] for item in asset.manifest["validation"]}
        self.assertEqual(kept.get("BLENDER-QA-VISUAL"), "NOT_TESTED")
        self.assertEqual(kept.get("AUDIO-LENGTH"), "WARNING")
        self.assertEqual(kept.get("TEARDOWN-VISUAL"), "NOT_TESTED")
        self.assertEqual(kept.get("BLENDER-QA"), "PASS")
        self.assertEqual(kept["GLB-001"], "PASS")               # recomputed, not carried
        self.assertEqual(report["status"], "WARNING")           # the early stop is still a warning
        self.assertEqual(report["summary"]["FAIL"], 0)

    def test_validating_twice_does_not_duplicate(self):
        project, asset = self._asset()
        asset.set_validation([{"artifact": "crate.blend", "id": "BLENDER-QA-VISUAL", "status": "NOT_TESTED", "detail": "pending"}])
        exporters.validate_asset(project, asset)
        first = list(asset.manifest["validation"])
        exporters.validate_asset(project, asset)
        self.assertEqual(asset.manifest["validation"], first)
        self.assertEqual(sum(1 for item in first if item["id"] == "BLENDER-QA-VISUAL"), 1)

    def test_true_peak_zero_is_a_setting_not_unset(self):
        self.assertEqual(exporters._ceiling({"true_peak": 0}), 0.0)
        self.assertEqual(exporters._ceiling({"true_peak": -2.5}), -2.5)
        self.assertEqual(exporters._ceiling({}), -1.0)
        self.assertEqual(exporters._ceiling({"true_peak": None}), -1.0)


class DryRunNamesProviders(Temp):
    def _needs(self, recipe_id, overrides=None, inputs=None):
        project = Project.init(self.tmp / "project", "Plan")
        recipe = recipes.get(recipe_id, project)
        params = recipes.resolve_params(recipe, overrides or {})
        with mock.patch.object(providers, "detect", return_value=[]):
            return set(runner.plan(recipe, inputs or {}, params, project)["providers"])

    def test_teardown_recipes_name_what_they_need(self):
        self.assertEqual(self._needs("teardown-build"), {"teardown", "node"})
        self.assertEqual(self._needs("teardown-film"), {"teardown", "node", "ffmpeg"})
        self.assertEqual(self._needs("teardown-film", {"stills": "0,1"}), {"teardown", "node"})

    def test_optional_checkers_are_listed(self):
        self.assertIn("audio-sfx", self._needs("audio-music", {"tags": "x"}))
        self.assertNotIn("audio-sfx", self._needs("audio-music", {"tags": "x", "check": "false"}))
        self.assertIn("audio-speech", self._needs("audio-voice", {"engine": "kokoro", "text": "hi"}))
        self.assertIn("gltf-validator", self._needs("glb-inspect"))
        self.assertIn("pillow", self._needs("image-prep"))

    def test_every_step_is_known_to_the_plan(self):
        # A new step must say what it needs (or that it needs nothing).
        self.assertEqual(set(runner.STEP_PROVIDERS), set(recipes.STEP_NAMES))


class ExplicitComfyUrl(unittest.TestCase):
    def test_a_dead_explicit_url_is_not_replaced(self):
        alive = {"system": {"comfyui_version": "x"}}
        with mock.patch.object(comfybackend, "_alive", side_effect=lambda url, timeout=2.0: alive if url.endswith(":8188") else None):
            with self.assertRaises(comfybackend.BackendError) as caught:
                comfybackend.find_running("http://127.0.0.1:9")
            self.assertIn("no ComfyUI answered", str(caught.exception))
            self.assertIn("http://127.0.0.1:9", str(caught.exception))
            self.assertEqual(comfybackend.find_running("")[0], "http://127.0.0.1:8188")
            with mock.patch.dict(os.environ, {"COMFYUI_URL": "http://127.0.0.1:9"}):
                self.assertEqual(comfybackend.find_running("")[0], "http://127.0.0.1:8188")

    def test_backend_modes_with_a_dead_explicit_url(self):
        for mode in ("auto", "running"):
            with mock.patch.object(comfybackend, "_alive", return_value=None), \
                 mock.patch.object(comfybackend, "comfy_python", side_effect=AssertionError("must not start one")):
                with self.assertRaises(comfybackend.BackendError):
                    with comfybackend.backend(Path("."), mode, Path("unused.log"), explicit="http://127.0.0.1:9"):
                        pass


@unittest.skipUnless(os.name == "nt", "Windows .cmd shim")
class GltfTransformShim(Temp):
    def test_a_global_npm_shim_is_found(self):
        shim = self.tmp / "gltf-transform.cmd"
        shim.write_text("@echo off\r\necho 4.5.1\r\n", encoding="utf-8")
        which = providers.shutil.which
        with mock.patch.object(providers.shutil, "which", side_effect=lambda name: str(shim) if name == "gltf-transform" else None if name == "node" else which(name)):
            command, version, path = providers._gltf_transform(None)
        self.assertEqual(command, [str(shim)])
        self.assertEqual(version, "4.5.1")


class JobLifecycle(Temp):
    def setUp(self):
        super().setUp()
        self.project = Project.init(self.tmp / "project", "Jobs")

    def test_an_interrupted_run_is_cancelled_not_running(self):
        recipe = recipes.get("glb-inspect", self.project)

        def interrupt(_ctx):
            raise KeyboardInterrupt()

        with mock.patch.dict(runner.HANDLERS, {"glb.inspect": interrupt}):
            with self.assertRaises(KeyboardInterrupt):
                runner.execute(self.project, recipe, {"mesh": make_glb(self.tmp / "m.glb")}, {})
        job = Job.latest(self.project)
        self.assertEqual(job.data["status"], "CANCELLED")
        self.assertIsNotNone(job.data["finished"])
        manifest = json.loads((self.project.assets_dir / job.data["asset"] / "asset.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "INCOMPLETE")

    def test_latest_is_the_job_created_last_within_one_second(self):
        for _ in range(3):
            ids = [Job.create(self.project, "r", {}).id for _ in range(12)]
            self.assertEqual(Job.latest(self.project).id, ids[-1])

    def test_latest_still_reads_jobs_written_before_this_version(self):
        old = Job.create(self.project, "r", {})
        del old.data["created_ns"]
        old.save()
        self.assertEqual(Job.latest(self.project).id, old.id)

    def test_lookups_cannot_leave_their_folder(self):
        outside = self.project.root / "evil"
        outside.mkdir()
        (outside / "asset.json").write_text(json.dumps({"id": "evil", "name": "evil"}), encoding="utf-8")
        (outside / "job.json").write_text(json.dumps({"id": "evil"}), encoding="utf-8")
        for query in ("../evil", "..\\evil", "..", str(outside)):
            with self.subTest(query=query):
                with self.assertRaises(StoreError):
                    self.project.asset(query)
                with self.assertRaises(StoreError):
                    Job.load(self.project, query)

    def test_prefix_lookup_still_works(self):
        asset = self.project.create_asset("Sword", "glb-inspect", {})
        self.assertEqual(self.project.asset("sword").id, asset.id)
        self.assertEqual(self.project.asset(asset.id).id, asset.id)


class ProviderSnapshot(Temp):
    def test_one_detection_per_run(self):
        project = Project.init(self.tmp / "project", "Snapshot")
        recipe = recipes.get("glb-inspect", project)
        real = providers._detect
        calls = []
        with mock.patch.object(providers, "_detect", side_effect=lambda p=None: (calls.append(1), real(p))[1]):
            job, _, _ = runner.execute(project, recipe, {"mesh": make_glb(self.tmp / "m.glb")}, {})
        self.assertEqual(job.data["status"], "SUCCEEDED")
        self.assertEqual(len(calls), 1)

    def test_outside_a_run_detection_is_fresh(self):
        calls = []
        with mock.patch.object(providers, "_detect", side_effect=lambda p=None: (calls.append(1), [])[1]):
            providers.detect()
            providers.detect()
            with providers.snapshot():
                providers.detect()
                providers.get("blender")
                with providers.snapshot():
                    providers.tool_versions()
            providers.detect()
        self.assertEqual(len(calls), 4)


class ProbeWalk(Temp):
    def test_a_large_folder_is_not_walked_past_the_cap(self):
        for folder in ("a", "b", "c", "d"):
            (self.tmp / folder).mkdir()
            for index in range(10):
                (self.tmp / folder / f"f{index}.txt").write_text("x", encoding="utf-8")
        seen = []
        real = probe._walk_files

        def counting(path):
            for item in real(path):
                seen.append(item)
                yield item

        with mock.patch.object(probe, "MAX_WALK", 12), mock.patch.object(probe, "_walk_files", counting):
            report = probe.probe(self.tmp)
        self.assertEqual(report["facts"]["files"], 12)
        self.assertTrue(any("stopped after 12" in item["detail"] for item in report["findings"]))
        self.assertLessEqual(len(seen), 13)

    def test_listing_order_is_deterministic(self):
        for name in ("b/z.png", "a/y.png", "c.png"):
            path = self.tmp / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b"x")
        self.assertEqual([p.relative_to(self.tmp).as_posix() for p in probe._walk_files(self.tmp)], ["c.png", "a/y.png", "b/z.png"])



class BlenderQaObjects(unittest.TestCase):
    def test_empty_object_means_every_mesh(self):
        qa = recipes.get("blender-qa")
        self.assertEqual(runner._qa_objects(qa, {"object": ""}), [])
        self.assertEqual(runner._qa_objects(qa, {"object": "Blade Hilt"}), ["Blade", "Hilt"])

    def test_the_pipeline_still_checks_its_crate(self):
        self.assertEqual(runner._qa_objects(recipes.get("blender-pipeline"), {}), ["SM_Crate"])


if __name__ == "__main__":
    unittest.main()
