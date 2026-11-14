"""Validation reports and engine export packaging.

Export means: copy the validated mesh, texture or audio deliverables into a target
folder, write a machine-readable record and import notes. It never claims the
asset was imported into an engine; that check is always NOT_TESTED here.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import audio, images, official, providers
from .glb import inspect_glb, validate_glb
from .store import Asset, Project, StoreError
from .util import now_iso, read_json, sha256_file, write_json, write_text


class ExportError(RuntimeError):
    pass


def profile_dir() -> Path:
    return Path(__file__).resolve().parent / "data" / "profiles"


def load_profile(profile_id: str) -> dict:
    path = profile_dir() / f"{profile_id}.json"
    if not path.exists():
        raise ExportError(f"unknown export profile {profile_id!r}")
    return read_json(path)


def profiles() -> dict[str, dict]:
    return {path.stem: read_json(path) for path in sorted(profile_dir().glob("*.json"))}


def _primary_mesh(asset: Asset) -> tuple[Path, bool]:
    """Return the declared mesh deliverable. Falls back to a deterministic
    label order only for older manifests without a primary entry."""
    declared = (asset.manifest.get("primary") or {}).get("mesh")
    if declared:
        return asset.resolve_artifact(declared), True
    candidates = [item for item in asset.manifest.get("artifacts", []) if item.get("role") == "mesh"]
    for label in ("optimized", "deliverable", "source"):
        for item in candidates:
            if item.get("label") == label:
                return asset.resolve_artifact(item["path"]), False
    if candidates:
        return asset.resolve_artifact(candidates[0]["path"]), False
    raise ExportError("asset has no GLB artifact to export")


def _image_artifacts(asset: Asset) -> list[dict]:
    """Texture deliverables only. Review sheets and reports are evidence, not
    export textures."""
    return [
        item for item in asset.manifest.get("artifacts", [])
        if item.get("media_type", "").startswith("image/") and item.get("role") in ("texture", "image")
    ]


def _primary_image(asset: Asset) -> tuple[Path, bool]:
    """Return the declared texture deliverable, falling back to a deterministic
    label order only when no primary image is recorded."""
    declared = (asset.manifest.get("primary") or {}).get("image")
    if declared:
        return asset.resolve_artifact(declared), True
    candidates = _image_artifacts(asset)
    for label in ("orm", "atlas", "deliverable", "source"):
        for item in candidates:
            if item.get("label") == label:
                return asset.resolve_artifact(item["path"]), False
    if candidates:
        return asset.resolve_artifact(candidates[0]["path"]), False
    raise ExportError("asset has no image artifact to export")


def _audio_artifacts(asset: Asset) -> list[dict]:
    """Finished sounds only; takes and reference voices are evidence."""
    return [item for item in asset.manifest.get("artifacts", []) if item.get("role") == "audio"]


def _audio_settings(asset: Asset) -> dict:
    """The loudness target and ceiling the asset was finished to, if recorded."""
    try:
        return read_json(asset.path("outputs", "audio.json"))
    except (OSError, ValueError):
        return {}


def _audio_validation(asset: Asset, items: list[dict]) -> list[dict]:
    ffmpeg = providers.get("ffmpeg", asset.project).get("path")
    settings = _audio_settings(asset)
    checks: list[dict] = []
    for item in items:
        try:
            path = asset.resolve_artifact(item["path"])
        except Exception as exc:
            checks.append({"artifact": item.get("path"), "id": "ASSET-002", "status": "FAIL", "detail": str(exc)})
            continue
        if not ffmpeg:
            checks.append({"artifact": item["path"], "id": "AUDIO-001", "status": "NOT_TESTED", "detail": "ffmpeg is not available to decode it"})
            continue
        try:
            found, _ = audio.checks(ffmpeg, path, loudness=settings.get("loudness"), true_peak=float(settings.get("true_peak") or -1))
        except audio.AudioError as exc:
            found = [{"id": "AUDIO-001", "status": "FAIL", "detail": str(exc)}]
        checks.extend({**check, "artifact": item["path"]} for check in found)
    # Transcript and prompt-match evidence comes from the run; carry it over.
    recorded = asset.manifest.get("validation") or []
    for check in recorded if isinstance(recorded, list) else []:
        if check.get("id") in ("AUDIO-ASR", "AUDIO-CLAP", "AUDIO-LISTEN"):
            checks.append(check)
    return checks


EXTERNAL_REFERENCE = re.compile(r"""<(?:script|link|img)\b[^>]*\b(?:src|href)\s*=\s*["']?(?:https?:)?//""", re.I)


