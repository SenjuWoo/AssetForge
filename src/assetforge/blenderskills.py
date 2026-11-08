"""Read-only integration with EL4CTEO/blender-skills.

blender-skills is an optional owner: it provides the Blender workflows and
scripts, while AssetForge detects it, exposes its catalog to agents and
delegates controlled headless runs. Nothing here installs or updates upstream.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .util import first_line, run

CORE = "blender-core"
QA = "blender-asset-qa"

# Route names map AssetForge work to the skill that owns it. The values are
# ordered: the first available skill is the primary recommendation.
ROUTES = {
    "core": ["blender-core"],
    "scene": ["blender-scene-setup"],
    "modeling": ["blender-hardsurface-modeling", "blender-geometry-nodes", "blender-environment-kits"],
    "sculpting": ["blender-sculpting"],
    "uv": ["blender-retopology-uv"],
    "texturing": ["blender-texturing", "blender-pbr-materials"],
    "materials": ["blender-pbr-materials", "blender-texturing"],
    "baking": ["blender-texture-baking"],
    "rigging": ["blender-character-rigging", "blender-facial-shapekeys"],
    "animation": ["blender-animation"],
    "optimization": ["blender-game-optimization"],
    "export": ["blender-export-pipelines"],
    "qa": ["blender-asset-qa"],
    "rendering": ["blender-rendering", "blender-lighting-lookdev"],
    "lighting": ["blender-lighting-lookdev", "blender-time-of-day"],
    "simulation": ["blender-simulation"],
    "clothing": ["blender-clothing"],
    "hair": ["blender-hair-grooming"],
    "facial": ["blender-facial-shapekeys"],
    "npr": ["blender-stylized-npr"],
    "weather": ["blender-weather-fx", "blender-time-of-day"],
    "video": ["blender-video-editing"],
    "addon": ["blender-addon-development"],
    "pipeline": ["blender-pipeline-automation", "blender-workflow-recipes"],
    "recipes": ["blender-workflow-recipes"],
}


def _layout(path: Path) -> tuple[Path, Path] | None:
    """Accept either a checkout (skills/<name>) or an installed skills folder."""
    path = Path(path).resolve()
    for base in (path, path / "skills"):
        if (base / CORE / "SKILL.md").is_file() and (base / QA / "SKILL.md").is_file():
            return path, base
    return None


def locate(project=None) -> tuple[tuple[Path, Path] | None, str]:
    home = Path.home()
    explicit = os.environ.get("BLENDER_SKILLS_ROOT")
    if explicit:
        found = _layout(Path(explicit).expanduser())
        if found:
            return found, ""
        return None, f"BLENDER_SKILLS_ROOT does not contain {CORE}/SKILL.md: {explicit}"

    configured = None
    if project is not None:
        configured = (project.data.get("integrations") or {}).get("blender_skills")
        if configured:
            candidate = Path(str(configured)).expanduser()
            if not candidate.is_absolute():
                candidate = project.root / candidate
            candidate = candidate.resolve()
            found = _layout(candidate)
            if found:
                return found, ""
            return None, f"integrations.blender_skills does not contain {CORE}/SKILL.md: {configured}"

    candidates = (
        home / "blender-skills",
        home / ".claude" / "skills",
        home / ".agents" / "skills",
    )
    for candidate in candidates:
        found = _layout(candidate)
        if found:
            return found, ""
    return None, "blender-skills was not found; set BLENDER_SKILLS_ROOT or integrations.blender_skills"


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else text[3:]
    data = {}
    for key in ("name", "description", "license"):
        match = re.search(rf"^{key}:\s*(.+)$", block, re.M)
        if match:
            data[key] = match.group(1).strip().strip('"').strip("'")
    version = re.search(r"^\s+version:\s*[\"']?([^\"'\n]+)", block, re.M)
    if version:
        data["version"] = version.group(1).strip()
    return data


def catalog(skills_dir: Path) -> list[dict]:
    items = []
    for folder in sorted(skills_dir.iterdir()):
        markdown = folder / "SKILL.md"
        if not folder.is_dir() or not markdown.is_file():
            continue
        meta = _frontmatter(markdown)
        scripts = sorted((folder / "scripts").glob("*.py")) if (folder / "scripts").is_dir() else []
        items.append({
            "name": meta.get("name") or folder.name,
            "description": meta.get("description") or "",
            "version": meta.get("version"),
            "license": meta.get("license"),
            "path": str(folder),
            "skill_md": str(markdown),
            "scripts": [str(path) for path in scripts],
        })
    return items


def revision(root: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    result = run(["git", "-C", str(root), "rev-parse", "HEAD"], timeout=15)
    if result["returncode"] == 0:
        return first_line(result["stdout"])
    return None


def route(name: str, skills: list[dict]) -> list[dict]:
    names = ROUTES.get(name, [])
    by_name = {item["name"]: item for item in skills}
    return [by_name[item] for item in names if item in by_name]


def describe(project=None) -> dict:
    found, reason = locate(project)
    if found is None:
        return {
            "id": "blender-skills",
            "title": "blender-skills agent workflows",
            "kind": "skill",
            "available": False,
            "version": None,
            "path": None,
            "reason": reason,
            "capabilities": [f"blender.skill.{name}" for name in ROUTES],
            "details": {"skills": 0, "routes": sorted(ROUTES)},
        }
    root, skills_dir = found
    skills = catalog(skills_dir)
    version = next((item["version"] for item in skills if item["name"] == CORE), None)
    return {
        "id": "blender-skills",
        "title": "blender-skills agent workflows",
        "kind": "skill",
        "available": True,
        "version": version,
        "path": str(root),
        "reason": "",
        "capabilities": [f"blender.skill.{name}" for name in ROUTES],
        "details": {
            "skills": len(skills),
            "skills_dir": str(skills_dir),
            "revision": revision(root),
            "license": "MIT",
            "routes": sorted(ROUTES),
            "catalog": [item["name"] for item in skills],
        },
    }
