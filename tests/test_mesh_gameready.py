"""Budget math always runs. The Blender pass runs only when Blender is installed."""

import json
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from helpers import ROOT, run_cli

sys.path.insert(0, str(ROOT / "src"))

from assetforge import providers  # noqa: E402
from assetforge.gameready import fit_size, reject_over_cap, resolve_budget  # noqa: E402
from assetforge.glb import inspect_glb  # noqa: E402
from assetforge.store import Project  # noqa: E402


class BudgetTests(unittest.TestCase):
    def test_default_game_cap_is_20000(self):
        self.assertEqual(resolve_budget("game", 0, 0), (17000, 1024, 20000))
        self.assertEqual(resolve_budget("hero", 0, 0), (25500, 2048, 30000))
        self.assertEqual(resolve_budget("accessory", 0, 0), (3400, 1024, 4000))

    def test_texture_cannot_exceed_the_budget_ceiling(self):
        self.assertEqual(resolve_budget("game", 0, 4096), (17000, 1024, 20000))
        self.assertEqual(resolve_budget("hero", 0, 1024), (25500, 1024, 30000))

    def test_sculpt_count_and_old_pc_budget_are_rejected(self):
        with self.assertRaises(ValueError):
            resolve_budget("game", 700000, 1024)
        with self.assertRaises(ValueError):
            resolve_budget("hero", 50000, 2048)
        with self.assertRaises(ValueError):
            resolve_budget("pc", 0, 0)

    def test_explicit_tris_under_the_cap_is_the_ask(self):
        self.assertEqual(resolve_budget("game", 400, 128), (400, 128, 20000))

    def test_written_mesh_over_the_cap_is_rejected(self):
        with self.assertRaises(ValueError):
            reject_over_cap(700000, 20000, "game")
        with self.assertRaises(ValueError):
            reject_over_cap(20001, 20000, "game")
        reject_over_cap(20000, 20000, "game")

    def test_recipe_default_is_the_game_cap(self):
        recipe = json.loads((ROOT / "src" / "assetforge" / "data" / "recipes" / "mesh-gameready.json").read_text(encoding="utf-8"))
        self.assertEqual(recipe["params"]["budget"]["default"], "game")
        self.assertEqual(recipe["params"]["budget"]["choices"], ["game", "hero", "accessory"])
        self.assertEqual(recipe["params"]["tris"]["default"], 0)
        self.assertEqual(recipe["params"]["texture"]["default"], 0)

    def test_bad_budget_and_tiny_target_are_rejected(self):
        with self.assertRaises(ValueError):
            resolve_budget("switch", 0, 0)
        with self.assertRaises(ValueError):
            resolve_budget("game", 10, 1024)

    def test_fit_size_snaps_the_long_edge_down(self):
        self.assertEqual(fit_size(4096, 4096, 2048), (2048, 2048))
        self.assertEqual(fit_size(4096, 2048, 2048), (2048, 1024))
        self.assertEqual(fit_size(1024, 1024, 2048), (1024, 1024))


def _png_sizes(data: bytes) -> list[tuple[int, int]]:
    sizes = []
    sig = b"\x89PNG\r\n\x1a\n"
    start = 0
    while True:
        index = data.find(sig, start)
        if index < 0 or index + 24 > len(data):
            break
        sizes.append(struct.unpack(">II", data[index + 16:index + 24]))
        start = index + 8
    return sizes


class BlenderGameReadyTests(unittest.TestCase):
    def test_dense_mesh_and_texture_come_down(self):
        blender = providers.get("blender")
        if not blender.get("available"):
            self.skipTest("Blender is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "dense.glb"
            script = tmp_path / "make_dense.py"
            script.write_text(textwrap.dedent(f"""
                import bpy
                bpy.ops.wm.read_factory_settings(use_empty=True)
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=1)
                obj = bpy.context.active_object
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.uv.smart_project()
                bpy.ops.object.mode_set(mode="OBJECT")
                image = bpy.data.images.new("T_Test", 512, 512)
                image.generated_color = (0.8, 0.2, 0.1, 1)
                image.filepath_raw = r"{(tmp_path / "T_Test.png").as_posix()}"
                image.file_format = "PNG"
                image.save()
                image.pack()
                mat = bpy.data.materials.new("M_Test")
                mat.use_nodes = True
                tree = mat.node_tree
                tex = tree.nodes.new("ShaderNodeTexImage")
                tex.image = image
                tree.links.new(tex.outputs["Color"], tree.nodes["Principled BSDF"].inputs["Base Color"])
                obj.data.materials.append(mat)
                bpy.ops.export_scene.gltf(filepath=r"{source.as_posix()}", export_format="GLB", export_apply=True)
            """).strip(), encoding="utf-8")
            made = subprocess.run(
                [blender["path"], "-b", "--factory-startup", "--python", str(script)],
                capture_output=True, text=True, errors="replace", timeout=180,
            )
            self.assertEqual(made.returncode, 0, made.stderr[-800:] or made.stdout[-800:])
            self.assertTrue(source.is_file())
            before = inspect_glb(source)
            self.assertGreater(before["triangles"], 1000)

            project = Project.init(tmp_path / "project", "Game ready")
            ran = run_cli(
                ["run", "mesh-gameready", "--input", str(source), "--set", "tris=400", "--set", "texture=128", "--json"],
                project.root,
            )
            self.assertEqual(ran.returncode, 0, ran.stdout[-1500:] + ran.stderr[-1500:])
            report = json.loads(ran.stdout)
            self.assertEqual(report["job"]["status"], "SUCCEEDED", report)
            primary = project.root / report["asset"]["primary"]["mesh"]
            after = inspect_glb(primary)
            self.assertLessEqual(after["triangles"], 900)
            self.assertLess(after["triangles"], before["triangles"])
            sizes = _png_sizes(primary.read_bytes())
            self.assertTrue(sizes, "exported GLB has no PNG to prove the texture cap")
            self.assertTrue(all(max(w, h) <= 128 for w, h in sizes), sizes)
