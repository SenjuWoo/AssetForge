# Release checklist — AssetForge 0.3.1

Public stable release. `v0.3.0` remains unchanged.

## Repository metadata

**Description**

> Standalone, agent-friendly toolkit for AI-assisted 2D/3D asset production, validation and game-engine export.

**Release title**

`AssetForge 0.3.1 — Game-ready mesh cap`

## Pre-publication checklist

- [ ] Working tree is clean; `VERSION`, `pyproject.toml`, `__init__.py` and `CHANGELOG.md` agree on `0.3.1`.
- [ ] Full local suite passes with real Blender: 97 tests, 2 skipped.
- [ ] Full local suite passes without blender-skills: 89 tests, 4 skipped.
- [ ] Showcase GLB inspection/validation passes and the generator reproduces the committed GLB SHA-256.
- [ ] Fresh wheel and source distributions build successfully.
- [ ] README and `docs/PROVIDERS.md` accurately separate discovered skills from exercised skills.
- [ ] No machine paths, credentials, local `.tools` or generated private outputs are tracked.
- [ ] Hosted CI is green on the exact commit.
- [ ] Dependabot and secret-scanning alerts are clear.

## Publication steps

The release is published from the green `main` commit as `v0.3.1`. Build `AssetForge-0.3.1.zip` from the tagged source snapshot with:

```bash
git archive --format=zip --prefix=AssetForge-0.3.1/ -o AssetForge-0.3.1.zip v0.3.1 \
  VERSION CHANGELOG.md LICENSE README.md ROADMAP.md RELEASE-NOTES.md pyproject.toml \
  START-HERE.bat Install.ps1 Update.ps1 assetforge.cmd assetforge src schemas docs examples integration

gh release create v0.3.1 --repo SenjuWoo/AssetForge \
  --title "AssetForge 0.3.1 — Game-ready mesh cap" \
  --notes-file RELEASE-NOTES.md AssetForge-0.3.1.zip
```

Verify the tag resolves to the release commit, download the asset, compare its SHA-256, extract it and run `Install.ps1`, then confirm `assetforge.cmd --version` reports `0.3.1`.
