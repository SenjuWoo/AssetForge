"""Rig, material and embedded-texture validation, the source probe, mesh
conversion and the cmd.exe shim. Every fixture is built here from bytes."""

import copy
import json
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from helpers import ROOT, make_glb, make_png, make_textured_glb, run_cli

sys.path.insert(0, str(ROOT / "src"))

from assetforge import exporters, providers, util  # noqa: E402
from assetforge.glb import image_size, inspect_glb, validate_glb  # noqa: E402
from assetforge.probe import probe  # noqa: E402
from assetforge.store import Project  # noqa: E402

AWKWARD = "!rig (x) é"


def write_glb(path: Path, doc: dict, binary: bytes) -> Path:
    while len(binary) % 4:
        binary += b"\x00"
    doc = dict(doc, buffers=[{"byteLength": len(binary)}])
    text = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    while len(text) % 4:
        text += b" "
    with open(path, "wb") as handle:
        handle.write(struct.pack("<III", 0x46546C67, 2, 28 + len(text) + len(binary)))
        handle.write(struct.pack("<II", len(text), 0x4E4F534A) + text)
        handle.write(struct.pack("<II", len(binary), 0x004E4942) + binary)
    return path


def png_bytes(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    rows = b"".join(b"\x00" + b"\x80\x80\x80" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def skinned_doc():
    """One triangle bound to a two-joint skin with a one-channel animation."""
    identity = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    parts = [
        struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0),            # 0 POSITION
        struct.pack("<3H", 0, 1, 2) + b"\x00\x00",                # 1 indices
        struct.pack("<12B", 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0),  # 2 JOINTS_0
        struct.pack("<12f", 1, 0, 0, 0, .5, .5, 0, 0, 1, 0, 0, 0),  # 3 WEIGHTS_0
        struct.pack("<32f", *identity, *identity),                # 4 inverse bind
        struct.pack("<2f", 0.0, 1.0),                             # 5 times
        struct.pack("<8f", 0, 0, 0, 1, 0, 0, 0.7071, 0.7071),     # 6 rotations
    ]
    views, offset = [], 0
    for part in parts:
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(part)})
        offset += len(part)
    doc = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0, 1]}],
        "nodes": [
            {"mesh": 0, "skin": 0, "name": "Body"},
            {"name": "Root", "children": [2]},
            {"name": "Tip", "translation": [0, 1, 0]},
        ],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "JOINTS_0": 2, "WEIGHTS_0": 3}, "indices": 1}]}],
        "skins": [{"joints": [1, 2], "inverseBindMatrices": 4}],
        "animations": [{
            "name": "Bend",
            "samplers": [{"input": 5, "output": 6, "interpolation": "LINEAR"}],
            "channels": [{"sampler": 0, "target": {"node": 2, "path": "rotation"}}],
        }],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [0, 0, 0], "max": [1, 1, 0]},
            {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
            {"bufferView": 2, "componentType": 5121, "count": 3, "type": "VEC4"},
            {"bufferView": 3, "componentType": 5126, "count": 3, "type": "VEC4"},
            {"bufferView": 4, "componentType": 5126, "count": 2, "type": "MAT4"},
            {"bufferView": 5, "componentType": 5126, "count": 2, "type": "SCALAR", "min": [0.0], "max": [1.0]},
            {"bufferView": 6, "componentType": 5126, "count": 2, "type": "VEC4"},
        ],
        "bufferViews": views,
    }
    return doc, b"".join(parts)


def check(report: dict, check_id: str) -> dict:
    return next(item for item in report["checks"] if item["id"] == check_id)


class Folder(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name).resolve() / AWKWARD
        self.dir.mkdir()

    def tearDown(self):
        self.temp.cleanup()


