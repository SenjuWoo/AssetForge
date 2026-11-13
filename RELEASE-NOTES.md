# AssetForge 0.6.0 — Machines you can take apart

teardown was the last planned candidate on the roadmap's simulation line. It is now a provider: a simulator folder goes in, a single offline page and a film come out, with the same evidence rules as every other recipe.

## Included

- `teardown-build` bundles a teardown simulator into one HTML page that opens from disk.
- `teardown-film` renders that page to MP4, or to a labelled review sheet, in headless Chromium.
- `validate` checks pages (`PAGE-001`: offline, one file) and videos (`VIDEO-001`: a real MP4).
- teardown detection, with the exact `npm install` / `npx playwright install chromium` command when something is missing.
- Everything from 0.5.1: blender-skills v1.3.0 and img2threejs v2.0.1 verified as providers.

## Verified

- Upstream teardown `a91262a` with Node 26, Playwright 1.58.2 and FFmpeg 9.0.2 on Windows: the upstream V8 example built through `teardown-build` and rendered to a short MP4 through `teardown-film`.
- The full AssetForge suite with every provider present on Windows: 157 tests, 2 platform skips.

## Not verified

- How a simulator looks. Frames are rendered, not reviewed: `TEARDOWN-VISUAL` stays `NOT_TESTED`.
- teardown on Linux and macOS (upstream supports them; AssetForge only ran it on Windows).
- Roblox Studio import; rendering and playback inside Godot.
