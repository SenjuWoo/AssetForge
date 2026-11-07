# Release checklist — AssetForge 0.1.0

This is a development release checklist. The repository has not been created and nothing has been pushed or published from this workspace.

## Repository metadata

**Description**

> Standalone, agent-friendly toolkit for AI-assisted 2D/3D asset production, validation and game-engine export.

**Topics**

`ai-agents`, `asset-pipeline`, `blender`, `game-development`, `glb`, `gltf`, `godot`, `img2threejs`, `roblox`, `texture`, `threejs`, `python`

**Release title**

`AssetForge 0.1.0 — standalone asset toolkit (development release)`

## Release notes

AssetForge 0.1.0 is the first standalone development release.

### Included

- Python CLI with stable exit codes, JSON output and project/job manifests.
- Project-owned inputs, relative artifact paths, path-escape rejection and explicit primary artifacts.
- Image inspection, resize/re-encode, thumbnails, PBR ORM packing and bounded sprite atlases.
- GLB inspection, structural validation, optional Khronos validation and conservative glTF-Transform optimization.
- Mesh and texture-only packaging for generic, Godot and Roblox profiles. Engine import remains `NOT_TESTED`.
- Optional adapters for comfy-kit texture generation, img2threejs probe/codegen and Blender.
- Windows installer with staged rollback, updater and local launchers.
- Tests, schema contracts and Windows/Linux CI.

### Verified boundaries

- img2threejs TypeScript generation is verified. Compilation, rendering, visual fidelity and game-ready conversion are not.
- Blender execution, Teardown, Graphite, AI 3D generation, rigging, MCP and real engine import are not verified.
- comfy-kit generation is verified against a running installation; model installation and ownership stay with comfy-kit.

### Requirements

- Python 3.10 or newer; Python 3.12–3.14 is exercised in CI.
- Pillow is optional but recommended for image recipes.
- All external tools and model weights are optional and independently installed.

## Pre-publication checklist

- [ ] Working tree is clean; `VERSION`, `pyproject.toml`, `__init__.py` and `CHANGELOG.md` agree on `0.1.0`.
- [ ] Full local suite passes with the Windows symlink test skipped or passed.
- [ ] Clean install from the final committed source passes.
- [ ] Wheel builds and contains recipes, profiles and the glTF validator bridge.
- [ ] README links resolve; third-party notices and MIT license are present.
- [ ] No machine paths, credentials, local `.tools` or generated assets are tracked.
- [ ] Hosted CI is green on the exact commit.
- [ ] Tag and release are created only after CI succeeds.

## Exact publication steps (operator-run)

```bash
# 1. Create the public repository and push the current main branch.
gh repo create SenjuWoo/AssetForge --public --source . --remote origin --description "Standalone, agent-friendly toolkit for AI-assisted 2D/3D asset production, validation and game-engine export."
git push -u origin main

# 2. Wait for CI on that exact commit.
gh run list --repo SenjuWoo/AssetForge --branch main
gh run watch <run-id> --repo SenjuWoo/AssetForge

# 3. Apply topics and confirm the repository state.
gh repo edit SenjuWoo/AssetForge --add-topic ai-agents,asset-pipeline,blender,game-development,glb,gltf,godot,img2threejs,roblox,texture,threejs,python

# 4. Tag, build the runtime archive, then publish only after CI is green.
git tag -a v0.1.0 -m "AssetForge 0.1.0"
git push origin v0.1.0
git archive --format=zip --prefix=AssetForge-0.1.0/ -o AssetForge-0.1.0.zip v0.1.0 \
  VERSION CHANGELOG.md LICENSE README.md ROADMAP.md RELEASE-NOTES.md pyproject.toml \
  START-HERE.bat Install.ps1 Update.ps1 assetforge.cmd assetforge src schemas docs examples integration
gh release create v0.1.0 --repo SenjuWoo/AssetForge --title "AssetForge 0.1.0 — standalone asset toolkit (development release)" --notes-file RELEASE-NOTES.md AssetForge-0.1.0.zip
```

Do not claim publication until the repository, hosted CI and release exist. The optional Ultimate AI Starter Bundle companion entry is a separate follow-up; it is not required for the standalone release.