class RigValidation(Folder):
    def build(self, mutate=None, binary_patch=None):
        doc, binary = skinned_doc()
        if mutate:
            mutate(doc)
        if binary_patch:
            binary = binary_patch(doc, binary)
        return validate_glb(write_glb(self.dir / "rig.glb", doc, binary))

    def test_consistent_rig_passes_and_reports_its_shape(self):
        report = self.build()
        rig = check(report, "GLB-013")
        self.assertEqual(rig["status"], "PASS", rig)
        self.assertIn("up to 2 joints", rig["detail"])
        self.assertEqual(report["stats"]["rig"]["animation_names"], ["Bend"])
        self.assertEqual(report["stats"]["rig"]["animation_seconds"], 1.0)

    def test_unrigged_file_is_not_tested_rather_than_passed(self):
        report = validate_glb(make_glb(self.dir / "plain.glb"))
        self.assertEqual(check(report, "GLB-013")["status"], "NOT_TESTED")

    def test_too_few_inverse_bind_matrices_fail(self):
        report = self.build(lambda doc: doc["accessors"][4].update(count=1))
        self.assertEqual(check(report, "GLB-013")["status"], "FAIL")
        self.assertIn("inverse bind", check(report, "GLB-013")["detail"])

    def test_skinned_mesh_without_weights_fails(self):
        report = self.build(lambda doc: doc["meshes"][0]["primitives"][0]["attributes"].pop("WEIGHTS_0"))
        self.assertEqual(check(report, "GLB-013")["status"], "FAIL")

    def test_joint_index_past_the_skin_fails(self):
        def patch(doc, binary):
            start = doc["bufferViews"][2]["byteOffset"]
            return binary[:start] + bytes([7]) + binary[start + 1:]

        report = self.build(binary_patch=patch)
        self.assertEqual(check(report, "GLB-013")["status"], "FAIL")
        self.assertIn("past the skin", check(report, "GLB-013")["detail"])

    def test_weights_that_do_not_sum_to_one_warn(self):
        def patch(doc, binary):
            start = doc["bufferViews"][3]["byteOffset"]
            return binary[:start] + struct.pack("<f", 0.25) + binary[start + 4:]

        rig = check(self.build(binary_patch=patch), "GLB-013")
        self.assertEqual(rig["status"], "WARNING")
        self.assertIn("do not sum to 1", rig["detail"])

    def test_animation_with_mismatched_key_counts_fails(self):
        report = self.build(lambda doc: doc["accessors"][6].update(count=1))
        self.assertEqual(check(report, "GLB-013")["status"], "FAIL")

    def test_animation_targeting_a_missing_node_fails(self):
        report = self.build(lambda doc: doc["animations"][0]["channels"][0]["target"].update(node=40))
        self.assertEqual(check(report, "GLB-013")["status"], "FAIL")


class MaterialAndTransformValidation(Folder):
    def textured(self, mutate):
        path = make_textured_glb(self.dir / "textured.glb")
        raw = path.read_bytes()
        json_length = struct.unpack_from("<I", raw, 12)[0]
        doc = json.loads(raw[20:20 + json_length])
        binary = raw[28 + json_length:]
        mutate(doc)
        return validate_glb(write_glb(path, doc, binary))

    def test_resolving_materials_pass(self):
        report = validate_glb(make_textured_glb(self.dir / "ok.glb"))
        self.assertEqual(check(report, "GLB-015")["status"], "PASS")
        self.assertEqual(check(report, "GLB-016")["status"], "PASS")

    def test_material_naming_a_missing_texture_fails(self):
        report = self.textured(lambda doc: doc["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"].update(index=9))
        self.assertEqual(check(report, "GLB-015")["status"], "FAIL")

    def test_primitive_naming_a_missing_material_fails(self):
        report = self.textured(lambda doc: doc["meshes"][1]["primitives"][0].update(material=5))
        self.assertEqual(check(report, "GLB-015")["status"], "FAIL")

    def test_textured_surface_without_uvs_warns(self):
        report = self.textured(lambda doc: doc["meshes"][0]["primitives"][0]["attributes"].pop("TEXCOORD_0"))
        self.assertEqual(check(report, "GLB-015")["status"], "WARNING")

    def test_mirrored_and_collapsed_nodes_warn(self):
        report = self.textured(lambda doc: (doc["nodes"][0].update(scale=[-1, 1, 1]), doc["nodes"][1].update(scale=[1, 0, 1])))
        detail = check(report, "GLB-016")
        self.assertEqual(detail["status"], "WARNING")
        self.assertIn("mirrored", detail["detail"])
        self.assertIn("zero", detail["detail"])


