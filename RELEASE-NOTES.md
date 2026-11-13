# AssetForge 0.4.1 — Blender is found where it is

A maintenance release for one failure: Blender was installed and AssetForge, or the agent driving it, could not find it.

## Included

- Blender detection reads every Steam library, the Windows uninstall registry, the Blender Foundation folders and a portable copy under a declared tool root. `BLENDER_EXE` still selects one explicitly.
- A `blender.bat` that starts a Hermes profile named `blender` is skipped instead of being started as if it were Blender.
- A missing Blender is reported with the places that were searched and the variable that fixes it.

## Unchanged

Everything in 0.4.0: `assetforge probe`, `mesh-convert`, rig, material and texture validation, embedded texture budgets.

## Verified

- The full suite on Windows with Blender 5.3 installed through Steam and not on PATH.
- `assetforge doctor --json` reports Blender available at its Steam path with no `BLENDER_EXE` set.

## Not verified

- Linux and macOS discovery beyond `BLENDER_EXE` and PATH; the registry and Steam library lookups are Windows-only.
- Engine import of any exported asset. Validation and export are file checks.
