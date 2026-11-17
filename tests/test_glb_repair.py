"""Zero-length normals and tangents in a GLB are rewritten to unit vectors.

Blender writes a (0,0,0,1) tangent for a triangle whose UVs have no area,
which a collapse decimate leaves behind; the official validator rejects it."""

import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT, make_glb

sys.path.insert(0, str(ROOT / "src"))

from assetforge import providers, recipes, runner  # noqa: E402
from assetforge.glb import inspect_glb, repair_unit_vectors, validate_glb  # noqa: E402
from assetforge.store import Project  # noqa: E402

NORMALS = [(0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (0.0, 3.0, 4.0), (1.0, 0.0, 0.0)]
TANGENTS = [(1.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, -1.0), (0.0, 0.0, 2.0, 1.0)]


def tangent_glb(path: Path, stride: int = 0) -> Path:
    """Four vertices, two triangles, NORMAL and TANGENT with bad entries.
    `stride` interleaves the tangents with four padding bytes each."""
    positions = b"".join(struct.pack("<3f", *p) for p in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)))
    normals = b"".join(struct.pack("<3f", *n) for n in NORMALS)
    tangents = b"".join(struct.pack("<4f", *t) + (b"\xAA" * (stride - 16) if stride else b"") for t in TANGENTS)
    indices = struct.pack("<6H", 0, 1, 2, 1, 3, 2)
    parts = [positions, normals, tangents, indices]
    offsets, cursor = [], 0
    for part in parts:
        offsets.append(cursor)
        cursor += len(part)
    binary = b"".join(parts)
    binary += b"\x00" * (-len(binary) % 4)
    tangent_view = {"buffer": 0, "byteOffset": offsets[2], "byteLength": len(tangents), "target": 34962}
    if stride:
        tangent_view["byteStride"] = stride
    doc = {
        "asset": {"version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TANGENT": 2}, "indices": 3, "mode": 4}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 4, "type": "VEC3", "min": [0, 0, 0], "max": [1, 1, 0]},
            {"bufferView": 1, "componentType": 5126, "count": 4, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": 4, "type": "VEC4"},
            {"bufferView": 3, "componentType": 5123, "count": 6, "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": offsets[0], "byteLength": len(positions), "target": 34962},
            {"buffer": 0, "byteOffset": offsets[1], "byteLength": len(normals), "target": 34962},
            tangent_view,
            {"buffer": 0, "byteOffset": offsets[3], "byteLength": len(indices), "target": 34963},
        ],
        "buffers": [{"byteLength": len(binary)}],
    }
    text = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    text += b" " * (-len(text) % 4)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(text) + 8 + len(binary)))
        fh.write(struct.pack("<II", len(text), 0x4E4F534A) + text)
        fh.write(struct.pack("<II", len(binary), 0x004E4942) + binary)
    return path


def vectors(path: Path, accessor: int, width: int, stride: int = 0):
    data = path.read_bytes()
    json_length = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + json_length])
    base = 20 + json_length + 8
    view = doc["bufferViews"][doc["accessors"][accessor]["bufferView"]]
    step = stride or 4 * width
    return [struct.unpack_from(f"<{width}f", data, base + view["byteOffset"] + index * step)
            for index in range(doc["accessors"][accessor]["count"])]


def length(vector) -> float:
    return math.sqrt(sum(value * value for value in vector[:3]))


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_zero_and_stretched_vectors_become_unit_and_good_ones_are_untouched(self):
        path = tangent_glb(self.dir / "t.glb")
        fixed = repair_unit_vectors(path)
        self.assertEqual(fixed, {"normals": 2, "tangents": 3})
        normals, tangents = vectors(path, 1, 3), vectors(path, 2, 4)
        for vector in normals + tangents:
            self.assertAlmostEqual(length(vector), 1.0, places=5)
        self.assertEqual(normals[0], NORMALS[0])
        self.assertEqual(normals[3], NORMALS[3])
        self.assertEqual(tangents[0], TANGENTS[0])
        self.assertEqual(normals[2], (0.0, 0.6000000238418579, 0.800000011920929))   # (0,3,4) scaled, direction kept
        self.assertEqual(tangents[3][:3], (0.0, 0.0, 1.0))
        self.assertEqual([t[3] for t in tangents], [1.0, 1.0, -1.0, 1.0])            # handedness is kept

    def test_a_rebuilt_tangent_lies_across_its_normal(self):
        path = tangent_glb(self.dir / "t.glb")
        repair_unit_vectors(path)
        normals, tangents = vectors(path, 1, 3), vectors(path, 2, 4)
        for index in (1, 2):
            dot = sum(a * b for a, b in zip(normals[index], tangents[index][:3]))
            self.assertAlmostEqual(dot, 0.0, places=5)

    def test_interleaved_data_is_read_by_its_stride(self):
        path = tangent_glb(self.dir / "t.glb", stride=20)
        self.assertEqual(repair_unit_vectors(path)["tangents"], 3)
        for vector in vectors(path, 2, 4, stride=20):
            self.assertAlmostEqual(length(vector), 1.0, places=5)
        data = path.read_bytes()
        self.assertEqual(data.count(b"\xAA\xAA\xAA\xAA"), 4)   # the bytes between the tangents are not touched

    def test_a_clean_file_is_not_rewritten(self):
        path = make_glb(self.dir / "clean.glb")
        before = path.read_bytes()
        stamp = path.stat().st_mtime_ns
        self.assertEqual(repair_unit_vectors(path), {"normals": 0, "tangents": 0})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(path.stat().st_mtime_ns, stamp)

    def test_the_file_is_still_a_valid_glb_of_the_same_size(self):
        path = tangent_glb(self.dir / "t.glb")
        size = path.stat().st_size
        repair_unit_vectors(path)
        self.assertEqual(path.stat().st_size, size)
        self.assertEqual(inspect_glb(path)["triangles"], 2)
        self.assertNotEqual(validate_glb(path)["status"], "FAIL")


class GamereadyRepairTests(unittest.TestCase):
    def test_mesh_gameready_repairs_what_blender_wrote_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp) / "project", "Repair")
            source = make_glb(Path(tmp) / "axe.glb")
            recipe = recipes.get("mesh-gameready", project)
            blender = {"id": "blender", "available": True, "version": "9.9", "path": "blender"}
            real_get = providers.get

            def collapse(provider, mesh, target, tris, texture, timeout=900):
                tangent_glb(target)
                return {"report": {"textures": []}}

            with mock.patch("assetforge.runner.providers.get", side_effect=lambda pid, project=None: blender if pid == "blender" else real_get(pid, project)), \
                 mock.patch("assetforge.adapters.blender_gameready", side_effect=collapse):
                job, asset, _ = runner.execute(project, recipe, {"mesh": source}, recipes.resolve_params(recipe, {}))
            step = next(item for item in job.data["steps"] if item["name"] == "blender.gameready")
            self.assertIn("3 tangent(s) and 2 normal(s)", step["detail"])
            written = next(project.root.rglob("axe-gameready.glb"))
            for vector in vectors(written, 2, 4):
                self.assertAlmostEqual(length(vector), 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