def _presentation_check(asset: Asset, item: dict) -> dict:
    """A page must open offline as one file; a video must be a real MP4.
    Neither check says anything about how it looks."""
    try:
        path = asset.resolve_artifact(item["path"])
    except Exception as exc:
        return {"id": "ASSET-002", "status": "FAIL", "detail": str(exc)}
    if item["role"] == "video":
        head = path.read_bytes()[:12]
        if head[4:8] != b"ftyp":
            return {"id": "VIDEO-001", "status": "FAIL", "detail": "not an MP4 container (no ftyp box)"}
        return {"id": "VIDEO-001", "status": "PASS", "detail": f"MP4 container, {path.stat().st_size} bytes; playback not reviewed"}
    text = path.read_text(encoding="utf-8", errors="replace")
    if "<script" not in text.lower():
        return {"id": "PAGE-001", "status": "FAIL", "detail": "page has no script; it is not a built simulator"}
    external = EXTERNAL_REFERENCE.search(text)
    if external:
        return {"id": "PAGE-001", "status": "FAIL", "detail": f"page loads from the network ({external.group(0)[:60]}); it will not open offline"}
    return {"id": "PAGE-001", "status": "PASS", "detail": f"single offline page, {path.stat().st_size} bytes; rendering not reviewed"}


def validate_asset(project: Project, asset: Asset) -> dict:
    checks: list[dict] = []
    meshes = [item for item in asset.manifest.get("artifacts", []) if item.get("role") == "mesh" or item.get("path", "").lower().endswith(".glb")]
    image_items = _image_artifacts(asset)
    presentation = [item for item in asset.manifest.get("artifacts", []) if item.get("role") in ("page", "video")]
    sounds = _audio_artifacts(asset)
    if not meshes and not image_items and not presentation and not sounds:
        checks.append({
            "artifact": None,
            "id": "ASSET-001",
            "status": "FAIL",
            "detail": "asset has no mesh, image, audio, page or video artifact; source-only artifacts such as Three.js TypeScript remain editable intermediates and are not exported",
        })
    checks.extend(_audio_validation(asset, sounds))
    for item in presentation:
        checks.append({"artifact": item["path"], **_presentation_check(asset, item)})
    for item in meshes:
        try:
            path = asset.resolve_artifact(item["path"])
        except Exception as exc:
            checks.append({"artifact": item.get("path"), "id": "ASSET-002", "status": "FAIL", "detail": str(exc)})
            continue
        report = validate_glb(path)
        for check in report["checks"]:
            if check["id"] == "GLB-014":
                check = official.check(project, path)
            checks.append({"artifact": item["path"], **check})

    for item in image_items:
        try:
            path = asset.resolve_artifact(item["path"])
            info = images.inspect_image(path)
            checks.append({
                "artifact": item["path"],
                "id": "IMG-001",
                "status": "PASS",
                "detail": f"{info['format']} {info['width']}x{info['height']} {info['mode']}",
            })
        except Exception as exc:
            checks.append({"artifact": item.get("path"), "id": "IMG-001", "status": "FAIL", "detail": str(exc)})

    summary = {status: 0 for status in ("PASS", "WARNING", "FAIL", "NOT_TESTED")}
    for item in checks:
        summary[item["status"]] += 1
    overall = "FAIL" if summary["FAIL"] else ("WARNING" if summary["WARNING"] else "PASS")
    report = {"schema": 1, "asset": asset.id, "created": now_iso(), "checks": checks, "summary": summary, "status": overall}
    path = asset.path("outputs", "validation.json")
    write_json(path, report)
    asset.set_validation(checks)
    return report


def _budget(checks: list[dict], name: str, value, limit, unit: str = "") -> None:
    if not limit:
        checks.append({"id": f"BUDGET-{name.upper()}", "status": "NOT_TESTED", "detail": f"no {name} budget in this profile"})
        return
    status = "PASS" if value <= limit else "FAIL"
    checks.append({
        "id": f"BUDGET-{name.upper()}",
        "status": status,
        "detail": f"{value}{unit} / budget {limit}{unit}",
    })


