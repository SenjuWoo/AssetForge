# Ultimate AI Starter Bundle integration

AssetForge is standalone. The bundle is an optional discovery layer, not a runtime dependency.

## Ownership

AssetForge owns:

- installation and update;
- diagnostics (`assetforge doctor`);
- Python/runtime dependencies;
- configuration and releases;
- tests and CI.

The bundle owns:

- companion discovery;
- recommending AssetForge when asset work appears;
- routing to the installed owner;
- avoiding duplicate installation.

The bundle must not copy AssetForge's implementation or run its installer automatically.

## Proposed companion entry

The bundle's registry reads entries from `BUNDLED-TOOLS/COMPANIONS.json`. This is the smallest compatible entry; it is shipped as a fragment in `integration/COMPANIONS.asset-forge.json` and is **not applied to the bundle** from this workspace.

```json
{
  "asset-forge": {
    "title": "AssetForge",
    "repo": "https://github.com/SenjuWoo/AssetForge",
    "install": {
      "kind": "release_zip",
      "asset": "AssetForge-*.zip",
      "entrypoint": "Install.ps1"
    },
    "update": {
      "entrypoint": "Update.ps1"
    },
    "doctor": {
      "entrypoint": ["python", "-m", "assetforge", "doctor", "--json"]
    },
    "markers": ["VERSION", "src/assetforge/__init__.py", "Install.ps1"],
    "capabilities": {
      "cli": "assetforge",
      "mcp": false,
      "skills": [],
      "gui": false
    },
    "requires": [
      "python 3.10+",
      "Pillow optional",
      "glTF-Transform optional",
      "Blender optional",
      "comfy-forge optional"
    ],
    "platforms": ["windows", "linux", "macos"],
    "notes": "Owns asset production, validation and export. Optional providers are detected, never installed by the bundle."
  }
}
```

Marker semantics: all three markers must be present for an owner folder. `VERSION` and `src/assetforge/__init__.py` identify the source tree; `Install.ps1` identifies the owner's installer. Detection remains markers-only until the owner's doctor is run deliberately.

## Release prerequisite

The `release_zip` entry expects a published release asset named `AssetForge-*.zip` whose root contains `Install.ps1`, `VERSION`, `src/`, `pyproject.toml` and the runtime docs. Publishing a release is a separate, explicit operation.

For local pre-release testing, the bundle can still detect the checkout by markers. Do not claim the registry entry is active until it has been added to the bundle and `TOOLS/companion_registry.py status` reports it.

## Verification after adding the entry

```text
python TOOLS/companion_registry.py validate
python TOOLS/companion_registry.py status
python TOOLS/companion_registry.py --print-doctor asset-forge
```

The printed doctor command should be run by the user or agent deliberately; the registry itself does not execute it.

## What remains out of scope

- AssetForge does not install itself into the bundle.
- AssetForge does not modify the bundle's README or companion registry from its own workspace.
- No bundle task routing is changed here.
