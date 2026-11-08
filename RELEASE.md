# Release checklist — AssetForge 0.2.0

Development release. The repository already exists; `v0.1.0` remains published and unchanged.

## Repository metadata

**Description**

> Standalone, agent-friendly toolkit for AI-assisted 2D/3D asset production, validation and game-engine export.

**Release title**

`AssetForge 0.2.0 — Blender-skills integration (development preview)`

## Pre-publication checklist

- [ ] Working tree is clean; `VERSION`, `pyproject.toml`, `__init__.py` and `CHANGELOG.md` agree on `0.2.0`.
- [ ] Full local suite passes with real Blender (91 tests, 2 skipped).
- [ ] Clean wheel installation and real pipeline pass.
- [ ] Wheel and source distributions contain the Blender package data.
- [ ] README and `docs/PROVIDERS.md` accurately separate discovered skills from exercised skills.
- [ ] No machine paths, credentials, local `.tools` or generated assets are tracked.
- [ ] Hosted CI is green on the exact commit.
- [ ] Dependabot and secret-scanning alerts are clear.

## Exact publication steps (operator-run)

```bash
# 1. Confirm the release identity.
git rev-parse HEAD
cat VERSION

# 2. Tag only the green commit and push the tag.
git tag -a v0.2.0 -m "AssetForge 0.2.0"
git push origin v0.2.0

# 3. Build the runtime archive from the tag.
git archive --format=zip --prefix=AssetForge-0.2.0/ -o AssetForge-0.2.0.zip v0.2.0 \
  VERSION CHANGELOG.md LICENSE README.md ROADMAP.md RELEASE-NOTES.md pyproject.toml \
  START-HERE.bat Install.ps1 Update.ps1 assetforge.cmd assetforge src schemas docs examples integration

# 4. Publish as a development preview.
gh release create v0.2.0 --repo SenjuWoo/AssetForge \
  --title "AssetForge 0.2.0 — Blender-skills integration (development preview)" \
  --notes-file RELEASE-NOTES.md --prerelease AssetForge-0.2.0.zip
```

Verify the tag resolves to the release commit, download the asset, compare its SHA-256, extract it and run `Install.ps1`, then confirm `assetforge.cmd --version` reports `0.2.0`.