class EmbeddedTextures(Folder):
    def with_texture(self, size: int) -> Path:
        path = make_textured_glb(self.dir / "base.glb")
        raw = path.read_bytes()
        json_length = struct.unpack_from("<I", raw, 12)[0]
        doc = json.loads(raw[20:20 + json_length])
        binary = raw[28 + json_length:]
        view = doc["bufferViews"][doc["images"][0]["bufferView"]]
        png = png_bytes(size, size)
        binary = binary[:view["byteOffset"]] + png
        view["byteLength"] = len(png)
        return write_glb(self.dir / f"tex{size}.glb", doc, binary)

    def test_header_sizes_for_the_gltf_image_formats(self):
        self.assertEqual(image_size(png_bytes(640, 480)), (640, 480, "png"))
        jpeg = b"\xff\xd8\xff\xe0\x00\x10" + b"J" * 14 + b"\xff\xc0\x00\x11\x08" + struct.pack(">HH", 300, 200) + b"\x03" * 12
        self.assertEqual(image_size(jpeg), (200, 300, "jpeg"))
        webp = b"RIFF" + b"\x00" * 4 + b"WEBPVP8X" + b"\x00" * 8 + (1023).to_bytes(3, "little") + (511).to_bytes(3, "little")
        self.assertEqual(image_size(webp), (1024, 512, "webp"))
        self.assertIsNone(image_size(b"not an image"))
        self.assertIsNone(image_size(b"\x89PNG\r\n\x1a\n"))

    def test_inspect_reports_the_embedded_size(self):
        stats = inspect_glb(self.with_texture(2048))
        self.assertEqual(stats["max_texture_size"], 2048)
        self.assertEqual(stats["image_details"][0]["source"], "embedded")

    def test_export_budget_measures_embedded_textures(self):
        project = Project.init(self.dir / "proj", "Tex")
        outcomes = {}
        for size in (512, 2048):
            proc = run_cli(["run", "glb-inspect", "--input", str(self.with_texture(size)), "--json"], project.root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            asset = project.asset(json.loads(proc.stdout)["asset"]["id"])
            plan = exporters.export(project, asset, "roblox", dry_run=True)
            outcomes[size] = next(item for item in plan["checks"] if item["id"] == "BUDGET-TEXTURE_SIZE")
        self.assertEqual(outcomes[512]["status"], "PASS", outcomes[512])
        self.assertEqual(outcomes[2048]["status"], "FAIL", outcomes[2048])
        self.assertIn("2048x2048", outcomes[2048]["detail"])


class Probe(Folder):
    def test_glb_over_budget_routes_to_gameready(self):
        doc, binary = skinned_doc()
        doc["accessors"][1]["count"] = 3
        path = write_glb(self.dir / "small.glb", doc, binary)
        report = probe(path)
        self.assertEqual(report["kind"], "glb")
        self.assertEqual(report["facts"]["skins"], 1)
        self.assertEqual(report["recommend"][0]["recipe"], "glb-optimize")
        self.assertIn(str(path), report["recommend"][0]["command"])

    def test_non_glb_mesh_routes_to_convert(self):
        source = self.dir / "model.fbx"
        source.write_bytes(b"Kaydara FBX Binary  \x00")
        report = probe(source)
        self.assertEqual(report["kind"], "mesh")
        self.assertEqual(report["recommend"][0]["recipe"], "mesh-convert")

    def test_folder_with_a_pbr_set_routes_to_texture_pack(self):
        for name in ("wall_ao.png", "wall_roughness.png", "wall_metallic.png"):
            make_png(self.dir / name)
        report = probe(self.dir)
        self.assertEqual(report["facts"]["by_kind"], {"image": 3})
        recipes = [item["recipe"] for item in report["recommend"]]
        self.assertEqual(recipes, ["texture-pack"])
        self.assertIn("occlusion=", report["recommend"][0]["command"])

    def test_cli_needs_no_project_and_fails_on_a_broken_file(self):
        good = run_cli(["probe", str(make_glb(self.dir / "ok.glb")), "--json"], self.dir)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)["facts"]["validation"], "PASS")
        broken = self.dir / "broken.glb"
        broken.write_bytes(b"glTF\x02\x00\x00\x00")
        self.assertEqual(run_cli(["probe", str(broken)], self.dir).returncode, 5)
        self.assertEqual(run_cli(["probe", str(self.dir / "absent.glb")], self.dir).returncode, 3)


