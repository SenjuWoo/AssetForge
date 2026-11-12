# Workspace ownership

- Project root: `.` (this file's directory; one owner shared by every agent).
- Project name: `AssetForge`.
- Active source: `.` — the repository root is the source. No version-stamped source snapshots; Git commits and tags carry releases.
- Versioning: SemVer. `VERSION` and `CHANGELOG.md` are the record; current version is `0.3.1`.
- Repository: intended `https://github.com/SenjuWoo/AssetForge` (public, MIT). The repository has not been created or published from this workspace.
- Publication intent: local and private until the operator explicitly asks to publish. Do not create a remote, push or publish a release from a routine development task.
- Read-only inputs: the Ultimate AI Starter Bundle checkout, the comfy-kit checkout, and the external img2threejs/teardown candidate checkouts. This project reads them for inspection and delegation; it does not write into them.
- State/output: `.assetforge/`, root `assets/`, `.tools/`, `.venv/` and `INSTALLATION.json` are local and git-ignored. Model weights and generated media are never committed.
- Recovery: Git history plus the last green commit/tag; `Install.ps1` stages a new `.venv` and keeps `.venv.prev`; `assetforge doctor` reports provider state.
- Release staging: runtime payload (`src/`, schemas, profiles, installer scripts, docs, VERSION, CHANGELOG, LICENSE) is separate from tests, scratch projects, local tool packages and validation notes.

Read the existing evidence and update the active-source/version fields before substantive edits. Do not create another owner or move files merely to match a template.
