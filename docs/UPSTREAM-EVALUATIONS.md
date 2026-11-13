# Upstream evaluations

Checked against upstream repository metadata on **2026-11-08**; integrated providers and companion tools rechecked on **2026-11-13** (see the last section). Licenses marked *not auto-detected* returned SPDX `NOASSERTION`; their LICENSE files must be reviewed before any redistribution. AssetForge does not vendor upstream source, binaries or model weights.

| Project | License | Status | Decision |
| --- | --- | --- | --- |
| [img2threejs](https://github.com/img2threejs/img2threejs) | Apache-2.0 | v2.0.1, revision `0c0c49b`, tested 2026-11-13 | Optional **technical probe** and **deterministic spec-to-Three.js codegen** adapters. Its core produces procedural Three.js source under an agent workflow; that is not a portable game-ready mesh. Image-to-spec reconstruction and review gates remain agent-driven. |
| [teardown](https://github.com/elvarofficial/teardown) | MIT | head `a91262a` (2026-10-31), no tagged release; tested 2026-11-13 | **Integrated (0.6.0)** as `teardown-build` and `teardown-film`: simulator pages and films, kept separate from engine meshes. Previously planned. |
| [image-js](https://github.com/image-js/image-js) | MIT | Active | Not integrated. Pillow covers the MVP image operations; image-js remains a Node-side option. |
| [Graphite](https://github.com/GraphiteEditor/Graphite) | Apache-2.0 | Alpha, active | **Planned** manual/interchange integration. No verified headless automation contract; no invented CLI. |
| [Blender](https://www.blender.org/) | GPL-2.0-or-later (Blender Foundation) | Optional external | **Integrated and executed** with Blender 5.2.3 LTS and again with 5.3.0 (2026-11-13): background smoke, procedural build, material, QA, export, conversion and game-ready collapse. Runs as an external process; AssetForge does not link or redistribute Blender. |
| [blender-skills](https://github.com/EL4CTEO/blender-skills) | MIT (Copyright (c) 2026 EL4CTEO) | v1.3.0, revision `3e481ad` (earlier v1.2.0 `389f28a`) | **Recommended Blender skills provider.** 28 skills validated, 69 upstream headless tests passed on Blender 5.3.0, catalog/routing, optimization, retopology/UV and QA gate integrated. Never vendored or auto-updated. |
| [glTF-Transform](https://github.com/donmccurdy/glTF-Transform) | MIT | CLI 4.5.1 = npm latest (2026-11-13) | **Integrated** for conservative GLB optimization. |
| [meshoptimizer](https://github.com/zeux/meshoptimizer) | MIT | Active | Used through glTF-Transform; no separate integration. |
| [glTF-Validator](https://github.com/KhronosGroup/glTF-Validator) | Apache-2.0 | npm 2.0.0-dev.3.10 = latest (2026-11-13) | **Integrated** as an optional Khronos conformance check. |
| [Trimesh](https://github.com/mikedh/trimesh) | MIT | Active | Not integrated for the MVP; optional future geometry backend. |
| [sharp](https://github.com/lovell/sharp) | Apache-2.0 | Active | Not integrated; Pillow covers current image work. |
| [xatlas](https://github.com/jpcy/xatlas) | MIT | Stable, low activity | **Planned** UV atlas step. |
| [Manifold](https://github.com/elalish/manifold) | Apache-2.0 | Active | **Planned** boolean/manifold checks. |
| [CadQuery](https://github.com/CadQuery/cadquery) | *not auto-detected* | Active | Deferred; license review required before packaging. |
| [Open3D](https://github.com/isl-org/Open3D) | *not auto-detected* | Active | Deferred; heavyweight for the MVP. |
| [Material Maker](https://github.com/RodZill4/material-maker) | MIT | Active | **Planned** material graph interchange. |
| [ArmorPaint](https://github.com/armory3d/armorpaint) | *not auto-detected* | Active | Deferred; optional external editor. |
| [OpenImageIO](https://github.com/AcademySoftwareFoundation/OpenImageIO) | Apache-2.0 | Active | Not needed for the MVP. |
| [ImageMagick](https://imagemagick.org/) | ImageMagick license, *not auto-detected* | Active | Deferred; Pillow is the current image backend. |
| [Basis Universal](https://github.com/BinomialLLC/basis_universal) | Apache-2.0 | Active | **Planned** texture compression. |
| [Krita](https://krita.org/) | GPL-3.0 | Active | Optional manual editor only. |
| [Inkscape](https://inkscape.org/) | GPL-3.0 | Active (GitHub mirror stale) | Optional manual editor only. |
| [LibreSprite](https://github.com/LibreSprite/LibreSprite) | GPL-2.0 | Active | Optional manual sprite editor. |
| [Aseprite](https://github.com/aseprite/aseprite) | Proprietary EULA / source-available | Active | Never bundled. Users must own a licensed copy. |
| [TripoSR](https://github.com/VAST-AI-Research/TripoSR) | MIT (code; model weights separate) | Active | **Planned** first local image-to-3D candidate. |
| [TRELLIS.2](https://github.com/microsoft/TRELLIS.2) | MIT | Active | **Planned**, but original requirements exceed 16 GB VRAM; not claimed as locally verified. |
| [Hunyuan3D-2](https://github.com/Tencent-Hunyuan/Hunyuan3D-2) | Tencent community license *not auto-detected* | Active | Optional, separately acknowledged; community-license restrictions apply. |
| [Hunyuan3D-2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) | Tencent community license *not auto-detected* | Active | Not an unrestricted dependency. Optional only, with geographic/use restrictions acknowledged. |
| [UniRig](https://github.com/VAST-AI-Research/UniRig) | MIT | Active | **Planned** rigging provider after core rig validation exists. |
| [PyNifly](https://github.com/BadDogSkyrim/PyNifly) | GPL-3.0 | Active | **Planned** Skyrim/Fallout export path through Blender; separate GPL addon. |
| [comfy-kit](https://github.com/SenjuWoo/comfy-kit) | MIT | Active owner | Optional generation/import adapter. AssetForge never owns its models, presets, nodes or configuration. |

## 2026-11-13: audio

| Candidate | Licence | Decision |
| --- | --- | --- |
| Qwen3-TTS 1.7B VoiceDesign + Base (`qwen-tts` 0.1.1) | Apache-2.0 | **Integrated (0.7.0)** as the default voice engine: voice design from text, then cloning for consistent line sets, 10 languages. |
| Dia 1.6B (nari-labs, through transformers) | Apache-2.0 | **Integrated (0.7.0)** for nonverbals and dialogue; takes the Qwen-designed reference voice. |
| Dia2 1B/2B | Apache-2.0 | Not adopted yet: voices vary per generation without a prefix, and its streaming server is still listed as upcoming. Recheck when it ships a stable API. |
| Kokoro-82M | Apache-2.0 | **Integrated (0.7.0)** for fast preset voices. |
| MOSS-SoundEffect v2.0 (OpenMOSS, 1.3B DiT) | Apache-2.0 | **Integrated (0.7.0)** for sound effects; installed at pinned commit `934d682` without upstream's numpy 1.26 and gradio pins. |
| Whisper large-v3-turbo; CLAP (laion/larger_clap_general) | MIT; Apache-2.0 | **Integrated (0.7.0)** as take checks. |
| Chatterbox (Resemble AI) | MIT, outputs watermarked | Not adopted: every output carries the PerTh watermark; Qwen3-TTS covers cloning. |
| MOSS-TTS 8B family | Apache-2.0 | Not adopted: 8B is heavy on one GPU; only the 1.3B sound-effect model is used. |
| Stable Audio Open / Stable Audio 3.0 SFX | Stability AI Community | Not adopted: free only under a revenue threshold. |
| soundbox (desktop app with an MCP server) | MIT app, mixed model licences | Not adopted: unsigned Windows installer, unauthenticated local API, young project. |
| ACE-Step 1.5 | MIT | Planned for music. |

## Licensing notes

- **Model weights are separate from source licenses.** TripoSR, TRELLIS and Hunyuan weights must be reviewed and acknowledged independently.
- **Hunyuan community licenses are not MIT-style.** They remain optional and are never downloaded or redistributed by AssetForge.
- **Aseprite cannot be redistributed.** It is not a dependency.
- **Blender and PyNifly are GPL.** They stay external programs/addons; AssetForge invokes them through process boundaries.
- **Graphite is alpha.** No stable automation contract is assumed.
- **No third-party binary is committed to this repository.** The local `.tools` folder is development-only and git-ignored.

## Candidate checkout status

The external `img2threejs` and `teardown` candidate snapshots were compared with upstream on 2026-11-13: both matched (img2threejs = v2.0.1, teardown = `a91262a`) and were replaced by the Git clones AssetForge now uses as providers. Before that they were inspected, not copied. Their capabilities and limits are documented above. They are not vendored, modified or deleted by AssetForge. The img2threejs probe and deterministic code generator are wired through external-path adapters; image-to-spec reconstruction remains agent-driven. Teardown and Graphite remain planned.

## 2026-11-13 recheck: providers and new companion tools

Integrated providers were compared with their upstream releases and each update was run before it was accepted:

| Provider | Was | Now | Evidence | Decision |
| --- | --- | --- | --- | --- |
| blender-skills | v1.2.0 `389f28a` | **v1.3.0** `3e481ad` | `validate_skills.py` OK; 69/69 upstream headless tests on Blender 5.3.0 and on 5.2.4 LTS; AssetForge pipeline, QA and runner tests pass | **Updated.** Blender 5.3 notes and KTX2 export guidance; the scripts AssetForge runs only changed in their docstrings. |
| img2threejs | v1.5.1 era | **v2.0.1** `0c0c49b` | upstream 1,416 tests, no assertion failures (3 Windows symlink-privilege fixture errors, 64 skipped); `img2threejs-probe` and `img2threejs-codegen` recipes succeed | **Updated.** Probe and generator keep the command lines the adapters call. |
| glTF-Transform CLI | 4.5.1 | 4.5.1 | npm latest | No change. |
| gltf-validator | 2.0.0-dev.3.10 | 2.0.0-dev.3.10 | npm latest | No change. |
| teardown | candidate snapshot | `a91262a` (no tagged release) | `npm ci`; upstream examples built and filmed through AssetForge; review sheet inspected | **Integrated in 0.6.0** as `teardown-build` / `teardown-film`. |
| GitHub Actions | checkout v4, setup-python v5 | checkout v7, setup-python v7 | release notes reviewed; the removed `pip-install` input is not used | **Updated**; Dependabot now proposes Actions updates monthly. |

Companion tools reviewed for AssetForge. Upstream versions were read from each project's own repository on 2026-11-13. None is vendored.

| Project | License | Version checked | What it is | Decision for AssetForge |
| --- | --- | --- | --- | --- |
| [CLI-Anything](https://github.com/HKUDS/CLI-Anything) | Apache-2.0 | v0.4.0 (head 2026-09-22) | Agent CLIs per desktop app (Blender, GIMP, Audacity, ComfyUI, ...) | **Not integrated.** AssetForge already calls Blender, ImageMagick and FFmpeg directly with argument lists; a harness would add a second path to the same programs. Agents may use a harness for apps AssetForge does not cover. |
| [MCP for Unity](https://github.com/CoplayDev/unity-mcp) | MIT | v10.3.0 | Live Unity Editor control over MCP | **Documented.** Candidate for a future Unity import check alongside `engine-check` (Godot). AssetForge has no Unity export target yet, so nothing is wired. |
| [AI Game Developer / Unity-MCP](https://github.com/IvanMurzak/Unity-MCP) | Apache-2.0 | server 9.3.2, CLI release 1.11.1 | One MCP server for Unity, Unreal and Godot editors | **Documented.** Same future role as above; editor sessions are live state, which AssetForge's headless recipes deliberately avoid. |
| [awesome-gamedev-agent-skills](https://github.com/gamedev-skills/awesome-gamedev-agent-skills) | Apache-2.0 | v2.0.0 | 79 engine skills for 12 engines | **Documented companion.** Engine-side skills; AssetForge hands them validated assets and does not vendor skills. |
| [OBS MCP](https://github.com/Tom-R-Main/OBS-MCP) | MIT (package) | 1.1.1 | OBS Studio scene and recording control | **Not integrated.** Turntable and preview video come from rendered frames through FFmpeg; screen capture adds nothing to an asset. |
| [context-mode](https://github.com/mksglu/context-mode) | Elastic-2.0 (package) | v2.1.10 | Agent context-window management plugin | **Out of scope.** Agent tooling, not asset production. |
| [REA](https://github.com/morluto/rea) | MIT | 6.9.0 | Reverse-engineering MCP | **Out of scope.** |
| Blender portable 5.2.3 | GPL-2.0-or-later | 5.2.3 | A second Blender | **Not needed.** Detection prefers the installed Blender; blender-skills v1.3.0 recommends 5.3. |

Not reviewed as asset tooling: general web build tools (Nx, Turborepo, Vite, webpack), a gallery of code-animated video prompts, and ClibDT 6.0.0 (a GPL-3.0 Skyrim mod-development toolkit; no public repository was found to compare its version against).
