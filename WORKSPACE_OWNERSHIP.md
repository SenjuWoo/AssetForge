# Workspace ownership

- Project root: `.` (this file's directory; one owner shared by every agent).
- Project name: `AssetForge`.
- Active source: `.` — the repository root is the source. No version-stamped source snapshots; Git commits and tags carry releases.
- Versioning: SemVer. `VERSION` and `CHANGELOG.md` are the record; current version is `0.8.0`.
- Repository: `https://github.com/SenjuWoo/AssetForge` (public, MIT), remote `origin`, default branch `main`. Releases are GitHub releases with an `AssetForge-<version>.zip` asset built from the tag.
- Publication: maintained repository. Push and release only after the full local suite passes and hosted CI is green on the exact commit.
- Read-only inputs: the Ultimate AI Starter Bundle checkout, the comfy-kit checkout, and the blender-skills, img2threejs and teardown provider clones. This project reads them for inspection and delegation; it does not write into them.
- Runtime state outside the repository: `~/.assetforge/audio` (audio runtimes and model cache, created by `assetforge audio-setup`). It is rebuilt by that command and is never committed.
- State/output: `.assetforge/`, root `assets/`, `.tools/`, `.venv/` and `INSTALLATION.json` are local and git-ignored. Model weights and generated media are never committed.
- Recovery: Git history plus the last green commit/tag; `Install.ps1` stages a new `.venv` and keeps `.venv.prev`; `assetforge doctor` reports provider state.
- Release staging: runtime payload (`src/`, schemas, profiles, installer scripts, docs, VERSION, CHANGELOG, LICENSE) is separate from tests, scratch projects, local tool packages and validation notes.

Read the existing evidence and update the active-source/version fields before substantive edits. Do not create another owner or move files merely to match a template.
