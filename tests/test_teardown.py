"""teardown provider: offline simulator pages and their films.

The stub provider stands in for the upstream checkout so the contract is tested
everywhere; the real-provider tests run only where teardown, its npm
dependencies, Chromium and FFmpeg are installed.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT, run_cli

sys.path.insert(0, str(ROOT / "src"))

from assetforge import cli, providers  # noqa: E402
from assetforge.store import Project  # noqa: E402

NODE = shutil.which("node")

# Writes <TEARDOWN_OUT>/dist/<name>.html the way upstream build.mjs does.
STUB_BUILD = r"""
import fs from 'node:fs';
import path from 'node:path';
const dir = path.resolve(process.argv[2]);
if (!fs.existsSync(path.join(dir, 'main.js'))) { console.error(`no main.js in ${dir}`); process.exit(1); }
const name = path.basename(dir);
const out = path.join(process.env.TEARDOWN_OUT || 'teardown-out', 'dist');
fs.mkdirSync(out, {recursive: true});
const js = fs.readFileSync(path.join(dir, 'main.js'), 'utf8');
fs.writeFileSync(path.join(out, `${name}.html`), `<!doctype html><title>${name}</title><script type="module">${js}</script>` + ' '.repeat(2048));
console.log(`${name}.html built`);
"""


def make_teardown(tmp: Path, deps: bool = True) -> Path:
    root = tmp / "teardown"
    (root / "sims").mkdir(parents=True)
    (root / "SKILL.md").write_text("---\nname: teardown\n---\n# teardown\n", encoding="utf-8")
    (root / "paths.mjs").write_text("export const OUT = 'teardown-out';\n", encoding="utf-8")
    (root / "sims" / "build.mjs").write_text(STUB_BUILD, encoding="utf-8")
    (root / "package.json").write_text(json.dumps({"name": "teardown", "version": "1.0.0"}), encoding="utf-8")
    if deps:
        for package in ("esbuild", "three"):
            folder = root / "node_modules" / package
            folder.mkdir(parents=True)
            (folder / "package.json").write_text(json.dumps({"name": package, "version": "0.0.1"}), encoding="utf-8")
    return root


def make_sim(tmp: Path, name: str = "pump-live") -> Path:
    sim = tmp / "sims in a folder!" / name
    (sim / "parts").mkdir(parents=True)
    (sim / "main.js").write_text("import './parts/rotor.js';\nconsole.log('pump');\n", encoding="utf-8")
    (sim / "parts" / "rotor.js").write_text("export const rotor = 1;\n", encoding="utf-8")
    return sim


class TeardownProvider(unittest.TestCase):
    def test_checkout_with_dependencies_is_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_teardown(Path(tmp))
            with mock.patch.dict(os.environ, {"TEARDOWN_ROOT": str(root)}):
                item = providers.get("teardown")
            self.assertEqual(item["available"], NODE is not None, item["reason"])
            self.assertEqual(item["version"], "1.0.0")
            self.assertTrue(item["use"])
            self.assertIn("presentation.page", item["capabilities"])

    def test_checkout_without_npm_install_says_what_to_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_teardown(Path(tmp), deps=False)
            with mock.patch.dict(os.environ, {"TEARDOWN_ROOT": str(root)}):
                item = providers.get("teardown")
            self.assertFalse(item["available"])
            self.assertIn("npm install", item["reason"])

    def test_wrong_variable_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"TEARDOWN_ROOT": str(Path(tmp) / "nope")}):
                item = providers.get("teardown")
            self.assertFalse(item["available"])
            self.assertIn("TEARDOWN_ROOT", item["reason"])

    def test_capabilities_list_the_recipes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_teardown(Path(tmp))
            with mock.patch.dict(os.environ, {"TEARDOWN_ROOT": str(root)}):
                payload = cli.capabilities_payload()
        ids = {item["id"]: item for item in payload["capabilities"]}
        self.assertEqual(ids["teardown-build"]["status"], "IMPLEMENTED")
        self.assertEqual(ids["teardown-film"]["status"], "IMPLEMENTED")
        self.assertNotIn("teardown-simulation", ids)


@unittest.skipUnless(NODE, "Node.js is required to run the teardown build")
class TeardownBuildRecipe(unittest.TestCase):
    def test_sim_folder_becomes_a_project_owned_offline_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = make_teardown(tmp)
            sim = make_sim(tmp)
            before = {path.name: path.read_bytes() for path in sim.rglob("*") if path.is_file()}
            project = tmp / "project"
            env = {"TEARDOWN_ROOT": str(root)}
            self.assertEqual(run_cli(["init", str(project), "--name", "T"], tmp, env).returncode, 0)
            result = run_cli(["run", "teardown-build", "--input", str(sim), "--json"], project, env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            job = payload.get("job", payload)
            self.assertEqual(job["status"], "SUCCEEDED")

            asset = Project(project).assets()[0]
            page = asset.primary("page")
            self.assertEqual(page.name, "pump-live.html")
            self.assertIn("console.log('pump')", page.read_text(encoding="utf-8"))
            # The sim was copied with its folder layout so relative imports still resolve.
            copied = asset.folder / "inputs" / "pump-live"
            self.assertTrue((copied / "parts" / "rotor.js").is_file())
            names = {item["name"] for item in asset.manifest["inputs"]}
            self.assertIn("pump-live/parts/rotor.js", names)
            checks = {item["id"]: item["status"] for item in asset.manifest["validation"]}
            self.assertEqual(checks["TEARDOWN-BUILD"], "PASS")
            self.assertEqual(checks["TEARDOWN-RENDER"], "NOT_TESTED")
            after = {path.name: path.read_bytes() for path in sim.rglob("*") if path.is_file()}
            self.assertEqual(before, after, "the source sim is never modified")

            report = run_cli(["validate", asset.id, "--json"], project, env)
            self.assertEqual(report.returncode, 0, report.stdout + report.stderr)
            ids = {item["id"]: item["status"] for item in json.loads(report.stdout)["checks"]}
            self.assertEqual(ids.get("PAGE-001"), "PASS")
            self.assertNotIn("ASSET-001", ids)

    def test_a_folder_without_main_js_fails_before_building(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = make_teardown(tmp)
            empty = tmp / "not-a-sim"
            empty.mkdir()
            (empty / "notes.txt").write_text("x", encoding="utf-8")
            project = tmp / "project"
            env = {"TEARDOWN_ROOT": str(root)}
            run_cli(["init", str(project), "--name", "T"], tmp, env)
            result = run_cli(["run", "teardown-build", "--input", str(empty), "--json"], project, env)
            self.assertEqual(result.returncode, cli.EXIT_RUN, result.stdout + result.stderr)
            self.assertIn("main.js", result.stdout + result.stderr)

    def test_a_folder_of_sims_needs_an_entry_and_keeps_its_siblings(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = make_teardown(tmp)
            first = make_sim(tmp, "pump-live")
            make_sim(tmp, "fan-live")
            shared = first.parent / "pump-shared"
            shared.mkdir()
            (shared / "engine.js").write_text("export const engine = 2;\n", encoding="utf-8")
            project = tmp / "project"
            env = {"TEARDOWN_ROOT": str(root)}
            run_cli(["init", str(project), "--name", "T"], tmp, env)
            result = run_cli(["run", "teardown-build", "--input", str(first.parent), "--json"], project, env)
            self.assertEqual(result.returncode, cli.EXIT_RUN, result.stdout + result.stderr)
            self.assertIn("entry=", result.stdout + result.stderr)
            for bad in ("../pump-live", "no-such-sim"):
                result = run_cli(["run", "teardown-build", "--input", str(first.parent), "--set", f"entry={bad}", "--json"], project, env)
                self.assertEqual(result.returncode, cli.EXIT_RUN, (bad, result.stdout + result.stderr))
            result = run_cli(["run", "teardown-build", "--input", str(first.parent), "--set", "entry=pump-live", "--json"], project, env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            asset = [item for item in Project(project).assets() if item.primary("page")][0]
            self.assertEqual(asset.primary("page").name, "pump-live.html")
            copied = asset.folder / "inputs" / first.parent.name
            self.assertTrue((copied / "pump-shared" / "engine.js").is_file())

    def test_film_parameters_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = make_teardown(tmp)
            sim = make_sim(tmp)
            project = tmp / "project"
            env = {"TEARDOWN_ROOT": str(root)}
            run_cli(["init", str(project), "--name", "T"], tmp, env)
            for bad in (["--set", "size=99999x10"], ["--set", "fps=500"], ["--set", "stills=0;rm"], ["--set", "to=-1"]):
                result = run_cli(["run", "teardown-film", "--input", str(sim), *bad, "--json"], project, env)
                self.assertEqual(result.returncode, cli.EXIT_RUN, (bad, result.stdout + result.stderr))

    def test_missing_provider_is_exit_4(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            sim = make_sim(tmp)
            project = tmp / "project"
            env = {"TEARDOWN_ROOT": str(tmp / "missing")}
            run_cli(["init", str(project), "--name", "T"], tmp, env)
            result = run_cli(["run", "teardown-build", "--input", str(sim), "--json"], project, env)
            self.assertEqual(result.returncode, cli.EXIT_PROVIDER, result.stdout + result.stderr)


def _real_teardown():
    saved = os.environ.pop("TEARDOWN_ROOT", None)
    try:
        item = providers.get("teardown")
    finally:
        if saved is not None:
            os.environ["TEARDOWN_ROOT"] = saved
    return item if item.get("available") else None


REAL = _real_teardown()


@unittest.skipUnless(REAL, "teardown with its npm dependencies is not installed")
class RealTeardown(unittest.TestCase):
    def test_upstream_example_builds_through_the_recipe(self):
        sims = Path(REAL["path"]) / "sims"
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            project = tmp / "project"
            run_cli(["init", str(project), "--name", "T"], tmp)
            # v8-live imports ../v8-shared, so the folder of sims goes in with an entry.
            result = run_cli(["run", "teardown-build", "--input", str(sims), "--set", "entry=v8-live", "--json"], project)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            page = Project(project).assets()[0].primary("page")
            text = page.read_text(encoding="utf-8")
            self.assertGreater(page.stat().st_size, 100_000)
            self.assertIn("<script", text)

    @unittest.skipUnless(providers.get("ffmpeg").get("available"), "FFmpeg is required for a film")
    def test_upstream_example_renders_a_short_film(self):
        sims = Path(REAL["path"]) / "sims"
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            project = tmp / "project"
            run_cli(["init", str(project), "--name", "T"], tmp)
            result = run_cli(
                ["run", "teardown-film", "--input", str(sims), "--set", "entry=v8-film", "--set", "to=1", "--set", "fps=12",
                 "--set", "size=480x600", "--json"],
                project,
            )
            if result.returncode != 0 and "Chromium is not installed" in (result.stdout + result.stderr):
                self.skipTest("Playwright's Chromium is not installed for teardown")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            asset = Project(project).assets()[0]
            video = asset.primary("video")
            self.assertEqual(video.read_bytes()[4:8], b"ftyp")
            checks = {item["id"]: item["status"] for item in asset.manifest["validation"]}
            self.assertEqual(checks["TEARDOWN-RENDER"], "PASS")
            self.assertEqual(checks["TEARDOWN-VISUAL"], "NOT_TESTED")

    def test_stills_write_a_review_sheet_and_record_every_frame(self):
        sims = Path(REAL["path"]) / "sims"
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            project = tmp / "project"
            run_cli(["init", str(project), "--name", "T"], tmp)
            result = run_cli(
                ["run", "teardown-film", "--input", str(sims), "--set", "entry=v8-film", "--set", "stills=0,1",
                 "--set", "size=480x600", "--json"],
                project,
            )
            if "Chromium is not installed" in (result.stdout + result.stderr):
                self.skipTest("Playwright's Chromium is not installed for teardown")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            asset = Project(project).assets()[0]
            sheet = asset.primary("preview")
            self.assertEqual(sheet.name, "v8-film-sheet.png")
            recorded = {asset.resolve_artifact(item["path"]) for item in asset.manifest["artifacts"]}
            written = {path for path in (asset.folder / "outputs").rglob("*") if path.is_file()}
            self.assertEqual(written - recorded, set(), "every file capture wrote is an artifact")

    def test_filming_a_live_page_says_it_needs_a_film_page(self):
        # A -live page never publishes window.SIM; capture waits 60 s for it.
        sims = Path(REAL["path"]) / "sims"
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            project = tmp / "project"
            run_cli(["init", str(project), "--name", "T"], tmp)
            result = run_cli(
                ["run", "teardown-film", "--input", str(sims), "--set", "entry=v8-live", "--set", "stills=0",
                 "--set", "size=480x600", "--json"],
                project,
            )
            if "Chromium is not installed" in (result.stdout + result.stderr):
                self.skipTest("Playwright's Chromium is not installed for teardown")
            self.assertEqual(result.returncode, cli.EXIT_RUN, result.stdout + result.stderr)
            self.assertIn("film page", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
