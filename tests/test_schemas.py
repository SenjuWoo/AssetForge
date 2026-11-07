import json
import sys
import unittest
from pathlib import Path

from helpers import ROOT

sys.path.insert(0, str(ROOT / "src"))

try:
    import jsonschema
except ImportError:
    jsonschema = None


class SchemaTests(unittest.TestCase):
    def test_all_json_files_parse(self):
        paths = []
        for folder in (ROOT / "schemas", ROOT / "src" / "assetforge" / "data", ROOT / "integration"):
            if folder.exists():
                paths.extend(sorted(folder.glob("**/*.json")))
        for path in paths:
            with self.subTest(path=path):
                json.loads(path.read_text(encoding="utf-8-sig"))

    @unittest.skipUnless(jsonschema, "jsonschema is required")
    def test_schemas_are_valid(self):
        for path in sorted((ROOT / "schemas").glob("*.json")):
            with self.subTest(path=path):
                schema = json.loads(path.read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator.check_schema(schema)

    def test_version_file_matches_package(self):
        import re

        from assetforge import __version__

        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), __version__)
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertEqual(re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1), __version__)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(re.search(r"^## ([0-9]+\.[0-9]+\.[0-9]+)", changelog, re.M).group(1), __version__)

    def test_public_files_have_no_machine_paths(self):
        forbidden = [str(Path.home()).replace("\\", "/"), "C:/Users/", "Z:/Backup/"]
        for name in (
            "README.md", "ROADMAP.md", "RELEASE.md", "RELEASE-NOTES.md",
            "docs/ARCHITECTURE.md", "docs/PROVIDERS.md", "docs/RECIPES.md",
            "docs/THIRD-PARTY-NOTICES.md", "docs/UPSTREAM-EVALUATIONS.md",
            "docs/UABS-INTEGRATION.md",
        ):
            path = ROOT / name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for item in forbidden:
                with self.subTest(file=name, needle=item):
                    self.assertNotIn(item, text)


if __name__ == "__main__":
    unittest.main()
