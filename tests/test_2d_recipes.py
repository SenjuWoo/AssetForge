"""The texture and sprite recipes end to end: what they record, what a later
step makes of an earlier one, and what an export ships."""

import contextlib
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT, make_glb, make_png

sys.path.insert(0, str(ROOT / "src"))

from assetforge import adapters, comfybackend, exporters, images, probe, providers, recipes, runner  # noqa: E402
from assetforge.runner import ProviderMissing, RunFailed  # noqa: E402
from assetforge.store import Job, Project  # noqa: E402

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    PIL_OK = True
except ImportError:  # pragma: no cover
    PIL_OK = False


def surface(path: Path, size=(64, 64), seed=3) -> Path:
    """A soft, drifting picture: a surface that does not tile."""
    rng = random.Random(seed)
    noise = Image.new("L", size)
    noise.putdata([rng.randrange(256) for _ in range(size[0] * size[1])])
    noise = noise.filter(ImageFilter.GaussianBlur(2))
    ramp = Image.linear_gradient("L").rotate(90).resize(size)
    mix = ImageChops.add(noise, ramp, scale=2)
    Image.merge("RGB", (mix, noise, ImageChops.invert(mix))).save(path)
    return path


def subject(path: Path, background=(255, 255, 255)) -> Path:
    image = Image.new("RGB", (80, 60), background)
    ImageDraw.Draw(image).ellipse((20, 10, 59, 49), fill=(200, 30, 30))
    image.save(path)
    return path


def roles(asset) -> dict:
    out: dict = {}
    for item in asset.manifest["artifacts"]:
        out.setdefault(item["role"], []).append(Path(item["path"]).name)
    return out