@unittest.skipUnless(os.name == "nt", "cmd.exe shim")
class CommandShim(Folder):
    def test_cmd_script_and_arguments_survive_an_awkward_folder(self):
        script = self.dir / "echo args.cmd"
        # The script proves each argument by using it: the first must name a real
        # file, the second must be the two words. Echoing the path back would test
        # the console code page instead of the command line.
        script.write_bytes(b'@echo off\r\nif not exist "%~1" exit /b 3\r\nif not "%~2"=="a b" exit /b 4\r\nexit /b 7\r\n')
        target = self.dir / "in (1).glb"
        target.write_bytes(b"x")
        result = util.run([str(script), str(target), "a b"], timeout=60)
        self.assertEqual(result["returncode"], 7, result)
        missing = util.run([str(script), str(self.dir / "absent.glb"), "a b"], timeout=60)
        self.assertEqual(missing["returncode"], 3, missing)


def _blender():
    item = providers.get("blender")
    return item if item.get("available") else None


@unittest.skipUnless(_blender(), "Blender is not installed")
class MeshConvert(Folder):
    OBJ = "o Tri\nv 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\nvn 0 0 1\nf 1/1/1 2/2/1 3/3/1\n"

    def test_obj_becomes_a_validated_glb_named_after_its_source(self):
        source = self.dir / "crate (v2).obj"
        source.write_text(self.OBJ, encoding="ascii")
        project = Project.init(self.dir / "proj", "Convert")
        proc = run_cli(["run", "mesh-convert", "--input", str(source), "--json"], project.root)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertTrue(report["asset"]["id"].startswith("crate-v2-mesh-convert"), report["asset"]["id"])
        primary = project.root / report["asset"]["primary"]["mesh"]
        stats = inspect_glb(primary)
        self.assertEqual(stats["triangles"], 1)
        self.assertEqual(validate_glb(primary)["summary"]["FAIL"], 0)

    def test_unreadable_source_fails_with_the_importer_message(self):
        source = self.dir / "empty.stl"
        source.write_bytes(b"")
        project = Project.init(self.dir / "proj", "Convert")
        proc = run_cli(["run", "mesh-convert", "--input", str(source)], project.root)
        self.assertEqual(proc.returncode, 6, proc.stdout + proc.stderr)
        job = json.loads(run_cli(["status", "--last", "--json"], project.root).stdout)
        self.assertEqual(job["status"], "FAILED")

    def test_unsupported_extension_is_refused_before_blender_starts(self):
        source = self.dir / "notes.txt"
        source.write_text("x", encoding="ascii")
        project = Project.init(self.dir / "proj", "Convert")
        proc = run_cli(["run", "mesh-convert", "--input", str(source)], project.root)
        self.assertEqual(proc.returncode, 6)
        self.assertIn("not a convertible mesh format", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
