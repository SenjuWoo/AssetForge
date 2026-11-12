# Upstream evaluations

Checked against upstream repository metadata on **2026-11-08**. Licenses marked *not auto-detected* returned SPDX `NOASSERTION`; their LICENSE files must be reviewed before any redistribution. AssetForge does not vendor upstream source, binaries or model weights.

| Project | License | Status | Decision |
| --- | --- | --- | --- |
| [img2threejs](https://github.com/img2threejs/img2threejs) | Apache-2.0 | Active, inspected | Optional **technical probe** and **deterministic spec-to-Three.js codegen** adapters. Its core produces procedural Three.js source under an agent workflow; that is not a portable game-ready mesh. Image-to-spec reconstruction and review gates remain agent-driven. |
| [teardown](https://github.com/elvarofficial/teardown) | MIT | Active, inspected | Specialized simulation/presentation module, **planned**. Its offline HTML/video output stays separate from engine mesh export. |
| [image-js](https://github.com/image-js/image-js) | MIT | Active | Not integrated. Pillow covers the MVP image operations; image-js remains a Node-side option. |
| [Graphite](https://github.com/GraphiteEditor/Graphite) | Apache-2.0 | Alpha, active | **Planned** manual/interchange integration. No verified headless automation contract; no invented CLI. |
| [Blender](https://www.blender.org/) | GPL-2.0-or-later (Blender Foundation) | Optional external | **Integrated and executed** with Blender 5.2.3 LTS: background smoke, procedural build, material, QA and export. Runs as an external process; AssetForge does not link or redistribute Blender. |
| [blender-skills](https://github.com/EL4CTEO/blender-skills) | MIT (Copyright (c) 2026 EL4CTEO) | v1.2.0, revision `389f28a` | **Recommended Blender skills provider.** 28 skills validated, 69 upstream headless tests passed, catalog/routing, optimization, retopology/UV and QA gate integrated. Never vendored or auto-updated. |
| [glTF-Transform](https://github.com/donmccurdy/glTF-Transform) | MIT | Active | **Integrated** for conservative GLB optimization. |
| [meshoptimizer](https://github.com/zeux/meshoptimizer) | MIT | Active | Used through glTF-Transform; no separate integration. |
| [glTF-Validator](https://github.com/KhronosGroup/glTF-Validator) | Apache-2.0 | Active | **Integrated** as an optional Khronos conformance check. |
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

## Licensing notes

- **Model weights are separate from source licenses.** TripoSR, TRELLIS and Hunyuan weights must be reviewed and acknowledged independently.
- **Hunyuan community licenses are not MIT-style.** They remain optional and are never downloaded or redistributed by AssetForge.
- **Aseprite cannot be redistributed.** It is not a dependency.
- **Blender and PyNifly are GPL.** They stay external programs/addons; AssetForge invokes them through process boundaries.
- **Graphite is alpha.** No stable automation contract is assumed.
- **No third-party binary is committed to this repository.** The local `.tools` folder is development-only and git-ignored.

## Candidate checkout status

The external `img2threejs` and `teardown` candidate checkouts were inspected, not copied. Their capabilities and limits are documented above. They are not vendored, modified or deleted by AssetForge. The img2threejs probe and deterministic code generator are wired through external-path adapters; image-to-spec reconstruction remains agent-driven. Teardown and Graphite remain planned.
