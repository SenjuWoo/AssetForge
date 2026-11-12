# AssetForge agent runbook

AssetForge turns source art into validated, engine-ready assets. It is a CLI; every command takes `--json`. It owns orchestration and validation. Blender, glTF-Transform, the Khronos validator, comfy-kit and img2threejs stay with their owners and are only detected and called.

## Cold start

```text
assetforge doctor --json          health; a missing optional provider is a WARNING, not a failure
assetforge capabilities --json    what this version does, and which providers are present
assetforge probe PATH --json      what a file or folder is, and the recipe commands that fit
assetforge recipes --json         every recipe with its inputs and parameters
```

Route with `probe` before choosing a recipe. Its `recommend` list holds complete commands.

## The loop

1. `assetforge init <folder>` once. All writes go under that project.
2. `assetforge run <recipe> --input <path> [--set key=value] --json`. Add `--dry-run` to see steps and missing providers first.
3. `assetforge validate <asset> --json`, then `assetforge export <asset> --target roblox|godot|generic --dry-run --json`.
4. On a failure read `assetforge status --last --json`: the failed step carries the tool's own message.

Exit codes: `0` ok, `2` usage or recipe error, `3` missing project/asset/job, `4` provider unavailable, `5` validation or budget failure, `6` run failure.

## Sources of truth

- Version: `VERSION`; `pyproject.toml`, `src/assetforge/__init__.py` and the top `CHANGELOG.md` entry are checked against it by `tests/test_schemas.py`.
- Recipes: `src/assetforge/data/recipes/*.json`. A recipe may only name steps in `recipes.STEP_NAMES`; the handlers are in `runner.py`.
- Export budgets: `src/assetforge/data/profiles/*.json`. Game-ready caps: `src/assetforge/gameready.py`.
- Check IDs (`GLB-0xx`): `src/assetforge/glb.py`. Contracts: `schemas/`.
- Progress and gaps: `STATE.md`. Ownership: `WORKSPACE_OWNERSHIP.md`.

## Boundaries

- Inputs are copied or read; a source file is never modified. Outputs stay inside the project.
- Recipes cannot run shell strings or arbitrary scripts. External tools are called with argument lists.
- Evidence tiers are separate. Structural validation, official glTF validation, export packaging and engine import are four claims; engine import is always `NOT_TESTED` because no engine is launched. A passing rig check means consistent data, not a rendered deformation.
- Do not report a `WARNING` or `NOT_TESTED` check as passed.

## Changing the code

Add a failing test beside the existing suite first, fix the shared function, then run `python -m unittest discover -s tests`. Tests that need Blender or blender-skills skip when the provider is absent; say which ran.
