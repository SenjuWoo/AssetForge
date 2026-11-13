import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT

sys.path.insert(0, str(ROOT / "src"))

from assetforge import blenderskills, cli, providers  # noqa: E402
from assetforge.store import Project  # noqa: E402


def make_skills(tmp: Path) -> Path:
    root = tmp / "blender-skills"
    skills = root / "skills"
    for name, version in (("blender-core", "1.2.0"), ("blender-asset-qa", "1.2.0"), ("blender-pbr-materials", "1.2.0")):
        folder = skills / name
        (folder / "scripts").mkdir(parents=True)
        (folder / "SKILL.md").write_text(
            "---\n"
            f"name: {name}\n"
            f"description: Test skill {name}\n"
            "license: MIT\n"
            "metadata:\n"
            f"  version: {version}\n"
            "---\n\n# Test\n",
            encoding="utf-8",
        )
        (folder / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    return root


class BlenderSkillsTests(unittest.TestCase):
    def test_catalog_accepts_checkout_and_installed_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_skills(Path(tmp))
            for candidate in (root, root / "skills"):
                with mock.patch.dict(os.environ, {"BLENDER_SKILLS_ROOT": str(candidate)}):
                    found, reason = blenderskills.locate()
                self.assertEqual(reason, "")
                self.assertEqual(found[1], (root / "skills").resolve())
                items = blenderskills.catalog(found[1])
                self.assertEqual(len(items), 3)
                self.assertEqual(items[0]["name"], "blender-asset-qa")
                self.assertEqual(items[0]["version"], "1.2.0")
                self.assertTrue(items[0]["skill_md"].endswith("SKILL.md"))

    def test_project_relative_integration_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_skills(Path(tmp))
            project = Project.init(Path(tmp) / "project", "Relative")
            project.data["integrations"] = {"blender_skills": "../blender-skills"}
            project.save()
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("BLENDER_SKILLS_ROOT", None)
                found, reason = blenderskills.locate(project)
            self.assertEqual(reason, "")
            self.assertEqual(found[1], (root / "skills").resolve())

    def test_a_checkout_in_a_declared_tool_root_is_found(self):
        # A plain clone beside other tools must be found without a variable,
        # the same way comfy-kit and img2threejs are.
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp) / "tools"
            tools.mkdir()
            root = make_skills(tools)
            home = Path(tmp) / "home"
            home.mkdir()
            env = {"ASSETFORGE_ROOTS": str(tools)}
            with mock.patch.dict(os.environ, env), mock.patch.object(Path, "home", return_value=home):
                os.environ.pop("BLENDER_SKILLS_ROOT", None)
                found, reason = blenderskills.locate()
            self.assertEqual(reason, "")
            self.assertEqual(found[1], (root / "skills").resolve())

    def test_release_version_comes_from_the_plugin_manifest(self):
        # Upstream 1.3.0 bumped .claude-plugin/plugin.json but left the
        # per-skill metadata at 1.2.0; the release is what we tested.
        with tempfile.TemporaryDirectory() as tmp:
            root = make_skills(Path(tmp))
            (root / ".claude-plugin").mkdir()
            (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "x", "version": "1.3.0"}), encoding="utf-8")
            with mock.patch.dict(os.environ, {"BLENDER_SKILLS_ROOT": str(root)}):
                provider = providers.get("blender-skills")
            self.assertEqual(provider["version"], "1.3.0")
            self.assertEqual(provider["details"]["skill_version"], "1.2.0")

    def test_route_materials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_skills(Path(tmp))
            with mock.patch.dict(os.environ, {"BLENDER_SKILLS_ROOT": str(root)}):
                provider = providers.get("blender-skills")
            self.assertTrue(provider["available"])
            self.assertEqual(provider["details"]["skills"], 3)
            items = blenderskills.catalog(Path(provider["details"]["skills_dir"]))
            names = [item["name"] for item in blenderskills.route("materials", items)]
            self.assertEqual(names, ["blender-pbr-materials"])

    def test_invalid_explicit_root_is_reported(self):
        with mock.patch.dict(os.environ, {"BLENDER_SKILLS_ROOT": os.path.join(tempfile.gettempdir(), "missing-blender-skills")}):
            provider = providers.get("blender-skills")
        self.assertFalse(provider["available"])
        self.assertIn("BLENDER_SKILLS_ROOT", provider["reason"])

    def test_cli_lists_and_routes_with_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_skills(Path(tmp))
            with mock.patch.dict(os.environ, {"BLENDER_SKILLS_ROOT": str(root)}):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = cli.main(["blender-skills", "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertTrue(payload["provider"]["available"])
            self.assertEqual(len(payload["skills"]), 3)
            self.assertIn("materials", payload["routes"])

    def test_cli_absent_returns_provider_exit(self):
        with mock.patch.dict(os.environ, {"BLENDER_SKILLS_ROOT": os.path.join(tempfile.gettempdir(), "missing-blender-skills")}):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = cli.main(["blender-skills", "--json"])
        self.assertEqual(code, 4)
        payload = json.loads(output.getvalue())
        self.assertFalse(payload["provider"]["available"])
        self.assertEqual(payload["skills"], [])


if __name__ == "__main__":
    unittest.main()
