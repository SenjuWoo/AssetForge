import json
import struct
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, make_glb, make_textured_glb

import sys

sys.path.insert(0, str(ROOT / "src"))

from assetforge.glb import compare_glb, inspect_glb, validate_glb  # noqa: E402


class GlbTests(unittest.TestCase):
    def test_inspect_valid_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_glb(Path(tmp) / "triangle.glb")
            stats = inspect_glb(path)
            self.assertEqual(stats["triangles"], 1)
            self.assertEqual(stats["vertices"], 3)
            self.assertEqual(stats["materials"], 1)
            self.assertEqual(stats["missing_normals"], 0)

    def test_validate_valid_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = validate_glb(make_glb(Path(tmp) / "triangle.glb"))
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["summary"]["FAIL"], 0)
            checks = {item["id"]: item for item in report["checks"]}
            self.assertEqual(checks["GLB-009"]["status"], "PASS")
            self.assertEqual(checks["GLB-008"]["status"], "PASS")

    def test_degenerate_triangles_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = validate_glb(make_glb(Path(tmp) / "degenerate.glb", degenerate=True))
            checks = {item["id"]: item for item in report["checks"]}
            self.assertEqual(checks["GLB-008"]["status"], "WARNING")

    def test_missing_normals_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = validate_glb(make_glb(Path(tmp) / "no-normals.glb", normals=False))
            checks = {item["id"]: item for item in report["checks"]}
            self.assertEqual(checks["GLB-009"]["status"], "WARNING")

    def test_bad_magic_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_glb(Path(tmp) / "bad.glb")
            data = bytearray(path.read_bytes())
            struct.pack_into("<I", data, 0, 0x12345678)
            path.write_bytes(bytes(data))
            report = validate_glb(path)
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(report["checks"][0]["id"], "GLB-001")

    def test_truncated_length_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_glb(Path(tmp) / "short.glb")
            data = bytearray(path.read_bytes())
            declared = struct.unpack_from("<I", data, 8)[0]
            struct.pack_into("<I", data, 8, declared + 4)
            path.write_bytes(bytes(data))
            report = validate_glb(path)
            checks = {item["id"]: item for item in report["checks"]}
            self.assertEqual(checks["GLB-002"]["status"], "FAIL")

    def test_compare(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = make_glb(Path(tmp) / "a.glb")
            second = make_glb(Path(tmp) / "b.glb")
            report = compare_glb(first, second)
            self.assertEqual(report["delta"]["triangles"], 0)
            self.assertIn("bytes", report["delta"])

    def test_stats_json_serializable(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = inspect_glb(make_glb(Path(tmp) / "x.glb"))
            json.dumps(stats)

    def test_textured_multi_node_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_textured_glb(Path(tmp) / "textured.glb")
            stats = inspect_glb(path)
            self.assertEqual(stats["nodes"], 2)
            self.assertEqual(stats["meshes"], 2)
            self.assertEqual(stats["materials"], 2)
            self.assertEqual(stats["textures"], 1)
            self.assertEqual(stats["images"], 1)
            self.assertEqual(stats["triangles"], 2)
            report = validate_glb(path)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["summary"]["FAIL"], 0)


if __name__ == "__main__":
    unittest.main()
