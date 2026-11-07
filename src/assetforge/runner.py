"""Job runner: maps recipe steps to real operations and records evidence.

The runner writes one job folder per non-dry run. A step failure stops the
pipeline, marks the job FAILED and leaves the asset folder for inspection.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import adapters, images, official, providers
from .glb import GlbError, compare_glb, inspect_glb, validate_glb
from .recipes import RecipeError
from .store import Asset, Job, Project, StoreError
from .util import human_bytes, now_iso, write_json

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tga"}
MESH_SUFFIXES = {".glb"}


class RunFailed(RuntimeError):
    pass


class ProviderMissing(RunFailed):
    pass


def _provider(ctx, provider_id: str) -> dict:
    item = providers.get(provider_id, ctx.project)
    if not item.get("available"):
        raise ProviderMissing(f"{provider_id} is unavailable: {item.get('reason') or 'not installed'}")
    return item


def _mark_failed(asset: Asset) -> None:
    try:
        asset.manifest["status"] = "FAILED"
        asset.save()
    except Exception:
        # A failed status write must not hide the original job failure.
        pass


class Context:
    def __init__(self, project: Project, asset: Asset, job: Job, recipe: dict, inputs: dict[str, Path], params: dict, copied: dict[str, Path] | None = None):
        self.project = project
        self.asset = asset
        self.job = job
        self.recipe = recipe
        self.inputs = inputs
        self.copied = copied if copied is not None else {}
        self.params = params
        self.outputs: dict = {}
        self.validation: list[dict] = []

    def input(self, name: str = "") -> Path:
        """Return a project-owned copy for files. Directories (an import
        source) stay external because there is nothing to copy into the asset."""
        if name:
            if name in self.copied:
                return self.copied[name]
            if name in self.inputs and self.inputs[name].is_dir():
                return self.inputs[name]
            raise RunFailed(f"input {name!r} has no project-owned copy")
        for key in ("image", "mesh", "source"):
            if key in self.copied:
                return self.copied[key]
            if key in self.inputs and self.inputs[key].is_dir():
                return self.inputs[key]
        if self.copied:
            return next(iter(self.copied.values()))
        raise RunFailed("recipe needs a project-owned input file but none was supplied")

    def image_input(self) -> Path:
        for path in self.copied.values():
            if path.suffix.lower() in IMAGE_SUFFIXES:
                return path
        raise RunFailed("recipe needs an image input")

    def mesh(self) -> Path:
        if "mesh" in self.outputs:
            return Path(self.outputs["mesh"])
        for path in self.copied.values():
            if path.suffix.lower() in MESH_SUFFIXES:
                return path
        raise RunFailed("recipe needs a .glb input")

    def artifact(self, path: Path, role: str, label: str = "") -> None:
        self.asset.add_artifact(path, role, label or None)

    def report(self, name: str, data: dict) -> Path:
        path = self.asset.path("outputs", name)
        write_json(path, data)
        self.artifact(path, "report", name)
        return path


def _image_inspect(ctx: Context) -> dict:
    source = ctx.image_input()
    info = images.inspect_image(source)
    ctx.outputs["image"] = source
    ctx.outputs["image_info"] = info
    warnings = []
    if info["width"] < 64 or info["height"] < 64:
        warnings.append("small image")
    if info["has_alpha"]:
        warnings.append("alpha present")
    status = "WARNING" if warnings else "PASS"
    return {"status": status, "detail": f"{info['format']} {info['width']}x{info['height']} {info['mode']}" + (f" ({', '.join(warnings)})" if warnings else "")}


def _image_convert(ctx: Context) -> dict:
    source = ctx.outputs.get("image") or ctx.image_input()
    fmt = ctx.params.get("format") or "png"
    suffix = ".jpg" if fmt in ("jpg", "jpeg") else f".{fmt}"
    target = ctx.asset.path("outputs", f"{Path(source).stem}{suffix}")
    result = images.convert_image(
        source,
        target,
        fmt=fmt,
        width=int(ctx.params.get("width") or 0),
        height=int(ctx.params.get("height") or 0),
        quality=int(ctx.params.get("quality") or 90),
    )
    ctx.outputs["image"] = target
    ctx.artifact(target, "image", "converted")
    ctx.asset.set_primary("image", target)
    detail = f"{result['format']} {result['width']}x{result['height']} {human_bytes(result['bytes'])}"
    if result["warnings"]:
        detail += f"; {'; '.join(result['warnings'])}"
    return {"status": "PASS", "detail": detail}


def _image_thumbnail(ctx: Context) -> dict:
    source = ctx.outputs.get("image") or ctx.image_input()
    target = ctx.asset.path("previews", f"{Path(source).stem}-thumb.png")
    result = images.thumbnail(source, target, size=int(ctx.params.get("thumbnail") or 256))
    ctx.artifact(target, "preview", "thumbnail")
    return {"status": "PASS", "detail": f"{result['width']}x{result['height']}"}


def _image_pack_orm(ctx: Context) -> dict:
    paths = [ctx.input(name) for name in ("occlusion", "roughness", "metallic")]
    target = ctx.asset.path("outputs", f"{ctx.asset.id}-orm.png")
    result = images.pack_orm(*paths, target, resize=bool(ctx.params.get("resize") or False))
    ctx.outputs["image"] = target
    ctx.artifact(target, "texture", "orm")
    ctx.asset.set_primary("image", target)
    detail = f"ORM {result['width']}x{result['height']} {human_bytes(result['bytes'])}"
    if result["warnings"]:
        detail += f"; {'; '.join(result['warnings'])}"
    return {"status": "WARNING" if result["warnings"] else "PASS", "detail": detail}


def _image_atlas(ctx: Context) -> dict:
    source = ctx.input("source")
    if not source.is_dir():
        raise RunFailed(f"atlas input is not a directory: {source}")
    files = sorted(
        path for path in source.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not files:
        raise RunFailed(f"atlas input has no images: {source}")
    if len(files) > images.ATLAS_MAX_FRAMES:
        raise RunFailed(
            f"atlas accepts at most {images.ATLAS_MAX_FRAMES} images, got {len(files)}; "
            "split the folder into smaller batches"
        )
    copied = []
    provenance = ctx.job.data.setdefault("sources", {}).setdefault("source_frames", [])
    for path in files:
        record = ctx.asset.add_input(path, "image")
        copied.append(ctx.project.root / record["path"])
        provenance.append({
            "name": path.name,
            "original": str(path.resolve()),
            "sha256": record["sha256"],
            "input": record["path"],
        })
    ctx.job.save()
    target = ctx.asset.path("outputs", "atlas.png")
    metadata = ctx.asset.path("outputs", "atlas.json")
    result = images.make_atlas(
        copied,
        target,
        metadata,
        columns=int(ctx.params.get("columns") or 4),
        padding=int(ctx.params.get("padding") or 2),
    )
    ctx.outputs["image"] = target
    ctx.artifact(target, "texture", "atlas")
    ctx.artifact(metadata, "report", "atlas-metadata")
    ctx.asset.set_primary("image", target)
    return {"status": "PASS", "detail": f"{len(files)} frames, {result['width']}x{result['height']}"}


def _glb_inspect(ctx: Context) -> dict:
    source = ctx.mesh()
    ctx.outputs["source_mesh"] = source
    ctx.artifact(source, "mesh", "source")
    if ctx.asset.primary("mesh") is None:
        ctx.asset.set_primary("mesh", source)
    stats = inspect_glb(source)
    ctx.outputs["stats"] = stats
    ctx.report(f"{source.stem}-inspect.json", stats)
    return {
        "status": "PASS",
        "detail": f"{stats['triangles']} tris, {stats['vertices']} verts, {stats['materials']} materials, {stats['bytes']} bytes",
    }


def _glb_validate(ctx: Context) -> dict:
    source = ctx.mesh()
    report = validate_glb(source)
    if official.available(ctx.project):
        report["checks"] = [
            official.check(ctx.project, source) if check["id"] == "GLB-014" else check
            for check in report["checks"]
        ]
        summary = {status: 0 for status in ("PASS", "WARNING", "FAIL", "NOT_TESTED")}
        for item in report["checks"]:
            summary[item["status"]] += 1
        report["summary"] = summary
        report["status"] = "FAIL" if summary["FAIL"] else ("WARNING" if summary["WARNING"] else "PASS")
    ctx.report(f"{source.stem}-validation.json", report)
    for check in report["checks"]:
        ctx.validation.append({"artifact": source.name, **check})
    return {"status": report["status"], "detail": ", ".join(f"{key}={value}" for key, value in report["summary"].items())}


def _glb_optimize(ctx: Context) -> dict:
    provider = _provider(ctx, "gltf-transform")
    source = ctx.mesh()
    target = ctx.asset.path("outputs", f"{source.stem}-optimized.glb")
    command = list(provider.get("command") or [provider["path"]]) + [
        "optimize",
        str(source),
        str(target),
        "--compress",
        "false",
        "--flatten",
        "false",
        "--instance",
        "false",
        "--join",
        "false",
        "--palette",
        "false",
        "--simplify",
        "false",
        "--texture-compress",
        "false",
        "--prune",
        "true",
        "--prune-solid-textures",
        "false",
        "--weld",
        "true",
    ]
    from .util import run

    result = run(command, timeout=float(ctx.params.get("timeout") or 300), cwd=ctx.project.root)
    ctx.job.log("gltf-transform: " + " ".join(command))
    if result.get("timed_out"):
        raise RunFailed("gltf-transform timed out")
    if result["returncode"] != 0:
        raise RunFailed(f"gltf-transform exited {result['returncode']}: {(result['stderr'] or result['stdout'])[-800:]}")
    stats = inspect_glb(target)
    ctx.outputs["mesh"] = target
    ctx.outputs["optimized_stats"] = stats
    ctx.artifact(target, "mesh", "optimized")
    ctx.asset.set_primary("mesh", target)
    return {"status": "PASS", "detail": f"{stats['triangles']} tris, {stats['bytes']} bytes"}


def _glb_compare(ctx: Context) -> dict:
    source = Path(ctx.outputs.get("source_mesh") or ctx.mesh())
    optimized = ctx.outputs.get("mesh")
    if not optimized or Path(optimized) == source:
        raise RunFailed("glb.compare needs an optimized mesh")
    report = compare_glb(source, optimized)
    ctx.report(f"{source.stem}-comparison.json", report)
    delta = report["delta"]
    return {
        "status": "PASS",
        "detail": f"bytes {delta['bytes']:+d}, triangles {delta['triangles']:+d}, vertices {delta['vertices']:+d}",
    }


def _blender_sample(ctx: Context) -> dict:
    provider = _provider(ctx, "blender")
    target = ctx.asset.path("outputs", "blender-sample.glb")
    adapters.blender_build(provider, target, timeout=float(ctx.params.get("timeout") or 240))
    stats = inspect_glb(target)
    ctx.outputs["mesh"] = target
    ctx.artifact(target, "mesh", "blender-sample")
    ctx.asset.set_primary("mesh", target)
    return {"status": "PASS", "detail": f"Blender {provider.get('version')}; {stats['triangles']} tris"}


def _comfykit_check(ctx: Context) -> dict:
    provider = _provider(ctx, "comfy-kit")
    details = provider.get("details") or {}
    return {"status": "PASS", "detail": f"comfy-kit {provider.get('version') or 'unknown'}; {details.get('presets', 0)} presets"}


def _comfykit_generate(ctx: Context) -> dict:
    provider = _provider(ctx, "comfy-kit")
    root = Path(provider["path"])
    out_dir = ctx.asset.path("outputs", "generated").resolve()
    try:
        out_dir.relative_to(ctx.project.root.resolve())
    except ValueError as exc:
        raise RunFailed("refusing to write comfy-kit output outside the project") from exc
    out_dir.mkdir(parents=True, exist_ok=True)
    result = adapters.comfykit_generate(root, ctx.params, out_dir, timeout=float(ctx.params.get("timeout") or 900))
    files = adapters.comfykit_images(out_dir)
    if not files:
        raise RunFailed("comfy-kit reported success but produced no images in the assigned output folder")
    for path in files:
        ctx.artifact(path, "image", "generated")
    ctx.outputs["images"] = files
    ctx.outputs["image"] = files[0]
    ctx.asset.set_primary("image", files[0])
    return {"status": "PASS", "detail": f"{len(files)} image(s); first {files[0].name}"}


def _comfykit_import(ctx: Context) -> dict:
    _provider(ctx, "comfy-kit")
    source_dir = Path(ctx.input("source"))
    if not source_dir.is_dir():
        raise RunFailed(f"not a directory: {source_dir}")
    files = sorted(
        (item for item in source_dir.iterdir() if item.suffix.lower() in IMAGE_SUFFIXES),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    limit = max(1, min(int(ctx.params.get("limit") or 1), 24))
    if not files:
        raise RunFailed(f"no images in {source_dir}")
    imported = []
    for path in files[:limit]:
        record = ctx.asset.add_input(path, "image")
        imported.append(record)
        ctx.artifact(Path(ctx.project.root) / record["path"], "image", "imported")
    ctx.outputs["images"] = [Path(ctx.project.root) / item["path"] for item in imported]
    ctx.outputs["image"] = ctx.outputs["images"][0]
    ctx.asset.set_primary("image", ctx.outputs["image"])
    return {"status": "PASS", "detail": f"imported {len(imported)} image(s) from comfy-kit output"}


def _img2threejs_probe(ctx: Context) -> dict:
    provider = _provider(ctx, "img2threejs")
    source = ctx.image_input()
    target = ctx.asset.path("outputs", "img2threejs-probe.json")
    data = adapters.img2threejs_probe(Path(provider["path"]), source, target)
    ctx.artifact(target, "report", "img2threejs-probe")
    suitability = data.get("technicalSuitability") or "unknown"
    status = "PASS" if suitability in ("suitable", "good") else "WARNING"
    return {"status": status, "detail": f"technicalSuitability={suitability}; {len(data.get('warnings') or [])} warning(s)"}


def _img2threejs_codegen(ctx: Context) -> dict:
    provider = _provider(ctx, "img2threejs")
    spec = ctx.input("spec")
    target = ctx.asset.path("outputs", f"{Path(spec).stem}.ts")
    adapters.img2threejs_codegen(Path(provider["path"]), spec, target, timeout=float(ctx.params.get("timeout") or 120))
    ctx.artifact(target, "source", "threejs-factory")
    return {"status": "PASS", "detail": f"generated {human_bytes(target.stat().st_size)} of TypeScript"}


def _asset_record(ctx: Context) -> dict:
    ctx.asset.manifest["provenance"]["versions"] = providers.tool_versions(ctx.project)
    ctx.asset.manifest["provenance"]["seed"] = ctx.params.get("seed")
    ctx.asset.manifest["source"] = {"recipe": ctx.recipe["id"], "params": ctx.params, "finished": now_iso()}
    if ctx.validation:
        ctx.asset.set_validation(ctx.validation)
    ctx.asset.save()
    return {"status": "PASS", "detail": f"{len(ctx.asset.manifest.get('artifacts', []))} artifact(s)"}


HANDLERS = {
    "image.inspect": _image_inspect,
    "image.convert": _image_convert,
    "image.thumbnail": _image_thumbnail,
    "image.pack_orm": _image_pack_orm,
    "image.atlas": _image_atlas,
    "glb.inspect": _glb_inspect,
    "glb.validate": _glb_validate,
    "glb.optimize": _glb_optimize,
    "glb.compare": _glb_compare,
    "blender.sample": _blender_sample,
    "comfykit.detect": _comfykit_check,
    "comfykit.generate": _comfykit_generate,
    "comfykit.import": _comfykit_import,
    "img2threejs.probe": _img2threejs_probe,
    "img2threejs.codegen": _img2threejs_codegen,
    "asset.record": _asset_record,
}


def _check_inputs(recipe: dict, inputs: dict[str, Path]) -> None:
    spec = recipe.get("input") or {}
    if spec.get("required"):
        name = spec.get("name", "input")
        if name not in inputs:
            raise RecipeError(f"recipe {recipe['id']} requires --input {name}=<path>")
    for name, item in (recipe.get("inputs") or {}).items():
        if item.get("required") and name not in inputs:
            raise RecipeError(f"recipe {recipe['id']} requires --input {name}=<path>")
    for name, path in inputs.items():
        if not Path(path).exists():
            raise RecipeError(f"input {name!r} does not exist: {path}")


def plan(recipe: dict, inputs: dict[str, Path], params: dict, project: Project | None = None) -> dict:
    providers_now = {item["id"]: item for item in providers.detect(project)}
    needs = []
    for step in recipe["steps"]:
        if step == "glb.optimize":
            needs.append("gltf-transform")
        elif step == "blender.sample":
            needs.append("blender")
        elif step.startswith("comfykit."):
            needs.append("comfy-kit")
        elif step == "img2threejs.probe":
            needs.append("img2threejs")
        elif step == "img2threejs.codegen":
            needs.append("img2threejs")
    return {
        "recipe": recipe["id"],
        "asset": None,
        "inputs": {name: str(path) for name, path in inputs.items()},
        "params": params,
        "steps": recipe["steps"],
        "providers": {item: providers_now.get(item) for item in sorted(set(needs))},
        "dry_run": True,
    }


def execute(project: Project, recipe: dict, inputs: dict[str, Path], params: dict, name: str | None = None, dry_run: bool = False):
    _check_inputs(recipe, inputs)
    if dry_run:
        return plan(recipe, inputs, params, project), None, None

    asset = project.create_asset(name or recipe["id"], recipe["id"], params)
    copied: dict[str, Path] = {}
    sources: dict[str, dict] = {}
    for input_name, path in inputs.items():
        kind = "directory" if Path(path).is_dir() else "image" if Path(path).suffix.lower() in IMAGE_SUFFIXES else "mesh" if Path(path).suffix.lower() in MESH_SUFFIXES else "file"
        sources[input_name] = {"original": str(Path(path).resolve()), "kind": kind}
    try:
        job = Job.create(project, recipe["id"], params, asset.id, sources)
    except Exception:
        # The folder was just created by this call; remove it rather than leave
        # an asset with no job.
        shutil.rmtree(asset.folder, ignore_errors=True)
        raise
    ctx = Context(project, asset, job, recipe, inputs, params, copied)
    try:
        for input_name, path in inputs.items():
            if sources[input_name]["kind"] == "directory":
                continue
            record = asset.add_input(path, sources[input_name]["kind"])
            copied[input_name] = project.root / record["path"]
        for step in recipe["steps"]:
            handler = HANDLERS.get(step)
            if handler is None:
                raise RunFailed(f"no handler for {step}")
            result = handler(ctx)
            status = result.get("status", "PASS")
            job.step(step, "OK" if status in ("PASS", "WARNING", "NOT_TESTED") else "FAIL", result.get("detail", ""), outcome=status)
            if status == "FAIL":
                raise RunFailed(f"{step} failed: {result.get('detail', '')}")
        asset.manifest["status"] = "COMPLETE"
        asset.save()
        job.finish("SUCCEEDED")
        return job, asset, ctx
    except (RunFailed, StoreError, RecipeError, images.ImageError, adapters.AdapterError, GlbError, OSError) as exc:
        message = str(exc) or type(exc).__name__
        _mark_failed(asset)
        job.step("failed", "FAIL", message)
        job.finish("FAILED", message)
        raise
    except Exception as exc:
        # External tools and parsers can raise ordinary exceptions; a job must
        # still finish FAILED with the real type and message instead of hanging
        # in RUNNING.
        message = f"unexpected {type(exc).__name__}: {exc}"
        _mark_failed(asset)
        job.step("failed", "FAIL", message)
        job.finish("FAILED", message)
        raise RunFailed(message) from exc