def checks(asset) -> dict:
    return {item["id"]: item["status"] for item in asset.manifest["validation"]}


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.project = Project.init(self.dir / "project", "2D Test")

    def tearDown(self):
        self.tmp.cleanup()

    def run_recipe(self, recipe_id, inputs=None, **overrides):
        recipe = recipes.get(recipe_id, self.project)
        params = recipes.resolve_params(recipe, {key: str(value) for key, value in overrides.items()})
        return runner.execute(self.project, recipe, inputs or {}, params)

    def test_texture_tileable_records_the_seam_and_a_tiled_preview(self):
        job, asset, _ = self.run_recipe("texture-tileable", {"image": surface(self.dir / "moss.png")})
        self.assertEqual(job.data["status"], "SUCCEEDED")
        found = roles(asset)
        self.assertEqual(found["texture"], ["moss-tileable.png"])
        self.assertIn("moss-tiled.png", found["preview"])
        self.assertEqual(checks(asset)["TEX-SEAM"], "PASS")
        self.assertEqual(checks(asset)["TEX-VISUAL"], "NOT_TESTED")
        self.assertTrue(asset.manifest["primary"]["image"].endswith("moss-tileable.png"))

    def test_a_picture_that_already_tiles_is_kept_as_it_is(self):
        import math
        tile = Image.new("L", (64, 64))
        tile.putdata([int(127 + 120 * math.sin(x * math.tau / 16) * math.cos(y * math.tau / 32)) for y in range(64) for x in range(64)])
        tile.convert("RGB").save(self.dir / "wave.png")
        job, asset, _ = self.run_recipe("texture-tileable", {"image": self.dir / "wave.png"})
        with Image.open(self.dir / "wave.png") as before, Image.open(next(self.project.root.rglob("wave-tileable.png"))) as after:
            self.assertEqual(before.convert("RGB").tobytes(), after.convert("RGB").tobytes())
        self.assertEqual(checks(asset)["TEX-SEAM"], "PASS")

    def test_texture_pbr_writes_the_set_and_exports_it_with_the_material_record(self):
        _, asset, _ = self.run_recipe("texture-pbr", {"image": surface(self.dir / "moss.png")}, convention="directx", tileable="false")
        found = roles(asset)
        self.assertEqual(sorted(found["texture"]), [
            "moss-basecolor.png", "moss-height.png", "moss-metallic.png", "moss-normal.png",
            "moss-occlusion.png", "moss-orm.png", "moss-roughness.png"])
        self.assertEqual(found["data"], ["moss-material.json"])
        state = checks(asset)
        self.assertEqual(state["TEX-NORMAL"], "PASS")
        self.assertEqual(state["TEX-DERIVED"], "NOT_TESTED")
        self.assertEqual(state["TEX-SEAM"], "NOT_TESTED")
        result = exporters.export(self.project, asset, "godot")
        names = sorted(Path(item["path"]).name for item in result["files"])
        self.assertEqual(names, sorted(found["texture"] + found["data"]))
        material = json.loads((Path(result["out_dir"]) / "textures" / "moss-material.json").read_text(encoding="utf-8"))
        self.assertEqual(material["normal_convention"], "directx")
        self.assertFalse(material["tileable"])
        for name in material["maps"].values():
            self.assertTrue((Path(result["out_dir"]) / "textures" / name).is_file(), name)

    def test_texture_pbr_auto_wraps_only_a_picture_that_tiles(self):
        _, asset, _ = self.run_recipe("texture-pbr", {"image": surface(self.dir / "moss.png")})
        material = json.loads(next(self.project.root.rglob("moss-material.json")).read_text(encoding="utf-8"))
        self.assertFalse(material["tileable"])
        flat = self.dir / "flat.png"
        Image.new("RGB", (32, 32), (120, 110, 90)).save(flat)
        self.run_recipe("texture-pbr", {"image": flat})
        material = json.loads(next(self.project.root.rglob("flat-material.json")).read_text(encoding="utf-8"))
        self.assertTrue(material["tileable"])

    def test_forcing_wrap_on_a_picture_that_does_not_tile_is_a_warning(self):
        job, asset, _ = self.run_recipe("texture-pbr", {"image": surface(self.dir / "moss.png")}, tileable="true")
        self.assertEqual(checks(asset)["TEX-SEAM"], "WARNING")
        step = next(item for item in job.data["steps"] if item["name"] == "image.pbr")
        self.assertEqual(step["outcome"], "WARNING")

    def test_bad_numbers_fail_the_job_with_the_reason(self):
        with self.assertRaises((RunFailed, images.ImageError)) as caught:
            self.run_recipe("texture-pbr", {"image": surface(self.dir / "moss.png")}, roughness="2")
        self.assertIn("roughness", str(caught.exception))
        self.assertEqual(Job.latest(self.project).data["status"], "FAILED")

    def test_image_cutout_ships_the_sprite_and_its_anchor(self):
        _, asset, _ = self.run_recipe("image-cutout", {"image": subject(self.dir / "apple.png")}, padding=0, feather=0)
        found = roles(asset)
        self.assertEqual(found["image"], ["apple-cutout.png"])
        self.assertEqual(found["data"], ["apple-cutout.json"])
        self.assertEqual(checks(asset)["CUT-BACKGROUND"], "PASS")
        result = exporters.export(self.project, asset, "generic")
        record = json.loads((Path(result["out_dir"]) / "textures" / "apple-cutout.json").read_text(encoding="utf-8"))
        self.assertEqual(record["image"], "apple-cutout.png")
        self.assertEqual(record["size"], [40, 40])
        self.assertEqual(record["anchor"], [20, 40])
        self.assertEqual(record["offset"], [20, 10])

    def test_pixel_art_takes_a_palette_file(self):
        (self.dir / "two.hex").write_text("101010\nf0f0f0\n", encoding="utf-8")
        _, asset, _ = self.run_recipe("pixel-art", {"image": subject(self.dir / "apple.png"), "palette": self.dir / "two.hex"}, size=20)
        found = roles(asset)
        self.assertEqual(found["image"], ["apple-pixel.png"])
        self.assertIn("apple-pixel-x8.png", found["preview"])
        with Image.open(next(self.project.root.rglob("apple-pixel.png"))) as image:
            self.assertEqual(image.size, (20, 15))
            self.assertLessEqual({color[:3] for _, color in image.getcolors()}, {(16, 16, 16), (240, 240, 240)})
        self.assertEqual(checks(asset)["PIX-PALETTE"], "PASS")

    def test_sprite_slice_ships_frames_and_their_rectangles(self):
        sheet = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
        draw = ImageDraw.Draw(sheet)
        draw.rectangle((2, 2, 12, 12), fill=(255, 0, 0, 255))
        draw.rectangle((18, 2, 28, 12), fill=(0, 0, 255, 255))
        sheet.save(self.dir / "walk.png")
        _, asset, _ = self.run_recipe("sprite-slice", {"image": self.dir / "walk.png"}, columns=2, rows=1)
        found = roles(asset)
        self.assertEqual(found["image"], ["walk_000.png", "walk_001.png"])
        self.assertEqual(found["data"], ["frames.json"])
        result = exporters.export(self.project, asset, "generic")
        self.assertEqual(sorted(Path(item["path"]).name for item in result["files"]), ["frames.json", "walk_000.png", "walk_001.png"])

    def test_atlas_record_is_exported_with_the_atlas(self):
        frames = self.dir / "frames"
        frames.mkdir()
        for index in range(3):
            make_png(frames / f"f{index}.png", size=(8, 8))
        _, asset, _ = self.run_recipe("sprite-atlas", {"source": frames})
        result = exporters.export(self.project, asset, "godot")
        self.assertEqual(sorted(Path(item["path"]).name for item in result["files"]), ["atlas.json", "atlas.png"])


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class GenerateChainTests(unittest.TestCase):
    """comfy-forge is replaced by a stand-in that writes a picture."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.project = Project.init(self.dir / "project", "Chain Test")
        self.calls = []
        self.provider = {"id": "comfy-forge", "available": True, "version": "9.9", "path": str(self.dir), "details": {"presets": 3}}

    def tearDown(self):
        self.tmp.cleanup()

    def fake_generate(self, maker):
        def generate(root, params, out_dir, timeout=900, port=0, init_image=None):
            self.calls.append({"params": dict(params), "port": port, "init_image": init_image})
            maker(out_dir / "0001-render.png")
            suffix = str(params.get("prompt_suffix") or "")
            return {"returncode": 0, "prompt": params["prompt"] + (", " + suffix if suffix else "")}
        return generate

    def run_recipe(self, recipe_id, maker, swarm=(0, "test SwarmUI"), inputs=None, **overrides):
        recipe = recipes.get(recipe_id, self.project)
        params = recipes.resolve_params(recipe, {key: str(value) for key, value in overrides.items()})
        real_get = providers.get
        with mock.patch("assetforge.runner.providers.get", side_effect=lambda pid, project=None: self.provider if pid == "comfy-forge" else real_get(pid, project)), \
             mock.patch("assetforge.runner.comfybackend.swarm", return_value=contextlib.nullcontext(swarm)), \
             mock.patch("assetforge.adapters.comfykit_generate", side_effect=self.fake_generate(maker)):
            return runner.execute(self.project, recipe, inputs or {}, params)

    def test_texture_generate_ships_the_material_not_the_raw_render(self):
        job, asset, _ = self.run_recipe("texture-generate", surface, prompt="mossy cobblestone", width=64, height=64)
        self.assertEqual(job.data["status"], "SUCCEEDED")
        found = roles(asset)
        self.assertEqual(found["intermediate"], ["mossy-cobblestone.png", "mossy-cobblestone-tileable.png"])
        self.assertIn("mossy-cobblestone-basecolor.png", found["texture"])
        self.assertIn("mossy-cobblestone-orm.png", found["texture"])
        state = checks(asset)
        self.assertEqual(state["TEX-SEAM"], "PASS")
        self.assertEqual(state["GEN-VISUAL"], "NOT_TESTED")
        result = exporters.export(self.project, asset, "generic")
        names = {Path(item["path"]).name for item in result["files"]}
        self.assertNotIn("mossy-cobblestone.png", names)
        self.assertNotIn("mossy-cobblestone-tileable.png", names)
        self.assertIn("mossy-cobblestone-material.json", names)
        material = json.loads(next(self.project.root.rglob("mossy-cobblestone-material.json")).read_text(encoding="utf-8"))
        self.assertTrue(material["tileable"])

    def test_the_seed_is_chosen_recorded_and_sent(self):
        _, asset, _ = self.run_recipe("comfy-generate", surface, prompt="a rock")
        sent = self.calls[0]["params"]["seed"]
        self.assertGreaterEqual(sent, 0)
        report = json.loads(next(self.project.root.rglob("image-generation.json")).read_text(encoding="utf-8"))
        self.assertEqual(report["seed"], sent)
        self.assertEqual(asset.manifest["provenance"]["seed"], sent)
        self.assertEqual(asset.manifest["source"]["params"]["seed"], sent)
        self.assertEqual(roles(asset)["image"], ["a-rock.png"])

    def test_generated_files_take_the_given_name_and_keep_their_sidecars(self):
        def two(path):
            surface(path)
            surface(path.with_name("0002-render.png"), seed=9)
            path.with_name(path.name + ".json").write_text("{}", encoding="utf-8")

        _, asset, _ = self.run_recipe("comfy-generate", two, prompt="Mossy, grey cobblestone pavement; hand-painted!", name="Wall Stone")
        self.assertEqual(roles(asset)["image"], ["wall-stone.png", "wall-stone-2.png"])
        self.assertTrue(next(self.project.root.rglob("wall-stone.png.json")).is_file())
        self.assertEqual(asset.manifest["name"], "Wall Stone")

    def test_without_a_name_the_first_words_of_the_prompt_name_the_files(self):
        _, asset, _ = self.run_recipe("comfy-generate", surface, prompt="Mossy, grey cobblestone pavement; hand-painted game texture!")
        self.assertEqual(roles(asset)["image"], ["mossy-grey-cobblestone-pavement-hand.png"])

    def test_a_given_seed_is_kept(self):
        self.run_recipe("comfy-generate", surface, prompt="a rock", seed=77)
        self.assertEqual(self.calls[0]["params"]["seed"], 77)

    def test_a_started_swarmui_port_reaches_comfy_forge(self):
        job, _, _ = self.run_recipe("comfy-generate", surface, swarm=(45123, "temporary SwarmUI"), prompt="a rock")
        self.assertEqual(self.calls[0]["port"], 45123)
        step = next(item for item in job.data["steps"] if item["name"] == "comfykit.generate")
        self.assertIn("temporary SwarmUI", step["detail"])

    def test_an_init_picture_is_copied_into_the_asset_and_sent(self):
        guide = subject(self.dir / "guide.png")
        _, asset, _ = self.run_recipe("comfy-generate", surface, inputs={"init": guide}, prompt="a rock", creativity="0.4")
        sent = self.calls[0]["init_image"]
        self.assertEqual(sent.name, "guide.png")
        self.assertTrue(sent.resolve().is_relative_to(self.project.root.resolve()))
        report = json.loads(next(self.project.root.rglob("image-generation.json")).read_text(encoding="utf-8"))
        self.assertEqual((report["init_image"], report["creativity"]), ("guide.png", "0.4"))

    def test_sprite_generate_cuts_the_render_out(self):
        _, asset, _ = self.run_recipe("sprite-generate", subject, prompt="a red apple")
        found = roles(asset)
        self.assertEqual(found["intermediate"], ["a-red-apple.png"])
        self.assertEqual(found["image"], ["a-red-apple-cutout.png"])
        self.assertIn("plain solid white background", self.calls[0]["params"]["prompt_suffix"])
        report = json.loads(next(self.project.root.rglob("image-generation.json")).read_text(encoding="utf-8"))
        self.assertTrue(report["prompt"].startswith("a red apple, single subject"))

    def test_no_backend_is_a_missing_provider(self):
        recipe = recipes.get("comfy-generate", self.project)
        params = recipes.resolve_params(recipe, {"prompt": "x", "backend": "running"})

        @contextlib.contextmanager
        def refuse(*_args, **_kwargs):
            raise comfybackend.BackendError("SwarmUI is not answering on port 7801")
            yield

        with mock.patch("assetforge.runner.providers.get", return_value=self.provider), \
             mock.patch("assetforge.runner.comfybackend.swarm", side_effect=refuse):
            with self.assertRaises(ProviderMissing):
                runner.execute(self.project, recipe, {}, params)
        self.assertEqual(Job.latest(self.project).data["status"], "FAILED")


class ComfyImageAdapterTests(unittest.TestCase):
    def command(self, params, port=0):
        with mock.patch("assetforge.adapters.shutil.which", return_value="powershell"), \
             mock.patch("assetforge.adapters.run", return_value={"returncode": 0, "stdout": "ok", "stderr": ""}) as run:
            result = adapters.comfykit_generate(Path("C:/comfy-forge"), params, Path("C:/out"), timeout=30, port=port)
            return run.call_args[0][0], result

    def test_steps_cfg_and_port_are_passed_when_set(self):
        command, _ = self.command({"prompt": "x", "steps": 12, "cfg": "4.5"}, port=7900)
        for flag, value in (("-Steps", "12"), ("-Cfg", "4.5"), ("-Port", "7900")):
            self.assertEqual(command[command.index(flag) + 1], value)

    def test_unset_steps_cfg_and_port_leave_the_preset_alone(self):
        command, _ = self.command({"prompt": "x", "steps": 0, "cfg": ""})
        for flag in ("-Steps", "-Cfg", "-Port"):
            self.assertNotIn(flag, command)

    def test_the_suffix_joins_the_prompt(self):
        command, result = self.command({"prompt": "oak planks", "prompt_suffix": "seamless"})
        self.assertEqual(command[command.index("-Prompt") + 1], "oak planks, seamless")
        self.assertEqual(result["prompt"], "oak planks, seamless")

    def test_bad_steps_and_cfg_are_refused_before_anything_runs(self):
        for params in ({"prompt": "x", "steps": 999}, {"prompt": "x", "cfg": "hot"}, {"prompt": "x", "cfg": "99"}):
            with mock.patch("assetforge.adapters.shutil.which", return_value="powershell"), \
                 mock.patch("assetforge.adapters.run") as run:
                with self.assertRaises(adapters.AdapterError, msg=str(params)):
                    adapters.comfykit_generate(Path("C:/comfy-forge"), params, Path("C:/out"))
                run.assert_not_called()

    def test_errors_name_comfy_forge(self):
        with mock.patch("assetforge.adapters.shutil.which", return_value="powershell"), \
             mock.patch("assetforge.adapters.run", return_value={"returncode": 1, "stdout": "", "stderr": "no preset"}):
            with self.assertRaises(adapters.AdapterError) as caught:
                adapters.comfykit_generate(Path("C:/comfy-forge"), {"prompt": "x"}, Path("C:/out"))
        self.assertIn("comfy-forge", str(caught.exception))
        self.assertNotIn("comfy-kit", str(caught.exception))


class SwarmBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.swarm = Path(self.tmp.name) / "SwarmUI"
        (self.swarm / "Data").mkdir(parents=True)
        (self.swarm / "launch-windows.bat").write_text("@echo off\n", encoding="utf-8")
        (self.swarm / "launch-linux.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        python = self.swarm / "dlbackend" / "comfy" / "python_embeded" / "python.exe"
        python.parent.mkdir(parents=True)
        python.write_bytes(b"")
        self.python = python
        self.log = Path(self.tmp.name) / "log" / "swarmui.log"

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_port_is_read_from_the_settings(self):
        self.assertEqual(comfybackend.swarm_port(self.swarm), 7801)
        (self.swarm / "Data" / "Settings.fds").write_text("Network:\n\t#the port\n\tPort: 7955\n\tPortCanChange: true\n", encoding="utf-8")
        self.assertEqual(comfybackend.swarm_port(self.swarm), 7955)

    def test_the_folder_is_the_one_above_comfy_forges_interpreter(self):
        with mock.patch("assetforge.comfybackend.comfy_python", return_value=self.python):
            self.assertEqual(comfybackend.swarm_root(Path("C:/comfy-forge")), self.swarm)
        with mock.patch("assetforge.comfybackend.comfy_python", return_value=Path(self.tmp.name) / "python.exe"):
            with self.assertRaises(comfybackend.BackendError):
                comfybackend.swarm_root(Path("C:/comfy-forge"))

    def test_a_running_swarmui_is_used_as_it_is(self):
        with mock.patch("assetforge.comfybackend.comfy_python", return_value=self.python), \
             mock.patch("assetforge.comfybackend.swarm_alive", return_value=True), \
             mock.patch("assetforge.comfybackend.subprocess.Popen") as popen:
            with comfybackend.swarm(Path("C:/comfy-forge"), "auto", self.log) as (port, how):
                self.assertEqual(port, 0)
                self.assertIn("running SwarmUI on port 7801", how)
            popen.assert_not_called()

    def test_running_mode_never_starts_one(self):
        with mock.patch("assetforge.comfybackend.comfy_python", return_value=self.python), \
             mock.patch("assetforge.comfybackend.swarm_alive", return_value=False), \
             mock.patch("assetforge.comfybackend.subprocess.Popen") as popen:
            with self.assertRaises(comfybackend.BackendError):
                with comfybackend.swarm(Path("C:/comfy-forge"), "running", self.log):
                    pass
            popen.assert_not_called()

    def test_auto_starts_one_without_a_browser_and_stops_it(self):
        proc = mock.Mock()
        proc.poll.return_value = None
        answers = iter([False, False, True])  # the settings port, then the new one
        with mock.patch("assetforge.comfybackend.comfy_python", return_value=self.python), \
             mock.patch("assetforge.comfybackend.swarm_alive", side_effect=lambda *a, **k: next(answers)), \
             mock.patch("assetforge.comfybackend.time.sleep"), \
             mock.patch("assetforge.comfybackend._stop") as stop, \
             mock.patch("assetforge.comfybackend.subprocess.Popen", return_value=proc) as popen:
            with comfybackend.swarm(Path("C:/comfy-forge"), "auto", self.log) as (port, how):
                self.assertGreater(port, 0)
                self.assertIn("temporary SwarmUI", how)
                stop.assert_not_called()
            stop.assert_called_once_with(proc)
        line = popen.call_args[0][0]
        text = line if isinstance(line, str) else " ".join(line)
        self.assertIn("--launch_mode none", text)
        self.assertIn(f"--port {port}", text)
        self.assertEqual(Path(popen.call_args[1]["cwd"]), self.swarm)

    def test_a_swarmui_that_dies_while_starting_is_reported_and_reaped(self):
        proc = mock.Mock()
        proc.poll.return_value = 1
        proc.returncode = 1
        with mock.patch("assetforge.comfybackend.comfy_python", return_value=self.python), \
             mock.patch("assetforge.comfybackend.swarm_alive", return_value=False), \
             mock.patch("assetforge.comfybackend._stop") as stop, \
             mock.patch("assetforge.comfybackend.subprocess.Popen", return_value=proc):
            with self.assertRaises(comfybackend.BackendError) as caught:
                with comfybackend.swarm(Path("C:/comfy-forge"), "start", self.log):
                    pass
            stop.assert_called_once_with(proc)
        self.assertIn("exited during startup", str(caught.exception))

    def test_an_unknown_mode_is_refused(self):
        with self.assertRaises(comfybackend.BackendError):
            with comfybackend.swarm(Path("C:/comfy-forge"), "maybe", self.log):
                pass


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class ExportHygieneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.project = Project.init(self.dir / "project", "Export Hygiene")

    def tearDown(self):
        self.tmp.cleanup()

    def texture_asset(self):
        asset = self.project.create_asset("Tex", "image-prep", {})
        image = make_png(asset.path("outputs", "wall.png"), alpha=False)
        asset.add_artifact(image, "texture", "deliverable")
        asset.set_primary("image", image)
        return asset

    def test_a_second_export_leaves_no_file_from_the_first(self):
        asset = self.texture_asset()
        first = exporters.export(self.project, asset, "generic")
        stale = Path(first["out_dir"]) / "textures" / "old-name.png"
        stale.write_bytes(b"left over")
        exporters.export(self.project, asset, "generic")
        self.assertFalse(stale.exists())
        self.assertTrue((Path(first["out_dir"]) / "textures" / "wall.png").is_file())

    def test_a_mesh_export_is_cleared_too(self):
        asset = self.project.create_asset("Tri", "glb-inspect", {})
        record = asset.add_input(make_glb(self.dir / "tri.glb"), "mesh")
        asset.add_artifact(self.project.root / record["path"], "mesh", "source")
        asset.set_primary("mesh", self.project.root / record["path"])
        first = exporters.export(self.project, asset, "generic")
        stale = Path(first["out_dir"]) / "stale.glb"
        stale.write_bytes(b"x")
        exporters.export(self.project, asset, "generic")
        self.assertFalse(stale.exists())

    def test_two_pictures_with_one_name_are_refused_before_anything_is_written(self):
        asset = self.texture_asset()
        asset.path("outputs", "other").mkdir(parents=True)
        twin = make_png(asset.path("outputs", "other", "wall.png"), alpha=False)
        asset.add_artifact(twin, "texture", "second")
        with self.assertRaises(exporters.ExportError) as caught:
            exporters.export(self.project, asset, "generic")
        self.assertIn("wall.png", str(caught.exception))
        self.assertFalse(asset.path("exports", "generic").exists())

    def test_a_record_naming_a_picture_the_asset_lacks_fails_validation(self):
        asset = self.texture_asset()
        record = asset.path("outputs", "sheet.json")
        record.write_text(json.dumps({"schema": 1, "image": "missing.png", "frames": []}), encoding="utf-8")
        asset.add_artifact(record, "data", "sprite-metadata")
        report = exporters.validate_asset(self.project, asset)
        data = next(item for item in report["checks"] if item["id"] == "DATA-001")
        self.assertEqual(data["status"], "FAIL")
        self.assertIn("missing.png", data["detail"])
        record.write_text(json.dumps({"schema": 1, "image": "wall.png", "frames": [{}]}), encoding="utf-8")
        asset.add_artifact(record, "data", "sprite-metadata")
        report = exporters.validate_asset(self.project, asset)
        data = [item for item in report["checks"] if item["id"] == "DATA-001"]
        self.assertEqual([item["status"] for item in data], ["PASS"])

    def test_a_broken_record_fails_validation(self):
        asset = self.texture_asset()
        record = asset.path("outputs", "sheet.json")
        record.write_text("{not json", encoding="utf-8")
        asset.add_artifact(record, "data", "sprite-metadata")
        report = exporters.validate_asset(self.project, asset)
        self.assertEqual(next(item for item in report["checks"] if item["id"] == "DATA-001")["status"], "FAIL")


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class ImageLimitsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.source = make_png(self.dir / "s.png", size=(16, 8))

    def tearDown(self):
        self.tmp.cleanup()

    def test_sizes_out_of_range_are_refused(self):
        for bad in ({"width": -4}, {"height": -1}, {"width": 100000}, {"quality": 0}, {"quality": 101}):
            with self.assertRaises(images.ImageError, msg=str(bad)):
                images.convert_image(self.source, self.dir / "o.png", **bad)
        self.assertFalse((self.dir / "o.png").exists())

    def test_a_one_sided_resize_never_rounds_to_zero(self):
        result = images.convert_image(self.source, self.dir / "o.png", width=1)
        self.assertEqual((result["width"], result["height"]), (1, 1))

    def test_tga_is_written(self):
        result = images.convert_image(self.source, self.dir / "o.tga", fmt="tga")
        self.assertEqual(result["format"], "TGA")
        self.assertEqual((result["width"], result["height"]), (16, 8))
        self.assertTrue(result["has_alpha"])

    def test_sheet_lays_rows_out_as_given(self):
        a = make_png(self.dir / "a.png", size=(4, 4))
        b = make_png(self.dir / "b.png", size=(4, 4))
        c = make_png(self.dir / "c.png", size=(4, 4))
        sheet = images.make_sheet([[a, b], [c]], self.dir / "sheet.png", padding=1)
        self.assertEqual((sheet["width"], sheet["height"], sheet["columns"], sheet["rows"]), (11, 11, 2, 2))
        self.assertEqual([(f["name"], f["x"], f["y"]) for f in sheet["frames"]], [("a.png", 1, 1), ("b.png", 6, 1), ("c.png", 1, 6)])
        with Image.open(self.dir / "sheet.png") as image:
            self.assertEqual(image.getpixel((7, 7))[3], 0)  # the cell with no frame stays empty

    def test_an_oversized_sheet_is_refused(self):
        big = make_png(self.dir / "big.png", size=(4096, 8))
        with self.assertRaises(images.ImageError):
            images.make_sheet([[big, big, big]], self.dir / "sheet.png")


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class DdsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.project = Project.init(self.dir / "project", "DDS Test")

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_command_carries_compression_and_mipmaps(self):
        target = self.dir / "o.dds"

        def fake_run(command, **_kwargs):
            target.write_bytes(b"DDS " + bytes(200))
            return {"returncode": 0, "stdout": "", "stderr": ""}

        with mock.patch("assetforge.adapters.run", side_effect=fake_run) as run:
            adapters.magick_dds({"path": "magick"}, self.dir / "in.png", target, compression="dxt1", mipmaps=False)
        command = run.call_args[0][0]
        self.assertIn("dds:compression=dxt1", command)
        self.assertIn("dds:mipmaps=0", command)
        self.assertEqual(command[-1], str(target))

    def test_a_file_that_is_not_dds_is_refused(self):
        target = self.dir / "o.dds"

        def fake_run(command, **_kwargs):
            target.write_bytes(b"PNG " + bytes(200))
            return {"returncode": 0, "stdout": "", "stderr": ""}

        with mock.patch("assetforge.adapters.run", side_effect=fake_run):
            with self.assertRaises(adapters.AdapterError):
                adapters.magick_dds({"path": "magick"}, self.dir / "in.png", target)
        with self.assertRaises(adapters.AdapterError):
            adapters.magick_dds({"path": "magick"}, self.dir / "in.png", target, compression="bc7")

    def test_a_dry_run_names_imagemagick_only_for_dds(self):
        recipe = recipes.get("image-prep", self.project)
        source = make_png(self.dir / "s.png")
        plain = runner.plan(recipe, {"image": source}, recipes.resolve_params(recipe, {}), self.project)
        dds = runner.plan(recipe, {"image": source}, recipes.resolve_params(recipe, {"format": "dds"}), self.project)
        self.assertNotIn("imagemagick", plain["providers"])
        self.assertIn("imagemagick", dds["providers"])

    def test_real_imagemagick_writes_a_dds_pillow_reads(self):
        if not providers.get("imagemagick").get("available"):
            self.skipTest("ImageMagick is not installed")
        recipe = recipes.get("image-prep", self.project)
        source = make_png(self.dir / "s.png", size=(64, 64), alpha=False)
        params = recipes.resolve_params(recipe, {"format": "dds"})
        job, asset, _ = runner.execute(self.project, recipe, {"image": source}, params)
        target = next(self.project.root.rglob("s.dds"))
        self.assertEqual(target.read_bytes()[:4], b"DDS ")
        step = next(item for item in job.data["steps"] if item["name"] == "image.convert")
        self.assertIn("dxt1", step["detail"])
        self.assertEqual(images.inspect_image(target)["width"], 64)
        self.assertFalse(list(asset.path("work").glob("*.png")))


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class ProbeRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def routes(self, path):
        report = probe.probe(path)
        return report, [item["recipe"] for item in report["recommend"]]

    def test_a_subject_on_a_plain_background_goes_to_cutout(self):
        report, found = self.routes(subject(self.dir / "apple.png"))
        self.assertIn("image-cutout", found)
        self.assertNotIn("texture-pbr", found)
        self.assertEqual(report["facts"]["looks_like"], "subject on a plain background")

    def test_a_surface_that_does_not_tile_goes_to_tileable_then_pbr(self):
        report, found = self.routes(surface(self.dir / "moss.png"))
        self.assertEqual(found[1:], ["texture-tileable", "texture-pbr"])
        self.assertEqual(report["facts"]["tiles"], "FAIL")

    def test_a_cut_out_sprite_goes_to_pixel_art_and_slicing(self):
        image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((10, 10, 29, 29), fill=(0, 200, 0, 255))
        image.save(self.dir / "s.png")
        _, found = self.routes(self.dir / "s.png")
        self.assertEqual(found[1:], ["pixel-art", "sprite-slice"])

    def test_a_named_channel_map_still_goes_to_texture_pack_only(self):
        Image.new("L", (32, 32), 90).save(self.dir / "wall_roughness.png")
        _, found = self.routes(self.dir / "wall_roughness.png")
        self.assertEqual(found, ["image-prep", "texture-pack"])

    def test_a_glb_is_offered_sprite_rendering(self):
        _, found = self.routes(make_glb(self.dir / "tri.glb"))
        self.assertIn("sprite-render", found)

    def test_every_recommended_recipe_exists(self):
        known = set(recipes.load_all())
        for path in (subject(self.dir / "a.png"), surface(self.dir / "b.png"), make_glb(self.dir / "c.glb")):
            for item in probe.probe(path)["recommend"]:
                self.assertIn(item["recipe"], known | {"probe"})


if __name__ == "__main__":
    unittest.main()
