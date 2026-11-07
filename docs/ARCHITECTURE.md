# Architecture

AssetForge is a small orchestration core with optional adapters. The core must start, inspect configuration and pass its tests without Blender, Node, CUDA, ComfyUI or network access.

## Layers

| Layer | Module | Responsibility |
| --- | --- | --- |
| CLI | `src/assetforge/cli.py` | Argument parsing, stable exit codes, human/JSON output. No business logic beyond validation and routing. |
| Projects | `src/assetforge/store.py` | Project records, asset manifests, job records, relative-path resolution. |
| Recipes | `src/assetforge/recipes.py` | Loads declarative JSON recipes and resolves typed parameters. Recipes may only name implemented steps. |
| Runner | `src/assetforge/runner.py` | Executes steps against project-owned inputs, records evidence, finalizes every job. |
| Container | `src/assetforge/glb.py` | GLB parsing, statistics, structural checks. No third-party dependency. |
| Images | `src/assetforge/images.py` | Pillow operations with a clear error when Pillow is absent. |
| Providers | `src/assetforge/providers.py` | Read-only detection of external tools and owner folders. |
| Adapters | `src/assetforge/adapters.py` | Argument-list construction and output verification for Blender, comfy-kit and img2threejs. |
| Validation | `src/assetforge/official.py`, `src/assetforge/exporters.py` | Optional Khronos validation and export packaging. |
| Schemas | `schemas/*.json` | Versioned public contracts. |

## Data flow

```text
CLI input
  -> recipe resolution and typed parameters
  -> project.create_asset()
  -> inputs copied into assets/<id>/inputs/
  -> Job.create() with original source provenance
  -> step handlers use project-owned copies
  -> artifacts recorded with project-relative paths
  -> manifest primary artifact selected explicitly
  -> validate/export consume only resolved artifact paths
```

## Manifest contract

`asset.json` schema version 1 keeps:

- identity: `id`, `name`, `status` (`INCOMPLETE`, `COMPLETE`, `FAILED`), timestamps;
- `source`: recipe id and resolved parameters;
- `inputs`: copied paths, kind, size and SHA-256;
- `artifacts`: relative path, role, media type, size and SHA-256;
- `primary`: the declared deliverable, for example `{"mesh": "assets/.../outputs/model-optimized.glb"}`;
- `exports`: target, output folder, status and timestamp;
- `validation`: flattened checks;
- `provenance`: tool versions and seed;
- `license`: user-supplied by default.

No binary payload is embedded in JSON. Original input locations are recorded only in the job's `sources` object, which is local execution history, not the portable asset manifest.

## Path safety

`Asset.resolve_artifact()` accepts only project-relative paths, resolves symlinks, rejects absolute paths, rejects `../` escapes and rejects missing files. Validation records a failed check for a rejected path; export refuses to run with an unresolved primary artifact.

## Job lifecycle

```text
RUNNING -> SUCCEEDED
        -> FAILED
        -> CANCELLED (reserved)
```

Every handler result becomes a step record with `OK`, `FAIL`, `SKIP` and an outcome of `PASS`, `WARNING`, `FAIL` or `NOT_TESTED`.

The runner creates the job before copying inputs. A copy failure is therefore captured as a failed job and marks the asset `FAILED`; it cannot leave an asset with no job or a job stuck in `RUNNING`.

The runner catches:

- `RunFailed` and `ProviderMissing`;
- `StoreError`, `RecipeError`, `ImageError`, `AdapterError`, `GlbError`, `OSError`;
- any other ordinary exception, which is converted to a failed job with the exception type and message.

Subprocess timeouts, non-zero exits and missing output files are adapter errors. A failed step marks the job `FAILED` before the CLI returns. No normal failure leaves a job in `RUNNING`.

## Validation taxonomy

| Result | Meaning |
| --- | --- |
| `PASS` | The check ran and found no defect. |
| `WARNING` | The check ran and found a quality risk. |
| `FAIL` | The check ran and found a blocking defect. |
| `NOT_TESTED` | The check did not run, often because an optional provider is missing or engine import was not performed. |

Structural validation, Khronos conformance and visual/engine approval are separate. A passing file check is never reported as engine compatibility.

## Export contract

The exporter:

1. validates every mesh and image artifact;
2. resolves the manifest's primary mesh, with a deterministic label fallback for older manifests;
3. applies profile budgets (project policy, not engine law);
4. copies the primary GLB and loose textures;
5. writes `export.json` and `IMPORT.md`;
6. records the export in the asset manifest;
7. reports `ENGINE-IMPORT: NOT_TESTED`.

Profiles are JSON files in `src/assetforge/data/profiles/`. Adding an exporter requires a profile, not a new core branch for every engine.

## Extension points

- **New recipe:** JSON file naming only existing steps, plus implementation in `runner.HANDLERS`.
- **New provider:** detection in `providers.py`, an adapter with argument-list execution and output verification, and capability reporting.
- **New exporter:** profile JSON plus, only when needed, target-specific validation.
- **New artifact type:** media-type mapping in `store.py` and a validator.
- **MCP:** planned as a thin layer over the same CLI/service functions, never a second implementation.
