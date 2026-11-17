"""sprite-render: the sheet and record AssetForge assembles from rendered
frames, and a real Blender run that proves which way each facing looks."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT, make_glb

sys.path.insert(0, str(ROOT / "src"))

from assetforge import adapters, exporters, providers, recipes, runner  # noqa: E402
from assetforge.runner import RunFailed  # noqa: E402
from assetforge.store import Job, Project  # noqa: E402
from assetforge.util import run  # noqa: E402

try:
    from PIL import Image, ImageDraw
    PIL_OK = True
except ImportError:  # pragma: no cover
    PIL_OK = False

# A body with a blue nose on its front and a green block on its right-hand
# side, turning once on the spot ("spin") and bobbing ("bob").
MARKER_SCRIPT = r'''
import bpy, sys, math
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)

def box(name, size, at, color):
    bpy.ops.mesh.primitive_cube_add(size=1, location=at)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*color, 1)
    mat.diffuse_color = (*color, 1)
    obj.data.materials.append(mat)
    return obj

root = bpy.data.objects.new("Root", None)
bpy.context.scene.collection.objects.link(root)
body = box("Body", (0.6, 0.6, 1.0), (0, 0, 0.5), (0.7, 0.7, 0.7))
nose = box("Nose", (0.2, 0.5, 0.2), (0, -0.5, 0.7), (0.0, 0.0, 1.0))      # -Y is the front
side = box("Side", (0.5, 0.2, 0.2), (-0.5, 0, 0.4), (0.0, 1.0, 0.0))      # -X is its right
for obj in (body, nose, side):
    obj.parent = root

def clip(name, prop, index, keys):
    root.animation_data_create()
    action = bpy.data.actions.new(name)
    root.animation_data.action = action
    for frame, value in keys:
        getattr(root, prop)[index] = value
        root.keyframe_insert(prop, index=index, frame=frame)
    track = root.animation_data.nla_tracks.new()
    track.name = name
    track.strips.new(name, int(keys[0][0]), action)
    root.animation_data.action = None
    getattr(root, prop)[index] = 0.0

if "--animated" in sys.argv:
    clip("bob", "location", 2, [(1, 0.0), (7, 0.6), (13, 0.0)])
    clip("spin", "rotation_euler", 2, [(1, 0.0), (13, math.pi), (25, 2 * math.pi)])
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_animations=True, export_animation_mode="NLA_TRACKS")
'''


def frame(path: Path, size=32, box=(8, 8, 23, 27), color=(200, 60, 60, 255)) -> None:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if box:
        ImageDraw.Draw(image).rectangle(box, fill=color)
    image.save(path)


def fake_render(blank=(), touching=()):
    """Stand-in for Blender: two animations, two facings, two frames each."""
    def render(provider, source, out_dir, **options):
        out_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for animation in ("idle", "walk"):
            for facing in ("south", "east"):
                for index in range(2):
                    name = f"{animation}__{facing}__{index:02d}.png"
                    box = None if name in blank else (0, 8, 23, 27) if name in touching else (8, 8, 23, 27)
                    frame(out_dir / name, size=options["size"], box=box)
                    files.append({"file": name, "animation": animation, "direction": facing, "index": index, "frame": 1.0 + index})
        return {
            "ok": True, "blender": "9.9.9", "engine": "BLENDER_WORKBENCH", "size": options["size"], "pitch": 30.0,
            "ortho_scale": 2.0, "pixels_per_unit": options["size"] / 2.0,
            "directions": [{"name": "south", "yaw": 0.0, "anchor": [16.0, 26.5]}, {"name": "east", "yaw": 90.0, "anchor": [16.0, 27.5]}],
            "pivot": "origin", "animations": [{"name": "idle", "frames": 2, "source_frames": [1, 13], "seconds": 0.5, "fps": 4.0},
                           {"name": "walk", "frames": 2, "source_frames": [1, 25], "seconds": 1.0, "fps": 2.0}],
            "available_animations": ["idle", "walk"], "meshes": 1, "files": files, "notes": [],
        }
    return render


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class SheetAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.project = Project.init(self.dir / "project", "Sprite Test")
        self.glb = make_glb(self.dir / "hero.glb")
        self.blender = {"id": "blender", "available": True, "version": "9.9.9", "path": "blender"}

    def tearDown(self):
        self.tmp.cleanup()

    def render(self, **fake):
        recipe = recipes.get("sprite-render", self.project)
        params = recipes.resolve_params(recipe, {"size": "32", "directions": "4"})
        real_get = providers.get
        with mock.patch("assetforge.runner.providers.get", side_effect=lambda pid, project=None: self.blender if pid == "blender" else real_get(pid, project)), \
             mock.patch("assetforge.adapters.blender_sprites", side_effect=fake_render(**fake)) as called:
            result = runner.execute(self.project, recipe, {"mesh": self.glb}, params)
        return result, called

    def test_the_sheet_has_one_row_per_animation_and_facing(self):
        (job, asset, _), called = self.render()
        self.assertEqual(job.data["status"], "SUCCEEDED")
        self.assertEqual(called.call_args[1]["directions"], 4)
        record = json.loads(next(self.project.root.rglob("hero-sheet.json")).read_text(encoding="utf-8"))
        self.assertEqual((record["width"], record["height"]), (64, 128))
        self.assertEqual(record["frame_size"], [32, 32])
        self.assertEqual([(f["animation"], f["direction"], f["index"], f["x"], f["y"]) for f in record["frames"]], [
            ("idle", "south", 0, 0, 0), ("idle", "south", 1, 32, 0),
            ("idle", "east", 0, 0, 32), ("idle", "east", 1, 32, 32),
            ("walk", "south", 0, 0, 64), ("walk", "south", 1, 32, 64),
            ("walk", "east", 0, 0, 96), ("walk", "east", 1, 32, 96)])
        self.assertEqual(record["frames"][2]["anchor"], [16.0, 27.5])
        self.assertEqual([a["name"] for a in record["animations"]], ["idle", "walk"])
        self.assertTrue(all(a["loop"] for a in record["animations"]))
        with Image.open(next(self.project.root.rglob("hero-sheet.png"))) as sheet:
            self.assertEqual(sheet.getpixel((16, 16))[:3], (200, 60, 60))
            self.assertEqual(sheet.getpixel((1, 1))[3], 0)

    def test_frames_are_evidence_and_the_sheet_is_what_ships(self):
        (_, asset, _), _ = self.render()
        by_role: dict = {}
        for item in asset.manifest["artifacts"]:
            by_role.setdefault(item["role"], []).append(Path(item["path"]).name)
        self.assertEqual(len(by_role["sprite-frame"]), 8)
        self.assertEqual(by_role["texture"], ["hero-sheet.png"])
        self.assertEqual(by_role["data"], ["hero-sheet.json"])
        state = {item["id"]: item["status"] for item in asset.manifest["validation"]}
        self.assertEqual(state["SPRITE-RENDER"], "PASS")
        self.assertEqual(state["SPRITE-EMPTY"], "PASS")
        self.assertEqual(state["SPRITE-CLIP"], "PASS")
        self.assertEqual(state["SPRITE-VISUAL"], "NOT_TESTED")
        self.assertNotIn("mesh", by_role)   # the model is an input, not something this asset ships
        result = exporters.export(self.project, asset, "godot")
        self.assertEqual(result["kind"], "texture")
        self.assertEqual(sorted(Path(item["path"]).name for item in result["files"]), ["hero-sheet.json", "hero-sheet.png"])

    def test_a_frame_touching_its_edge_is_a_warning(self):
        (job, asset, _), _ = self.render(touching=("walk__east__01.png",))
        state = {item["id"]: item for item in asset.manifest["validation"]}
        self.assertEqual(state["SPRITE-CLIP"]["status"], "WARNING")
        self.assertIn("walk__east__01.png", state["SPRITE-CLIP"]["detail"])
        self.assertEqual(job.data["status"], "SUCCEEDED")

    def test_an_empty_frame_fails_the_job(self):
        with self.assertRaises(RunFailed) as caught:
            self.render(blank=("idle__south__00.png",))
        self.assertIn("idle__south__00.png", str(caught.exception))
        self.assertEqual(Job.latest(self.project).data["status"], "FAILED")

    def test_a_report_without_its_files_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            line = "SPRITES " + json.dumps({"ok": True, "files": [{"file": "gone.png"}]})
            with mock.patch("assetforge.adapters.run", return_value={"returncode": 0, "stdout": line, "stderr": ""}):
                with self.assertRaises(adapters.AdapterError) as caught:
                    adapters.blender_sprites({"path": "blender"}, self.glb, Path(tmp) / "frames")
        self.assertIn("gone.png", str(caught.exception))

    def test_blenders_own_reason_is_passed_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            line = "SPRITES " + json.dumps({"ok": False, "error": "ValueError: the file has no mesh to render"})
            with mock.patch("assetforge.adapters.run", return_value={"returncode": 1, "stdout": line, "stderr": ""}):
                with self.assertRaises(adapters.AdapterError) as caught:
                    adapters.blender_sprites({"path": "blender"}, self.glb, Path(tmp) / "frames")
        self.assertIn("no mesh to render", str(caught.exception))


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class RealBlenderSpriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blender = providers.get("blender")
        if not cls.blender.get("available"):
            raise unittest.SkipTest("real Blender is required")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        script = cls.dir / "marker.py"
        script.write_text(MARKER_SCRIPT, encoding="utf-8")
        cls.still = cls.dir / "marker.glb"
        cls.moving = cls.dir / "mover.glb"
        for target, extra in ((cls.still, []), (cls.moving, ["--animated"])):
            result = run([cls.blender["path"], "-b", "--factory-startup", "--python", str(script), "--", str(target), *extra], timeout=300)
            if result["returncode"] != 0 or not target.is_file():
                raise unittest.SkipTest(f"Blender could not write the fixture: {(result['stderr'] or result['stdout'])[-300:]}")
        cls.project = Project.init(cls.dir / "project", "Real Sprites")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, source, **overrides):
        recipe = recipes.get("sprite-render", self.project)
        params = recipes.resolve_params(recipe, {key: str(value) for key, value in overrides.items()})
        job, asset, _ = runner.execute(self.project, recipe, {"mesh": source}, params)
        frames = asset.path("outputs", "frames")
        record = json.loads(next(asset.path("outputs").glob("*-sheet.json")).read_text(encoding="utf-8"))
        return job, asset, frames, record

    @staticmethod
    def centre(path: Path, want: str):
        """Mean x of the pixels that are clearly blue or clearly green."""
        with Image.open(path) as image:
            pixels = image.convert("RGBA").load()
            xs = []
            for y in range(image.height):
                for x in range(image.width):
                    red, green, blue, alpha = pixels[x, y]
                    if alpha < 200:
                        continue
                    if want == "blue" and blue > red + 60 and blue > green + 60:
                        xs.append(x)
                    if want == "green" and green > red + 60 and green > blue + 60:
                        xs.append(x)
                    if want == "gray" and abs(red - green) < 20 and abs(green - blue) < 20:
                        xs.append(x)
            return (sum(xs) / len(xs), len(xs)) if xs else (None, 0)

    def test_each_facing_looks_the_way_its_name_says(self):
        job, asset, frames, record = self.render(self.still, directions=4, size=96, pitch=20)
        self.assertEqual([d["name"] for d in record["directions"]], ["south", "east", "north", "west"])
        self.assertEqual([a["name"] for a in record["animations"]], ["static"])
        middle = 48
        self.assertEqual(record["pivot"], "origin")
        for facing in ("south", "east", "north", "west"):
            # The body stands on the origin, so it stays put while the model turns.
            body, _ = self.centre(frames / f"static__{facing}__00.png", "gray")
            self.assertAlmostEqual(body, middle, delta=3, msg=facing)
        nose_east, _ = self.centre(frames / "static__east__00.png", "blue")
        nose_west, _ = self.centre(frames / "static__west__00.png", "blue")
        self.assertGreater(nose_east, middle + 8)     # facing east: the nose points to screen right
        self.assertLess(nose_west, middle - 8)
        nose_south, seen_south = self.centre(frames / "static__south__00.png", "blue")
        self.assertAlmostEqual(nose_south, middle, delta=4)  # facing the viewer: the nose is in the middle
        _, seen_north = self.centre(frames / "static__north__00.png", "blue")
        self.assertLess(seen_north, seen_south / 2)    # from behind the body hides most of it
        right_side, _ = self.centre(frames / "static__south__00.png", "green")
        self.assertLess(right_side, middle - 8)        # its right hand is on the viewer's left
        state = {item["id"]: item["status"] for item in asset.manifest["validation"]}
        self.assertEqual(state["SPRITE-EMPTY"], "PASS")
        self.assertEqual(state["SPRITE-CLIP"], "PASS")

    def test_the_anchor_is_the_ground_under_the_model(self):
        _, _, frames, record = self.render(self.still, directions=1, size=96, pitch=0)
        x, y = record["directions"][0]["anchor"]
        self.assertAlmostEqual(x, 48, delta=1.5)
        with Image.open(frames / "static__south__00.png") as image:
            bottom = image.convert("RGBA").getchannel("A").getbbox()[3]
        self.assertAlmostEqual(y, bottom, delta=2)     # side view: the anchor sits on the lowest drawn row

    def test_animations_are_rendered_by_name_and_share_one_scale(self):
        job, _, frames, record = self.render(self.moving, directions=4, frames=4, size=64, animations="spin,bob")
        self.assertEqual([(a["name"], a["frames"]) for a in record["animations"]], [("spin", 4), ("bob", 4)])
        self.assertEqual(len(record["frames"]), 32)
        self.assertEqual((record["width"], record["height"]), (4 * 64, 8 * 64))
        # A quarter turn of the model seen from the south is the still model seen from the east.
        turned, _ = self.centre(frames / "spin__south__01.png", "blue")
        self.assertIsNotNone(turned)
        self.assertNotAlmostEqual(turned, 32, delta=4)
        # The bob lifts the model: its top row moves up, the scale stays.
        with Image.open(frames / "bob__south__00.png") as low, Image.open(frames / "bob__south__02.png") as high:
            low_box = low.convert("RGBA").getchannel("A").getbbox()
            high_box = high.convert("RGBA").getchannel("A").getbbox()
        self.assertLess(high_box[1], low_box[1] - 3)
        self.assertAlmostEqual(high_box[2] - high_box[0], low_box[2] - low_box[0], delta=2)

    def test_a_still_model_puts_its_facings_in_one_row(self):
        _, _, _, record = self.render(self.still, directions=8, size=32, engine="flat")
        self.assertEqual((record["width"], record["height"]), (8 * 32, 32))
        self.assertEqual([f["direction"] for f in record["frames"]],
                         ["south", "south-east", "east", "north-east", "north", "north-west", "west", "south-west"])
        self.assertEqual([f["x"] for f in record["frames"]], [index * 32 for index in range(8)])
        self.assertIn("facings left to right", record["layout"])

    def test_leaving_animations_out_is_said(self):
        job, asset, _, record = self.render(self.moving, directions=1, size=48, animations="none")
        self.assertEqual([a["name"] for a in record["animations"]], ["static"])
        state = {item["id"]: item for item in asset.manifest["validation"]}
        self.assertEqual(state["SPRITE-ANIM"]["status"], "WARNING")
        self.assertIn("bob", state["SPRITE-ANIM"]["detail"])

    def test_an_unknown_animation_fails_with_the_names_the_file_has(self):
        recipe = recipes.get("sprite-render", self.project)
        params = recipes.resolve_params(recipe, {"animations": "dance", "directions": "1"})
        with self.assertRaises(adapters.AdapterError) as caught:
            runner.execute(self.project, recipe, {"mesh": self.moving}, params)
        self.assertIn("bob", str(caught.exception))

    def test_hard_edges_when_antialiasing_is_off(self):
        _, _, frames, _ = self.render(self.still, directions=1, size=48, antialias="false")
        with Image.open(frames / "static__south__00.png") as image:
            levels = {value for value in image.convert("RGBA").getchannel("A").tobytes()}
        self.assertLessEqual(levels, {0, 255})


if __name__ == "__main__":
    unittest.main()