def export(project: Project, asset: Asset, target: str, dry_run: bool = False, namespace: str = "") -> dict:
    profile = load_profile(target)
    validation = validate_asset(project, asset)
    if validation["status"] == "FAIL":
        failed = [item for item in validation["checks"] if item["status"] == "FAIL"]
        detail = "; ".join(item["detail"] for item in failed[:3])
        raise ExportError(f"export blocked by validation: {detail}")

    mesh_items = [item for item in asset.manifest.get("artifacts", []) if item.get("role") == "mesh" or item.get("path", "").lower().endswith(".glb")]
    image_items = _image_artifacts(asset)
    if not mesh_items and _audio_artifacts(asset):
        return _export_audio(project, asset, profile, validation, dry_run, namespace)
    if profile.get("format") == "ogg":
        raise ExportError(f"the {profile['title']} profile packages sounds only; this asset has no finished audio")
    kind = "mesh" if mesh_items else "texture"
    budgets = profile.get("budgets") or {}

    if kind == "mesh":
        try:
            primary, declared = _primary_mesh(asset)
        except StoreError as exc:
            raise ExportError(f"cannot resolve the primary mesh: {exc}") from exc
        stats = inspect_glb(primary)
        checks = [
            {"id": "FORMAT-001", "status": "PASS", "detail": f"glTF binary, {stats['bytes']} bytes"},
            {
                "id": "PRIMARY-001",
                "status": "PASS" if declared else "WARNING",
                "detail": asset.manifest.get("primary", {}).get("mesh") or "manifest has no primary; deterministic label fallback used",
            },
        ]
        _budget(checks, "triangles", stats["triangles"], budgets.get("triangles"))
        _budget(checks, "vertices", stats["vertices"], budgets.get("vertices"))
        _budget(checks, "textures", stats["images"], budgets.get("textures"))
        if budgets.get("joints") and stats["skins"]:
            _budget(checks, "joints", stats["rig"]["max_joints"], budgets.get("joints"))
    else:
        try:
            primary, declared = _primary_image(asset)
        except StoreError as exc:
            raise ExportError(f"cannot resolve the primary image: {exc}") from exc
        info = images.inspect_image(primary)
        checks = [
            {"id": "FORMAT-002", "status": "PASS", "detail": f"{info['format']} image, {info['width']}x{info['height']}, {info['bytes']} bytes"},
            {
                "id": "PRIMARY-001",
                "status": "PASS" if declared else "WARNING",
                "detail": asset.manifest.get("primary", {}).get("image") or "manifest has no primary image; deterministic label fallback used",
            },
        ]
        for name in ("triangles", "vertices", "textures"):
            checks.append({"id": f"BUDGET-{name.upper()}", "status": "NOT_TESTED", "detail": "texture-only asset has no mesh budget"})

    texture_limit = int(budgets.get("texture_size") or 0)
    if not texture_limit:
        checks.append({"id": "BUDGET-TEXTURE_SIZE", "status": "NOT_TESTED", "detail": "no texture size budget"})
    elif not image_items and kind == "mesh" and stats.get("image_details"):
        # The usual GLB carries its textures inside the file; measure those.
        oversize = [
            f"image {item['index']} {item['width']}x{item['height']}"
            for item in stats["image_details"]
            if item["width"] and max(item["width"], item["height"]) > texture_limit
        ]
        unread = sum(1 for item in stats["image_details"] if not item["width"])
        if oversize:
            status, detail = "FAIL", "; ".join(oversize) + f" over {texture_limit}px"
        elif unread:
            status, detail = "NOT_TESTED", f"{unread} embedded image(s) have an unrecognized header"
        else:
            status, detail = "PASS", f"{len(stats['image_details'])} embedded texture(s) <= {texture_limit}px"
        checks.append({"id": "BUDGET-TEXTURE_SIZE", "status": status, "detail": detail})
    elif not image_items:
        checks.append({"id": "BUDGET-TEXTURE_SIZE", "status": "NOT_TESTED", "detail": "asset has no textures"})
    else:
        oversize = []
        for item in image_items:
            try:
                info = images.inspect_image(asset.resolve_artifact(item["path"]))
                if max(info["width"], info["height"]) > texture_limit:
                    oversize.append(f"{Path(item['path']).name} {info['width']}x{info['height']}")
            except Exception:
                oversize.append(f"{Path(item['path']).name} unreadable")
        checks.append({
            "id": "BUDGET-TEXTURE_SIZE",
            "status": "FAIL" if oversize else "PASS",
            "detail": "; ".join(oversize) if oversize else f"all loose textures <= {texture_limit}px",
        })

    checks.append({
        "id": "ENGINE-IMPORT",
        "status": "NOT_TESTED",
        "detail": f"{profile['title']} was not launched; this is packaging and structural validation only",
    })
    summary = {status: 0 for status in ("PASS", "WARNING", "FAIL", "NOT_TESTED")}
    for item in checks:
        summary[item["status"]] += 1
    overall = "FAIL" if summary["FAIL"] else ("WARNING" if summary["WARNING"] else "PASS")

    plan = {
        "target": target,
        "asset": asset.id,
        "kind": kind,
        "profile": profile,
        "source": str(primary),
        "checks": checks,
        "summary": summary,
        "status": overall,
        "engine_import": "NOT_TESTED",
        "validation": validation["summary"],
    }
    if dry_run:
        return plan
    if overall == "FAIL":
        raise ExportError("export blocked by a failed budget check: " + "; ".join(item["detail"] for item in checks if item["status"] == "FAIL"))

    out_dir = asset.path("exports", target)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    if kind == "mesh":
        target_name = f"{asset.id}{primary.suffix.lower()}"
        mesh_target = out_dir / target_name
        shutil.copy2(primary, mesh_target)
        files.append({
            "path": mesh_target.name,
            "sha256": sha256_file(mesh_target),
            "bytes": mesh_target.stat().st_size,
        })
    texture_dir = out_dir / "textures"
    for item in image_items:
        source = asset.resolve_artifact(item["path"])
        texture_dir.mkdir(exist_ok=True)
        copy = texture_dir / source.name
        shutil.copy2(source, copy)
        files.append({"path": copy.relative_to(out_dir).as_posix(), "sha256": sha256_file(copy), "bytes": copy.stat().st_size})

    record = {
        "schema": 1,
        "target": target,
        "title": profile["title"],
        "asset": asset.id,
        "kind": kind,
        "created": now_iso(),
        "status": overall,
        "checks": checks,
        "files": files,
        "engine_import": "NOT_TESTED",
    }
    write_json(out_dir / "export.json", record)
    write_text(out_dir / "IMPORT.md", _import_notes(profile, record))
    asset.add_export({"target": target, "path": out_dir.relative_to(project.root).as_posix(), "created": record["created"], "status": overall})
    return {**plan, "out_dir": str(out_dir), "files": files}


