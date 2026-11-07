"""Recipe loading and parameter validation.

Recipes are declarative JSON. They may only name step kinds implemented in
`runner.py`; a recipe can never introduce shell commands or arbitrary code.
"""

from __future__ import annotations

import re
from pathlib import Path

from .util import read_json, safe_name

STEP_NAMES = {
    "image.inspect",
    "image.convert",
    "image.thumbnail",
    "glb.inspect",
    "glb.validate",
    "glb.optimize",
    "glb.compare",
    "blender.sample",
    "comfykit.detect",
    "comfykit.generate",
    "comfykit.import",
    "img2threejs.probe",
    "asset.record",
}

RECIPE_ID = re.compile(r"^[a-z][a-z0-9-]{1,48}$")


class RecipeError(ValueError):
    pass


def builtin_dir() -> Path:
    return Path(__file__).resolve().parent / "data" / "recipes"


def _validate(recipe: dict, source: str) -> dict:
    if not isinstance(recipe, dict) or recipe.get("schema") != 1:
        raise RecipeError(f"{source}: schema must be 1")
    rid = recipe.get("id")
    if not isinstance(rid, str) or not RECIPE_ID.match(rid):
        raise RecipeError(f"{source}: invalid id")
    if not recipe.get("title"):
        raise RecipeError(f"{source}: title is required")
    steps = recipe.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RecipeError(f"{source}: steps must be a non-empty list")
    unknown = [step for step in steps if step not in STEP_NAMES]
    if unknown:
        raise RecipeError(f"{source}: unknown step(s): {', '.join(unknown)}")
    parameters = recipe.get("params") or {}
    if not isinstance(parameters, dict):
        raise RecipeError(f"{source}: params must be an object")
    for name, spec in parameters.items():
        if not isinstance(spec, dict) or spec.get("type") not in ("string", "integer", "boolean"):
            raise RecipeError(f"{source}: param {name!r} has unsupported type")
        if spec["type"] == "integer" and not isinstance(spec.get("default", 0), int):
            raise RecipeError(f"{source}: integer param {name!r} needs an integer default")
        choices = spec.get("choices")
        if choices is not None and not isinstance(choices, list):
            raise RecipeError(f"{source}: param {name!r} choices must be a list")
    recipe.setdefault("input", {})
    recipe.setdefault("params", {})
    return recipe


def load_all(project=None) -> dict[str, dict]:
    recipes: dict[str, dict] = {}
    folders = [builtin_dir()]
    if project is not None:
        folders.append(project.root / "recipes")
    for folder in folders:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.json")):
            try:
                recipe = _validate(read_json(path), str(path))
            except (OSError, ValueError) as exc:
                raise RecipeError(str(exc)) from exc
            recipes[recipe["id"]] = recipe
    return dict(sorted(recipes.items()))


def get(recipe_id: str, project=None) -> dict:
    recipes = load_all(project)
    if recipe_id not in recipes:
        raise RecipeError(f"unknown recipe {recipe_id!r}; available: {', '.join(recipes) or 'none'}")
    return recipes[recipe_id]


def parse_value(name: str, raw: str, spec: dict):
    kind = spec.get("type")
    if kind == "integer":
        try:
            value = int(raw)
        except ValueError as exc:
            raise RecipeError(f"{name} must be an integer, got {raw!r}") from exc
    elif kind == "boolean":
        value = str(raw).lower() in ("1", "true", "yes", "on")
    else:
        value = raw
    choices = spec.get("choices")
    if choices and value not in choices:
        raise RecipeError(f"{name} must be one of {', '.join(map(str, choices))}")
    return value


def resolve_params(recipe: dict, overrides: dict[str, str] | None = None) -> dict:
    params = {name: spec.get("default") for name, spec in recipe.get("params", {}).items()}
    for name, raw in (overrides or {}).items():
        spec = recipe.get("params", {}).get(name)
        if spec is None:
            raise RecipeError(f"recipe {recipe['id']} has no parameter {name!r}")
        params[name] = parse_value(name, raw, spec)
    for name, spec in recipe.get("params", {}).items():
        if spec.get("required") and params.get(name) in (None, ""):
            raise RecipeError(f"parameter {name!r} is required")
    return params


def asset_name(recipe: dict, inputs: dict[str, Path]) -> str:
    first = next(iter(inputs.values()), None)
    base = first.stem if first else recipe["id"]
    return safe_name(f"{base}-{recipe['id']}", fallback=recipe["id"])
