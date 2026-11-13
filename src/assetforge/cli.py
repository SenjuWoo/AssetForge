"""AssetForge command line interface.

Exit codes are part of the public contract:
    0 success, 2 usage/recipe error, 3 missing project/asset/job,
    4 provider unavailable, 5 validation or budget failure, 6 run failure.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import __version__, adapters, audio, exporters, images, providers
from . import blenderskills
from . import probe as probe_lib
from . import recipes as recipe_lib
from .adapters import AdapterError
from .glb import GlbError
from .runner import ProviderMissing, RunFailed, execute
from .store import Job, Project, StoreError
from .util import human_bytes

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_PROVIDER = 4
EXIT_VALIDATION = 5
EXIT_RUN = 6


def _print(data, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2))
    else:
        print(data)


def _project(required: bool = True) -> Project | None:
    project = Project.find()
    if project is None and required:
        raise SystemExit(_fail("no AssetForge project here; run `assetforge init` first", EXIT_NOT_FOUND))
    return project


def _fail(message: str, code: int) -> int:
    print(f"error: {message}", file=sys.stderr)
    return code


def _parse_inputs(values: list[str], recipe: dict) -> dict[str, Path]:
    spec_name = (recipe.get("input") or {}).get("name") or "input"
    inputs: dict[str, Path] = {}
    for raw in values:
        name = None
        value = raw
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)=(.+)$", raw)
        if match and Path(match.group(2)).expanduser().exists():
            name, value = match.group(1), match.group(2)
        path = Path(value).expanduser().resolve()
        if name is None:
            name = spec_name if len(values) == 1 else path.stem
        if name in inputs:
            raise recipe_lib.RecipeError(f"input {name!r} was given twice")
        inputs[name] = path
    return inputs


def _parse_sets(values: list[str]) -> dict[str, str]:
    overrides = {}
    for item in values:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise recipe_lib.RecipeError(f"--set expects key=value, got {item!r}")
        overrides[name] = value
    return overrides


def cmd_doctor(args) -> int:
    project = Project.find()
    checks = []
    python_ok = sys.version_info >= (3, 10)
    checks.append({
        "id": "python",
        "status": "PASS" if python_ok else "FAIL",
        "detail": f"{sys.version.split()[0]} ({sys.executable})",
    })
    checks.append({"id": "core", "status": "PASS", "detail": f"assetforge {__version__} imports"})
    checks.append({
        "id": "project",
        "status": "PASS" if project else "WARNING",
        "detail": str(project.root) if project else "no project in this folder; run `assetforge init`",
    })
    provider_list = providers.detect(project)
    for item in provider_list:
        checks.append({
            "id": item["id"],
            "status": "PASS" if item["available"] else "WARNING",
            "detail": (f"{item.get('version') or 'available'} {item.get('path') or ''}").strip()
            if item["available"]
            else item.get("reason", "not available"),
        })
    failed = any(item["status"] == "FAIL" for item in checks)
    degraded = any(item["status"] == "WARNING" for item in checks)
    report = {
        "schema": 1,
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "project": str(project.root) if project else None,
        "checks": checks,
        "providers": provider_list,
        "state": "BLOCKED" if failed else ("DEGRADED" if degraded else "READY"),
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"AssetForge {__version__}  {report['state']}")
        for item in checks:
            print(f"  {item['status']:<9} {item['id']:<16} {item['detail']}")
    return 0 if not failed else 1


def capabilities_payload(project=None) -> dict:
    now = {item["id"]: item for item in providers.detect(project)}
    capabilities = [
        {"id": "image-processing", "status": "IMPLEMENTED", "provider": "pillow", "available": now["pillow"]["available"]},
        {"id": "glb-inspect", "status": "IMPLEMENTED", "provider": "core", "available": True},
        {"id": "glb-validate-structural", "status": "IMPLEMENTED", "provider": "core", "available": True},
        {"id": "glb-validate-official", "status": "IMPLEMENTED", "provider": "gltf-validator", "available": now["gltf-validator"]["available"]},
        {"id": "glb-optimize", "status": "IMPLEMENTED", "provider": "gltf-transform", "available": now["gltf-transform"]["available"]},
        {"id": "source-probe", "status": "IMPLEMENTED", "provider": "core", "available": True},
        {"id": "glb-rig-validation", "status": "IMPLEMENTED", "provider": "core", "available": True, "note": "skin, weight and animation data consistency; deformation is not rendered"},
        {"id": "glb-material-validation", "status": "IMPLEMENTED", "provider": "core", "available": True},
        {"id": "mesh-convert", "status": "IMPLEMENTED", "provider": "blender", "available": now["blender"]["available"], "formats": list(probe_lib.CONVERTIBLE)},
        {"id": "mesh-gameready", "status": "IMPLEMENTED", "provider": "blender", "available": now["blender"]["available"]},
        {"id": "blender-export", "status": "IMPLEMENTED", "provider": "blender", "available": now["blender"]["available"]},
        {"id": "blender-skills", "status": "IMPLEMENTED", "provider": "blender-skills", "available": now["blender-skills"]["available"]},
        {"id": "blender-asset-qa", "status": "IMPLEMENTED", "provider": "blender-skills", "available": now["blender-skills"]["available"]},
        {"id": "comfy-kit-generation", "status": "IMPLEMENTED", "provider": "comfy-kit", "available": now["comfy-kit"]["available"]},
        {"id": "img2threejs-probe", "status": "IMPLEMENTED", "provider": "img2threejs", "available": now["img2threejs"]["available"]},
        {"id": "img2threejs-codegen", "status": "IMPLEMENTED", "provider": "img2threejs", "available": now["img2threejs"]["available"]},
        {"id": "img2threejs-reconstruction", "status": "PLANNED", "provider": "img2threejs", "available": False},
        {"id": "export-roblox", "status": "IMPLEMENTED", "engine_import": "NOT_TESTED"},
        {"id": "export-godot", "status": "IMPLEMENTED", "engine_import": "NOT_TESTED", "note": "run `assetforge engine-check <file.glb>` for a real Godot import"},
        {"id": "godot-import-check", "status": "IMPLEMENTED", "provider": "godot", "available": now["godot"]["available"], "note": "headless import and load; rendering is not tested"},
        {"id": "teardown-build", "status": "IMPLEMENTED", "provider": "teardown", "available": now["teardown"]["available"], "note": "a sim folder becomes one offline HTML page; it is not a game-engine asset"},
        {"id": "teardown-film", "status": "IMPLEMENTED", "provider": "teardown", "available": now["teardown"]["available"] and now["ffmpeg"]["available"], "note": "frame-accurate mp4 or a review sheet rendered in headless Chromium; visual quality is not judged"},
        {"id": "ffmpeg", "status": "IMPLEMENTED", "provider": "ffmpeg", "available": now["ffmpeg"]["available"], "note": "audio finishing and measurement; teardown-film encodes through it"},
        {"id": "audio-voice", "status": "IMPLEMENTED", "provider": "audio-speech", "available": now["audio-speech"]["available"] and now["ffmpeg"]["available"], "note": "Qwen3-TTS voice design and cloning, Dia nonverbals; Whisper checks the words; nobody listens"},
        {"id": "audio-voice-fast", "status": "IMPLEMENTED", "provider": "audio-kokoro", "available": now["audio-kokoro"]["available"] and now["ffmpeg"]["available"], "note": "Kokoro preset voices"},
        {"id": "audio-sfx", "status": "IMPLEMENTED", "provider": "audio-sfx", "available": now["audio-sfx"]["available"] and now["ffmpeg"]["available"], "note": "MOSS-SoundEffect v2; CLAP scores prompt match; nobody listens"},
        {"id": "audio-process", "status": "IMPLEMENTED", "provider": "ffmpeg", "available": now["ffmpeg"]["available"], "note": "trim, level, convert and measure existing audio"},
        {"id": "audio-music", "status": "PLANNED", "note": "ACE-Step 1.5 is the candidate; not integrated"},
        {"id": "imagemagick", "status": "DETECTED_ONLY", "provider": "imagemagick", "available": now["imagemagick"]["available"], "note": "no recipe calls it yet"},
        {"id": "export-generic", "status": "IMPLEMENTED", "engine_import": "NOT_TESTED"},
        {"id": "export-minecraft-sounds", "status": "IMPLEMENTED", "engine_import": "NOT_TESTED", "note": "Ogg sounds plus sounds.json for a resource pack or mod; sounds only"},
        {"id": "ai-3d-providers", "status": "PLANNED"},
        {"id": "rig-deformation-preview", "status": "PLANNED"},
        {"id": "graphite-integration", "status": "PLANNED"},
        {"id": "mcp-server", "status": "PLANNED"},
    ]
    return {"schema": 1, "version": __version__, "capabilities": capabilities}


def cmd_capabilities(args) -> int:
    payload = capabilities_payload(Project.find())
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for item in payload["capabilities"]:
            extra = " available" if item.get("available") else ""
            print(f"{item['status']:<12} {item['id']:<28}{extra}")
    return 0


def cmd_providers(args) -> int:
    project = Project.find()
    items = providers.detect(project)
    if args.json:
        print(json.dumps({"schema": 1, "providers": items}, indent=2))
    else:
        for item in items:
            state = "available" if item["available"] else "missing"
            version = f" {item['version']}" if item.get("version") else ""
            print(f"{item['id']:<16} {state:<9}{version}  {item.get('path') or item.get('reason', '')}")
    return 0


def cmd_blender_skills(args) -> int:
    project = Project.find()
    provider = providers.get("blender-skills", project)
    if not provider.get("available"):
        if args.json:
            print(json.dumps({
                "schema": 1,
                "provider": provider,
                "skills": [],
                "routes": sorted(blenderskills.ROUTES),
            }, indent=2))
        else:
            print(f"blender-skills unavailable: {provider.get('reason')}", file=sys.stderr)
        return EXIT_PROVIDER
    details = provider.get("details") or {}
    catalog = blenderskills.catalog(Path(details["skills_dir"]))
    selected = blenderskills.route(args.route, catalog) if args.route else catalog
    payload = {
        "schema": 1,
        "provider": provider,
        "route": args.route,
        "skills": selected,
        "routes": blenderskills.ROUTES,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for item in selected:
            version = f" {item['version']}" if item.get("version") else ""
            print(f"{item['name']:<34}{version:<10}{item['description']}")
        print(f"{len(catalog)} skill(s); tested upstream revision in docs/PROVIDERS.md")
    return 0



def cmd_audio_setup(args) -> int:
    names = args.runtime or ["speech", "sfx", "kokoro"]
    unknown = [name for name in names if name not in audio.RUNTIMES]
    if unknown:
        return _fail(f"unknown audio runtime(s) {', '.join(unknown)}; choose from {', '.join(audio.RUNTIMES)}", EXIT_USAGE)
    if args.list:
        payload = {"schema": 1, "home": str(audio.home()), "runtimes": [audio.runtime_state(name) for name in names]}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"audio home {payload['home']}")
            for item in payload["runtimes"]:
                state = "ready" if item["available"] else "missing"
                print(f"  {item['id']:<14} {state:<8} {item['details']['licenses']}  {item.get('reason') or ''}")
        return 0
    log = (lambda message: print(message, file=sys.stderr)) if args.json else print
    try:
        results = audio.setup(names, device=args.device, log=log)
    except audio.AudioError as exc:
        return _fail(str(exc), EXIT_PROVIDER)
    ok = all(item["ok"] for item in results)
    if args.json:
        print(json.dumps({"schema": 1, "home": str(audio.home()), "results": results, "ok": ok}, indent=2))
    else:
        for item in results:
            if item["ok"]:
                print(f"ready   {item['runtime']:<8} torch {item.get('torch')} {'GPU ' + str(item.get('gpu')) if item.get('cuda') else 'CPU only'}")
            else:
                print(f"FAILED  {item['runtime']:<8} {item.get('error')}")
        print("Models download on first use into " + str(audio.hf_home()))
    return 0 if ok else EXIT_PROVIDER


def cmd_probe(args) -> int:
    try:
        report = probe_lib.probe(Path(args.path))
    except FileNotFoundError as exc:
        return _fail(f"no such file or folder: {exc}", EXIT_NOT_FOUND)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(probe_lib.render(report))
    return EXIT_VALIDATION if any(item["status"] == "FAIL" for item in report["findings"]) else 0


def cmd_engine_check(args) -> int:
    source = Path(args.path)
    if not source.is_file():
        return _fail(f"no such file: {source}", EXIT_NOT_FOUND)
    if source.suffix.lower() != ".glb":
        return _fail("engine-check reads a .glb; convert other formats first with the mesh-convert recipe", EXIT_USAGE)
    provider = providers.get("godot", Project.find())
    if not provider["available"]:
        return _fail(provider["reason"], EXIT_PROVIDER)
    try:
        result = adapters.godot_import_check(provider, source, timeout=args.timeout)
    except adapters.AdapterError as exc:
        report = {"schema": 1, "source": str(source), "engine": "godot", "engine_version": provider.get("version"),
                  "status": "FAIL", "error": str(exc)}
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"FAIL  Godot {provider.get('version')} could not use {source.name}: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    # A scene with no mesh loads, but it is not what an asset export means.
    status = "PASS" if result["meshes"] > 0 and not result["engine_errors"] else "WARNING"
    report = {"schema": 1, "source": str(source), "status": status,
              "evidence": "godot --headless --import, then load and instantiate the imported scene",
              "not_tested": ["rendering", "materials on screen", "animation playback", "physics"], **result}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{status}  Godot {result['engine_version']} imported and loaded {source.name}")
        print(f"  meshes {result['meshes']}  skeletons {result['skeletons']}  animations {len(result['animations'])}")
        for line in result["engine_errors"]:
            print(f"  {line}")
        print("  not tested: " + ", ".join(report["not_tested"]))
    return 0


def cmd_init(args) -> int:
    root = Path(args.path).expanduser().resolve()
    project = Project.init(root, args.name)
    print(f"project {project.data['name']} at {project.root}")
    return 0


def cmd_recipes(args) -> int:
    project = Project.find()
    if args.recipe and args.recipe not in ("list", "show"):
        recipe = recipe_lib.get(args.recipe, project)
        if args.json:
            print(json.dumps(recipe, indent=2))
        else:
            print(f"{recipe['id']}  {recipe['title']}")
            print(recipe.get("description", ""))
            print("params: " + (", ".join(recipe.get("params", {})) or "none"))
            print("steps:  " + " -> ".join(recipe["steps"]))
        return 0
    items = list(recipe_lib.load_all(project).values())
    if args.json:
        print(json.dumps(items, indent=2))
    else:
        for item in items:
            print(f"{item['id']:<24} {item['title']}")
    return 0


def cmd_run(args) -> int:
    project = _project()
    recipe = recipe_lib.get(args.recipe, project)
    inputs = _parse_inputs(args.input, recipe)
    params = recipe_lib.resolve_params(recipe, _parse_sets(args.set))
    if args.dry_run:
        report, _, _ = execute(project, recipe, inputs, params, args.asset, dry_run=True)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"dry run: {recipe['id']}")
            for step in report["steps"]:
                print(f"  {step}")
            for name, item in report["providers"].items():
                state = "available" if item and item.get("available") else "MISSING"
                print(f"  provider {name}: {state}")
        return 0
    try:
        job, asset, _ = execute(project, recipe, inputs, params, args.asset, dry_run=False)
    except ProviderMissing as exc:
        return _fail(str(exc), EXIT_PROVIDER)
    except (RunFailed, StoreError, recipe_lib.RecipeError, images.ImageError, AdapterError, GlbError, OSError) as exc:
        return _fail(str(exc), EXIT_RUN)
    if args.json:
        print(json.dumps({"job": job.data, "asset": asset.manifest}, indent=2))
    else:
        print(f"job {job.id} {job.data['status']}")
        print(f"asset {asset.id}")
        for step in job.data["steps"]:
            print(f"  {step['status']:<4} {step['name']:<20} {step.get('detail', '')}")
    return EXIT_OK if job.data["status"] == "SUCCEEDED" else EXIT_RUN


def cmd_status(args) -> int:
    project = _project()
    job = Job.latest(project) if args.last or not args.job_id else Job.load(project, args.job_id)
    if job is None:
        return _fail("no jobs yet", EXIT_NOT_FOUND)
    if args.json:
        print(json.dumps(job.data, indent=2))
    else:
        print(f"{job.id}  {job.data['recipe']}  {job.data['status']}")
        for step in job.data["steps"]:
            print(f"  {step['status']:<4} {step['name']:<20} {step.get('detail', '')}")
        if job.data.get("error"):
            print(f"error: {job.data['error']}")
    return 0


def cmd_inspect(args) -> int:
    project = _project()
    try:
        asset = project.asset(args.asset)
    except StoreError as exc:
        return _fail(str(exc), EXIT_NOT_FOUND)
    if args.json:
        print(json.dumps(asset.manifest, indent=2))
    else:
        manifest = asset.manifest
        print(f"{manifest['id']}  {manifest['name']}  [{manifest.get('status', 'UNKNOWN')}]")
        print(f"source: {manifest.get('source', {}).get('recipe') or 'none'}")
        for item in manifest.get("inputs", []):
            print(f"  input    {item['path']}  {human_bytes(item['bytes'])}")
        for item in manifest.get("artifacts", []):
            print(f"  artifact {item['role']:<8} {item['path']}  {human_bytes(item['bytes'])}")
        for item in manifest.get("exports", []):
            print(f"  export   {item['target']:<8} {item['path']}  {item['status']}")
        validation = manifest.get("validation") or []
        if validation:
            counts = {}
            for item in validation:
                counts[item["status"]] = counts.get(item["status"], 0) + 1
            print("validation: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 0


def cmd_validate(args) -> int:
    project = _project()
    try:
        asset = project.asset(args.asset)
        report = exporters.validate_asset(project, asset)
    except (StoreError, exporters.ExportError) as exc:
        return _fail(str(exc), EXIT_NOT_FOUND)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for item in report["checks"]:
            print(f"{item['status']:<10} {item['id']:<12} {item.get('artifact', '')}  {item['detail']}")
        print("summary: " + ", ".join(f"{key}={value}" for key, value in report["summary"].items()))
    return EXIT_VALIDATION if report["status"] == "FAIL" else 0


def cmd_export(args) -> int:
    project = _project()
    try:
        asset = project.asset(args.asset)
        result = exporters.export(project, asset, args.target, dry_run=args.dry_run, namespace=args.namespace or "")
    except StoreError as exc:
        return _fail(str(exc), EXIT_NOT_FOUND)
    except exporters.ExportError as exc:
        return _fail(str(exc), EXIT_VALIDATION if "blocked" in str(exc) else EXIT_USAGE)
    except (GlbError, OSError) as exc:
        return _fail(str(exc), EXIT_VALIDATION)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{'dry run: ' if args.dry_run else ''}export {asset.id} -> {args.target}  {result['status']}")
        for item in result["checks"]:
            print(f"  {item['status']:<10} {item['id']:<22} {item['detail']}")
        if result.get("out_dir"):
            print(f"  written to {result['out_dir']}")
    return EXIT_VALIDATION if result["status"] == "FAIL" else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assetforge", description="AI-assisted asset production, validation and export")
    parser.add_argument("--version", action="version", version=f"assetforge {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="report core and provider status")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    caps = sub.add_parser("capabilities", help="list implemented and planned capabilities")
    caps.add_argument("--json", action="store_true")
    caps.set_defaults(func=cmd_capabilities)

    prov = sub.add_parser("providers", help="detect external providers")
    prov.add_argument("--json", action="store_true")
    prov.set_defaults(func=cmd_providers)

    bskills = sub.add_parser("blender-skills", help="list or route blender-skills workflows")
    bskills.add_argument("--route", choices=sorted(blenderskills.ROUTES))
    bskills.add_argument("--json", action="store_true")
    bskills.set_defaults(func=cmd_blender_skills)

    probe = sub.add_parser("probe", help="inspect a file or folder and name the recipes that fit (no project needed)")
    probe.add_argument("path")
    probe.add_argument("--json", action="store_true")
    probe.set_defaults(func=cmd_probe)

    asetup = sub.add_parser("audio-setup", help="install or check the local audio runtimes (speech, sfx, kokoro) with uv")
    asetup.add_argument("runtime", nargs="*", help="speech, sfx or kokoro; default all")
    asetup.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    asetup.add_argument("--list", action="store_true", help="show what is installed without changing anything")
    asetup.add_argument("--json", action="store_true")
    asetup.set_defaults(func=cmd_audio_setup)

    engine = sub.add_parser("engine-check", help="import a GLB into a real engine (Godot, headless) and load it")
    engine.add_argument("path")
    engine.add_argument("--engine", choices=("godot",), default="godot")
    engine.add_argument("--timeout", type=float, default=300)
    engine.add_argument("--json", action="store_true")
    engine.set_defaults(func=cmd_engine_check)

    init = sub.add_parser("init", help="create a project")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--name")
    init.set_defaults(func=cmd_init)

    rec = sub.add_parser("recipes", help="list recipes or show one")
    rec.add_argument("recipe", nargs="?")
    rec.add_argument("--json", action="store_true")
    rec.set_defaults(func=cmd_recipes)

    run = sub.add_parser("run", help="run a recipe")
    run.add_argument("recipe")
    run.add_argument("--input", action="append", default=[], help="path or name=path")
    run.add_argument("--set", action="append", default=[], help="parameter override key=value")
    run.add_argument("--asset", help="asset name override")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--json", action="store_true")
    run.set_defaults(func=cmd_run)

    status = sub.add_parser("status", help="show a job")
    status.add_argument("job_id", nargs="?")
    status.add_argument("--last", action="store_true")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    inspect = sub.add_parser("inspect", help="show an asset manifest")
    inspect.add_argument("asset")
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(func=cmd_inspect)

    validate = sub.add_parser("validate", help="validate an asset")
    validate.add_argument("asset")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=cmd_validate)

    export = sub.add_parser("export", help="package an asset for an engine")
    export.add_argument("asset")
    export.add_argument("--target", required=True, choices=sorted(exporters.profiles()))
    export.add_argument("--dry-run", action="store_true")
    export.add_argument("--namespace", help="minecraft target: the mod or resource-pack namespace for sounds.json")
    export.add_argument("--json", action="store_true")
    export.set_defaults(func=cmd_export)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except recipe_lib.RecipeError as exc:
        return _fail(str(exc), EXIT_USAGE)
    except StoreError as exc:
        return _fail(str(exc), EXIT_NOT_FOUND)
    except KeyboardInterrupt:
        return _fail("cancelled", EXIT_RUN)


if __name__ == "__main__":
    raise SystemExit(main())