NAMESPACE = __import__("re").compile(r"^[a-z0-9_.-]{1,64}$")


def _resource(value: str) -> str:
    """Minecraft resource locations allow only lowercase a-z, 0-9, _ . -"""
    return re.sub(r"[^a-z0-9_.-]+", "_", value.lower()).strip("_.") or "sound"


def _event_name(stem: str) -> str:
    """greet1, greet2 -> greet: numbered takes of one line become variants
    of one sound event, which the game picks between at random."""
    base = re.sub(r"[_-]?\d+$", "", stem.lower())
    return re.sub(r"[^a-z0-9_.]", "_", base or stem.lower())


def _export_audio(project: Project, asset: Asset, profile: dict, validation: dict, dry_run: bool, namespace: str) -> dict:
    rules = profile.get("audio") or {}
    allowed = rules.get("formats") or sorted(audio.FORMATS)
    ffmpeg = providers.get("ffmpeg", project).get("path")
    ffprobe = audio.ffprobe_for(ffmpeg) if ffmpeg else None
    sources = [asset.resolve_artifact(item["path"]) for item in _audio_artifacts(asset)]
    kinds = {item.get("file"): item.get("kind") for item in _audio_settings(asset).get("items", [])}
    lengths: dict[str, float] = {}
    checks = []
    for path in sources:
        fmt = path.suffix.lower().lstrip(".")
        checks.append({"artifact": path.name, "id": "FORMAT-003", "status": "PASS" if fmt in allowed else "FAIL",
                       "detail": f".{fmt}" + ("" if fmt in allowed else f" is not accepted; {profile['title']} takes {', '.join('.' + f for f in allowed)} (re-run with --set format={allowed[0]})")})
        info = audio.probe(ffprobe, path) if ffprobe else {}
        lengths[path.name] = info.get("seconds") or 0.0
        if rules.get("max_seconds"):
            seconds = info.get("seconds")
            checks.append({"artifact": path.name, "id": "BUDGET-AUDIO_SECONDS", "status": "NOT_TESTED" if seconds is None else "PASS" if seconds <= rules["max_seconds"] else "FAIL",
                           "detail": f"{seconds} s / limit {rules['max_seconds']} s"})
        if rules.get("max_bytes"):
            size = path.stat().st_size
            checks.append({"artifact": path.name, "id": "BUDGET-AUDIO_BYTES", "status": "PASS" if size <= rules["max_bytes"] else "FAIL",
                           "detail": f"{size} / limit {rules['max_bytes']} bytes"})
        if rules.get("max_sample_rate") and info.get("sample_rate"):
            checks.append({"artifact": path.name, "id": "BUDGET-SAMPLE_RATE", "status": "PASS" if info["sample_rate"] <= rules["max_sample_rate"] else "FAIL",
                           "detail": f"{info['sample_rate']} Hz / limit {rules['max_sample_rate']} Hz"})
        if rules.get("positional_mono") and info.get("channels"):
            if kinds.get(path.name) == "music":
                checks.append({"artifact": path.name, "id": "AUDIO-POSITIONAL", "status": "PASS",
                               "detail": f"music, {info['channels']} ch: played without a position, so stereo is kept"})
            else:
                checks.append({"artifact": path.name, "id": "AUDIO-POSITIONAL", "status": "PASS" if info["channels"] == 1 else "WARNING",
                               "detail": "mono: plays from its position in the world" if info["channels"] == 1 else "stereo: the game plays it without distance falloff"})
    ns = namespace.strip().lower()
    if profile["id"] == "minecraft":
        if not ns:
            ns = "modid"
            checks.append({"id": "NAMESPACE", "status": "WARNING", "detail": "no --namespace given; sounds.json uses 'modid', replace it with your mod or pack namespace"})
        elif not NAMESPACE.match(ns):
            raise ExportError("namespace must be lowercase letters, digits, '_', '-' or '.'")
    checks.append({"id": "ENGINE-IMPORT", "status": "NOT_TESTED", "detail": f"{profile['title']} was not launched; this is packaging and structural validation only"})
    summary = {status: 0 for status in ("PASS", "WARNING", "FAIL", "NOT_TESTED")}
    for item in checks:
        summary[item["status"]] += 1
    overall = "FAIL" if summary["FAIL"] else ("WARNING" if summary["WARNING"] else "PASS")
    plan = {"target": profile["id"], "asset": asset.id, "kind": "audio", "profile": profile, "source": [str(p) for p in sources],
            "checks": checks, "summary": summary, "status": overall, "engine_import": "NOT_TESTED", "validation": validation["summary"]}
    if dry_run:
        return plan
    if overall == "FAIL":
        raise ExportError("export blocked: " + "; ".join(item["detail"] for item in checks if item["status"] == "FAIL"))
    out_dir = asset.path("exports", profile["id"])
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    files = []
    if profile["id"] == "minecraft":
        # The asset's name, not its timestamped id: ids carry an uppercase T,
        # which a resource location rejects.
        group = _resource(str(asset.manifest.get("name") or asset.id))
        sound_dir = out_dir / "assets" / ns / "sounds" / group
        events: dict[str, list] = {}
        for path in sources:
            stem = _resource(path.stem)
            copy = sound_dir / f"{stem}{path.suffix.lower()}"
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, copy)
            files.append({"path": copy.relative_to(out_dir).as_posix(), "sha256": sha256_file(copy), "bytes": copy.stat().st_size})
            entry = {"name": f"{ns}:{group}/{stem}"}
            # Minecraft recommends streaming anything longer than a few
            # seconds so it is not loaded into memory whole.
            if kinds.get(path.name) == "music" or lengths.get(path.name, 0.0) > 10.0:
                entry["stream"] = True
            events.setdefault(f"{group}.{_event_name(stem)}", []).append(entry)
        sounds_json = out_dir / "assets" / ns / "sounds.json"
        write_json(sounds_json, {event: {"sounds": variants, "subtitle": f"subtitles.{ns}.{event}"} for event, variants in sorted(events.items())})
        files.append({"path": sounds_json.relative_to(out_dir).as_posix(), "sha256": sha256_file(sounds_json), "bytes": sounds_json.stat().st_size})
    else:
        for path in sources:
            copy = out_dir / "sounds" / path.name
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, copy)
            files.append({"path": copy.relative_to(out_dir).as_posix(), "sha256": sha256_file(copy), "bytes": copy.stat().st_size})
    record = {"schema": 1, "target": profile["id"], "title": profile["title"], "asset": asset.id, "kind": "audio",
              "namespace": ns or None, "created": now_iso(), "status": overall, "checks": checks, "files": files, "engine_import": "NOT_TESTED"}
    write_json(out_dir / "export.json", record)
    write_text(out_dir / "IMPORT.md", _import_notes(profile, record))
    asset.add_export({"target": profile["id"], "path": out_dir.relative_to(project.root).as_posix(), "created": record["created"], "status": overall})
    return {**plan, "out_dir": str(out_dir), "files": files}


