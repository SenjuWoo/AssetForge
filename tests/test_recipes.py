import json
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

sys.path.insert(0, str(ROOT / "src"))

from assetforge import recipes  # noqa: E402
from assetforge.store import Project  # noqa: E402

try:
    import jsonschema
except ImportError:
    jsonschema = None


class RecipeTests(unittest.TestCase):
    def test_all_builtin_recipes_load(self):
        loaded = recipes.load_all()
        self.assertGreaterEqual(len(loaded), 7)
        for recipe in loaded.values():
            self.assertTrue(recipe["steps"])
            if jsonschema:
                schema = json.loads((ROOT / "schemas" / "recipe.schema.json").read_text(encoding="utf-8"))
                jsonschema.validate(recipe, schema)

    def test_unknown_step_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp) / "demo")
            bad = {
                "schema": 1,
                "id": "bad-recipe",
                "title": "Bad",
                "steps": ["subprocess.exec"],
            }
            (project.root / "recipes" / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(recipes.RecipeError):
                recipes.load_all(project)

    def test_project_recipe_overrides_builtin(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project.init(Path(tmp) / "demo")
            custom = {
                "schema": 1,
                "id": "image-prep",
                "title": "Custom image prep",
                "input": {"name": "image", "kind": "image", "required": True},
                "params": {},
                "steps": ["image.inspect", "asset.record"],
            }
            (project.root / "recipes" / "image-prep.json").write_text(json.dumps(custom), encoding="utf-8")
            self.assertEqual(recipes.get("image-prep", project)["title"], "Custom image prep")

    def test_param_resolution(self):
        recipe = recipes.get("image-prep")
        params = recipes.resolve_params(recipe, {"width": "64", "format": "webp"})
        self.assertEqual(params["width"], 64)
        self.assertEqual(params["format"], "webp")
        with self.assertRaises(recipes.RecipeError):
            recipes.resolve_params(recipe, {"width": "wide"})
        with self.assertRaises(recipes.RecipeError):
            recipes.resolve_params(recipe, {"format": "tiff"})
        with self.assertRaises(recipes.RecipeError):
            recipes.resolve_params(recipe, {"nope": "1"})

    def test_required_param(self):
        recipe = recipes.get("comfy-generate")
        with self.assertRaises(recipes.RecipeError):
            recipes.resolve_params(recipe, {})


if __name__ == "__main__":
    unittest.main()
