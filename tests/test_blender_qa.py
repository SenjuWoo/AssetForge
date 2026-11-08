import sys
import unittest
from pathlib import Path

from helpers import ROOT

sys.path.insert(0, str(ROOT / "src"))

from assetforge import runner  # noqa: E402


class BlenderQaGateTests(unittest.TestCase):
    def data(self, **overrides):
        base = {
            "pass": True,
            "errors": [],
            "warnings": [],
            "ground_z": 0.0,
            "objects": {"SM_Crate": {"tris": 108}},
        }
        base.update(overrides)
        return base

    def test_clean_qa_passes(self):
        passed, detail = runner._blender_qa_gate(self.data(), "")
        self.assertTrue(passed)
        self.assertIn("108 tris", detail)
        self.assertIn("0 warning(s)", detail)

    def test_unacknowledged_warning_fails(self):
        passed, detail = runner._blender_qa_gate(self.data(warnings=["floating part"]), "")
        self.assertFalse(passed)
        self.assertIn("warning_note", detail)

    def test_acknowledged_warning_passes_and_is_preserved(self):
        passed, detail = runner._blender_qa_gate(
            self.data(warnings=["floating part"]), "accepted: decorative handle"
        )
        self.assertTrue(passed)
        self.assertIn("1 warning(s)", detail)

    def test_error_never_passes(self):
        passed, _ = runner._blender_qa_gate(self.data(errors=["bad normals"]), "accepted")
        self.assertFalse(passed)

    def test_pass_false_without_details_never_passes(self):
        passed, detail = runner._blender_qa_gate(
            {"pass": False, "errors": [], "warnings": [], "objects": {}}, ""
        )
        self.assertFalse(passed)
        self.assertIn("0 error(s)", detail)

    def test_visual_review_is_pending_by_default(self):
        status, detail = runner._blender_visual_review("pending", "")
        self.assertEqual(status, "NOT_TESTED")
        self.assertIn("pending", detail)

    def test_visual_approval_requires_a_note(self):
        with self.assertRaises(runner.RunFailed):
            runner._blender_visual_review("approved", "")
        status, detail = runner._blender_visual_review("approved", "inspected both sheets")
        self.assertEqual(status, "PASS")
        self.assertIn("inspected both sheets", detail)
        with self.assertRaises(runner.RunFailed):
            runner._blender_visual_review("maybe", "")


if __name__ == "__main__":
    unittest.main()
