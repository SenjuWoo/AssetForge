"""What AssetForge asks of comfy-forge: optional `generate` arguments checked
against the installed script, image to 3D through `TOOLS/model3d.py`, and the
comfy-3d recipe built on it. comfy-forge itself is a stand-in here."""

import contextlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT, make_glb, make_png

sys.path.insert(0, str(ROOT / "src"))

from assetforge import adapters, exporters, providers, recipes, runner  # noqa: E402
from assetforge.runner import ProviderMissing  # noqa: E402
from assetforge.store import Job, Project  # noqa: E402

OLD_PARAMS = '''[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [string]$Verb = 'status',
  [string]$Preset = 'x',
  [string]$Prompt = 'y',
  [int]$Steps = 0,
  [double]$Cfg = 0,
  [int]$Port = 0
)
$ErrorActionPreference = 'Stop'
[string]$Negative = 'not a parameter: it is below the block'
'''
NEW_PARAMS = OLD_PARAMS.replace("  [int]$Port = 0\n", '''  [string]$Negative = '',
  [string]$InitImage = '',
  [double]$Creativity = -1,
  [string[]]$Lora = @(),
  [switch]$Transparent,
  [switch]$Tileable,
  [double]$Upscale = 0,
  [int]$Port = 0
''')

# Stands in for comfy-forge's TOOLS/model3d.py generate: same arguments, same
# closing JSON line, and a real GLB copied into the folder it was given.
STUB_MODEL3D = r'''
import argparse, json, os, shutil, sys
parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="verb")
g = sub.add_parser("generate")
g.add_argument("--variant"); g.add_argument("--image"); g.add_argument("--url"); g.add_argument("--no-start", action="store_true")
g.add_argument("--out"); g.add_argument("--timeout"); g.add_argument("--name", default="model"); g.add_argument("--seed")
args = parser.parse_args()
mode = os.environ.get("STUB_MODE", "ok")
print(f"..   variant {args.variant} seed {args.seed} url {args.url} no_start {args.no_start}")
if mode == "fail":
    print("FAIL missing model file pixal3d_int8_convrot.safetensors (Install-3DModels.ps1 -Set pixal3d)")
    sys.exit(1)
if mode == "nojson":
    print("ok   rendered")
    sys.exit(0)
folder = os.environ["STUB_ELSEWHERE"] if mode == "outside" else args.out
os.makedirs(folder, exist_ok=True)
model = os.path.join(folder, args.name + ".glb")
shutil.copyfile(os.environ["STUB_GLB"], model)
with open(os.path.join(args.out, "args.json"), "w", encoding="utf-8") as fh:
    json.dump(vars(args), fh)
print("ok   rendered    in 1s")
print(json.dumps({"variant": args.variant, "name": args.name, "files": [model], "model": model, "splat": None,
                  "game_ready": None, "triangles": 699878, "image": args.image}))
'''


def forge(folder: Path, params: str = NEW_PARAMS, model3d: bool = True) -> Path:
    root = folder / "comfy-forge"
    (root / "TOOLS").mkdir(parents=True)
    (root / "presets").mkdir()
    (root / "presets" / "presets.json").write_text("{}", encoding="utf-8")
    (root / "TOOLS" / "image-stack.ps1").write_text(params, encoding="utf-8")
    if model3d:
        (root / "TOOLS" / "model3d.py").write_text(STUB_MODEL3D, encoding="utf-8")
    return root


class GenerateOptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def command(self, root, params, init_image=None):
        with mock.patch("assetforge.adapters.shutil.which", return_value="powershell"), \
             mock.patch("assetforge.adapters.run", return_value={"returncode": 0, "stdout": "", "stderr": ""}) as run:
            result = adapters.comfykit_generate(root, {"prompt": "x", **params}, self.dir / "out", init_image=init_image)
            return run.call_args[0][0], result

    def refused(self, root, params, init_image=None):
        with mock.patch("assetforge.adapters.shutil.which", return_value="powershell"), \
             mock.patch("assetforge.adapters.run") as run:
            with self.assertRaises(adapters.AdapterError) as caught:
                adapters.comfykit_generate(root, {"prompt": "x", **params}, self.dir / "out", init_image=init_image)
            run.assert_not_called()
        return str(caught.exception)

    def test_only_the_declared_parameters_are_read(self):
        old, new = forge(self.dir / "old", OLD_PARAMS), forge(self.dir / "new")
        self.assertEqual(adapters.comfy_generate_flags(old), {"Verb", "Preset", "Prompt", "Steps", "Cfg", "Port"})
        self.assertLessEqual({"Negative", "InitImage", "Creativity", "Lora", "Transparent", "Tileable", "Upscale"},
                             adapters.comfy_generate_flags(new))
        self.assertEqual(adapters.comfy_generate_flags(self.dir / "nowhere"), set())

    def test_options_are_passed_to_a_comfy_forge_that_has_them(self):
        root = forge(self.dir)
        picture = make_png(self.dir / "guide.png")
        command, result = self.command(root, {"negative": "blurry, text", "creativity": "0.45", "lora": "ink:0.8,grain",
                                              "transparent": True, "upscale": "1.5", "seamless": True}, init_image=picture)
        for flag, value in (("-Negative", "blurry, text"), ("-InitImage", str(picture)), ("-Creativity", "0.45"),
                            ("-Lora", "ink:0.8,grain"), ("-Upscale", "1.5")):
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assertIn("-Transparent", command)
        self.assertIn("-Tileable", command)
        self.assertTrue(result["seamless"])

    def test_an_older_comfy_forge_is_told_what_it_lacks_before_anything_runs(self):
        root = forge(self.dir, OLD_PARAMS)
        message = self.refused(root, {"negative": "blurry", "transparent": True})
        self.assertIn("-Negative", message)
        self.assertIn("-Transparent", message)
        self.assertIn("0.11.0", message)

    def test_seamless_is_asked_for_only_when_set(self):
        old, new = forge(self.dir / "old", OLD_PARAMS), forge(self.dir / "new")
        command, result = self.command(new, {"seamless": False})
        self.assertNotIn("-Tileable", command)
        self.assertFalse(result["seamless"])
        command, result = self.command(new, {"seamless": True})
        self.assertIn("-Tileable", command)
        self.assertIn("-Tileable", self.refused(old, {"seamless": True}))

    def test_plain_renders_never_read_the_script(self):
        with mock.patch("assetforge.adapters.comfy_generate_flags") as probe:
            command, _ = self.command(self.dir / "nowhere", {"seamless": False, "transparent": False, "negative": ""})
            probe.assert_not_called()
        self.assertNotIn("-Negative", command)

    def test_bad_values_are_refused(self):
        root = forge(self.dir)
        picture = make_png(self.dir / "guide.png")
        self.assertIn("init", self.refused(root, {"creativity": "0.5"}))
        self.assertIn("creativity", self.refused(root, {"creativity": "2"}, init_image=picture))
        self.assertIn("creativity", self.refused(root, {"creativity": "lots"}, init_image=picture))
        self.assertIn("upscale", self.refused(root, {"upscale": "9"}))


class Model3dAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.root = forge(self.dir)
        self.glb = make_glb(self.dir / "sculpt.glb")
        self.picture = make_png(self.dir / "axe.png")
        self.env = {"STUB_GLB": str(self.glb), "STUB_ELSEWHERE": str(self.dir / "elsewhere")}

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, mode="ok", **options):
        with mock.patch.dict(os.environ, {**self.env, "STUB_MODE": mode}):
            return adapters.comfy_model3d(self.root, "http://127.0.0.1:8188", self.picture, self.dir / "out", **options)

    def test_the_model_comes_back_from_the_assigned_folder(self):
        result = self.call(name="rune-axe", seed=7, variant="pixal3d-multi")
        self.assertEqual(result["model"], self.dir / "out" / "rune-axe.glb")
        self.assertEqual(result["triangles"], 699878)
        sent = json.loads((self.dir / "out" / "args.json").read_text(encoding="utf-8"))
        self.assertEqual((sent["variant"], sent["seed"], sent["url"], sent["no_start"]), ("pixal3d-multi", "7", "http://127.0.0.1:8188", True))
        self.assertEqual(sent["image"], str(self.picture))

    def test_the_tools_own_reason_is_passed_on(self):
        with self.assertRaises(adapters.AdapterError) as caught:
            self.call("fail")
        self.assertIn("pixal3d_int8_convrot.safetensors", str(caught.exception))

    def test_success_without_a_result_line_is_refused(self):
        with self.assertRaises(adapters.AdapterError) as caught:
            self.call("nojson")
        self.assertIn("no result line", str(caught.exception))

    def test_a_model_written_elsewhere_is_refused(self):
        with self.assertRaises(adapters.AdapterError) as caught:
            self.call("outside")
        self.assertIn("not in the assigned folder", str(caught.exception))

    def test_an_unknown_variant_is_refused_before_anything_runs(self):
        with mock.patch("assetforge.adapters.run") as run:
            with self.assertRaises(adapters.AdapterError):
                self.call(variant="idol")
            run.assert_not_called()