def _import_notes(profile: dict, record: dict) -> str:
    lines = [
        f"# {profile['title']} import",
        "",
        f"Asset: `{record['asset']}`",
        f"Package status: **{record['status']}**",
        "",
        "## Files",
        "",
    ]
    for item in record["files"]:
        lines.append(f"- `{item['path']}`")
    lines += ["", "## Steps", ""]
    if record.get("kind") == "audio":
        if profile["id"] == "minecraft":
            ns = record.get("namespace") or "modid"
            lines += [
                f"1. Copy `assets/` into your resource pack, or merge it into `src/main/resources/assets/` of the mod whose namespace is `{ns}`.",
                f"2. If `assets/{ns}/sounds.json` already exists, merge the events instead of replacing the file.",
                f"3. Register each event in `sounds.json` (for example `{ns}:<event>`) as a SoundEvent in code, or play it with `/playsound {ns}:<event> master @s`.",
                "4. Add the subtitle keys to your language file; mono files play from their position, stereo ones do not fade with distance.",
            ]
        elif profile["id"] == "roblox":
            lines += [
                "1. Open the Asset Manager in Roblox Studio (or the Creator Dashboard) and import the files in `sounds/`.",
                "2. Each upload becomes an audio asset; put its ID in a Sound or AudioPlayer.",
                "3. Uploads go through Roblox moderation before they play for others.",
            ]
        elif profile["id"] == "godot":
            lines += [
                "1. Copy `sounds/` into the Godot project and let the editor import it.",
                "2. Godot suggests WAV for short repeated effects and Ogg Vorbis for music, speech and long effects.",
                "3. Set loop points in the import dock for anything that loops.",
            ]
        else:
            lines += ["1. Use the files in `sounds/` in any engine or audio tool."]
    elif record.get("kind") == "texture":
        if profile["id"] == "roblox":
            lines += [
                "1. Open the Roblox Creator Dashboard or Studio's Asset Manager.",
                "2. Upload each PNG in `textures/` as an image asset.",
                "3. Apply the image to a material or decal; no mesh is included in this package.",
            ]
        elif profile["id"] == "godot":
            lines += [
                "1. Copy the PNG files into the Godot project.",
                "2. Let the editor import them as textures.",
                "3. Assign them to a material; no `.glb` is included in this package.",
            ]
        else:
            lines += [
                "1. Load the PNG in an image viewer or material authoring tool.",
                "2. ORM maps are linear data, not sRGB color; base color stays separate.",
            ]
    elif profile["id"] == "roblox":
        lines += [
            "1. Open Roblox Studio and choose **File > Import**.",
            "2. Select the `.glb` file in this folder.",
            "3. Check scale and pivot in the import preview before confirming.",
        ]
    elif profile["id"] == "godot":
        lines += [
            "1. Copy the `.glb` into the Godot project.",
            "2. Let the editor finish importing, then open the generated scene.",
            "3. Check scale, materials and lightmap UVs in the editor.",
        ]
    else:
        lines += ["1. Load the `.glb` in any glTF 2.0 viewer or engine importer.", "2. Check scale and materials."]
    lines += [
        "",
        "## Evidence boundary",
        "",
        profile.get("notes", ""),
        "",
        "This package passed structural checks and any configured budgets. "
        "No editor or engine import was executed, so visual quality, pivots, "
        "scale, materials and runtime behavior remain **NOT_TESTED**.",
        "",
    ]
    return "\n".join(lines)