class Comfy3dRecipeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.project = Project.init(self.dir / "project", "3D Test")
        self.glb = make_glb(self.dir / "sculpt.glb")
        self.picture = make_png(self.dir / "axe.png")
        self.env = {"STUB_GLB": str(self.glb), "STUB_ELSEWHERE": str(self.dir / "elsewhere"), "STUB_MODE": "ok"}

    def tearDown(self):
        self.tmp.cleanup()

    def run_recipe(self, root, **overrides):
        recipe = recipes.get("comfy-3d", self.project)
        params = recipes.resolve_params(recipe, {key: str(value) for key, value in overrides.items()})
        fake = {
            "comfy-forge": {"id": "comfy-forge", "available": True, "version": "0.11.0", "path": str(root), "details": {"presets": 1}},
            "blender": {"id": "blender", "available": True, "version": "9.9", "path": "blender"},
        }
        real_get = providers.get

        def collapse(provider, source, target, tris, texture, timeout=900):
            shutil.copyfile(source, target)
            return {"report": {"textures": []}}

        with mock.patch.dict(os.environ, self.env), \
             mock.patch("assetforge.runner.providers.get", side_effect=lambda pid, project=None: fake.get(pid) or real_get(pid, project)), \
             mock.patch("assetforge.runner.comfybackend.backend", return_value=contextlib.nullcontext(("http://127.0.0.1:8188", "test ComfyUI"))), \
             mock.patch("assetforge.adapters.blender_gameready", side_effect=collapse) as collapsed:
            result = runner.execute(self.project, recipe, {"image": self.picture}, params)
        return result, collapsed

    def test_the_picture_becomes_a_game_ready_mesh_with_the_sculpt_kept(self):
        (job, asset, _), collapsed = self.run_recipe(forge(self.dir), seed=11)
        self.assertEqual(job.data["status"], "SUCCEEDED")
        meshes = {item["label"]: Path(item["path"]).name for item in asset.manifest["artifacts"] if item["role"] == "mesh"}
        self.assertEqual(meshes, {"source": "axe.glb", "gameready": "axe-gameready.glb"})
        self.assertTrue(asset.manifest["primary"]["mesh"].endswith("axe-gameready.glb"))
        self.assertEqual(collapsed.call_args[0][1].name, "axe.glb")      # the sculpt is what gets collapsed
        report = json.loads(next(self.project.root.rglob("model3d-generation.json")).read_text(encoding="utf-8"))
        self.assertEqual((report["seed"], report["variant"], report["image"]), (11, "pixal3d", "axe.png"))
        state = {item["id"]: item["status"] for item in asset.manifest["validation"]}
        self.assertEqual(state["GEN-VISUAL"], "NOT_TESTED")
        exported = exporters.export(self.project, asset, "generic")
        self.assertTrue(exported["source"].endswith("axe-gameready.glb"))

    def test_a_seed_is_chosen_and_recorded_when_none_is_given(self):
        (_, asset, _), _ = self.run_recipe(forge(self.dir))
        self.assertGreaterEqual(asset.manifest["provenance"]["seed"], 0)

    def test_a_comfy_forge_without_the_tool_is_a_missing_provider(self):
        with self.assertRaises(ProviderMissing) as caught:
            self.run_recipe(forge(self.dir, model3d=False))
        self.assertIn("0.11.0", str(caught.exception))
        self.assertEqual(Job.latest(self.project).data["status"], "FAILED")

    def test_the_tools_failure_fails_the_job_with_its_reason(self):
        self.env["STUB_MODE"] = "fail"
        with self.assertRaises(adapters.AdapterError):
            self.run_recipe(forge(self.dir))
        self.assertIn("pixal3d_int8_convrot", Job.latest(self.project).data["error"])


class ProviderDetailTests(unittest.TestCase):
    def test_comfy_forge_reports_whether_it_has_image_to_3d(self):
        with tempfile.TemporaryDirectory() as tmp:
            for has in (True, False):
                root = forge(Path(tmp) / str(has), model3d=has)
                with mock.patch.dict(os.environ, {"COMFY_FORGE_ROOT": str(root)}):
                    item = providers.get("comfy-forge")
                self.assertTrue(item["available"])
                self.assertEqual(item["details"]["model3d"], has)
                self.assertEqual("model3d.generate.delegated" in item["capabilities"], has)


if __name__ == "__main__":
    unittest.main()
