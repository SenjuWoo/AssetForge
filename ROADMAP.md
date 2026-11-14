# Roadmap

AssetForge is built around one priority: a genuine reference-image → 3D → engine workflow. Everything else supports that path.

## Priority 0 — release gate

- Keep the standalone CLI, installer, schemas and tests green.
- Publish `0.1.0` only after the exact commit passes local checks and hosted CI.
- Keep every optional provider optional and independently installed.

## Priority 1 — reference image to 3D to engine

1. **img2threejs image-to-spec**: run the upstream intake, texture and material analysis, then produce a reviewed ObjectSculptSpec. Status: planned; agent review gates are required.
2. **Spec-to-Three.js codegen**: implemented and verified. The TypeScript remains an editable intermediate.
3. **Render/visual review**: compile and render the generated factory and capture comparison evidence. Status: planned.
4. **GLB conversion**: convert the reviewed procedural result into a portable mesh, validate it and export. Status: planned; feature loss must be reported, not hidden.
5. **Real engine import**: test the exported package in Roblox Studio and Godot, and record evidence. Status: Godot import and load is automated by `engine-check` (0.5.0); rendering in Godot and any Roblox Studio import are not tested.

## Priority 2 — Blender integration

**Done:** real Blender 5.2.3 detection, headless execution, `blender-skills` catalog/routing, procedural build, PBR material, mandatory `blender-asset-qa` gate, random/wire review evidence, GLB export, optimization and validation. Tested upstream revision `389f28a`; 69 upstream tests and the AssetForge end-to-end pipeline passed.

- Add controlled processing for imported `.blend` scenes (the QA-only recipe is available now).
- Expand skill routing into repeatable recipes for rigging, animation and baking after the first pipeline is stable.
- Keep Blender MCP optional; the verified path is headless.

## Priority 3 — texture and material depth

- **comfy-kit is the recommended free local texture generator.** It owns SwarmUI/ComfyUI, models and presets; AssetForge delegates generation and imports only the result.
- Add Material Maker interchange for procedural PBR graphs where a stable contract exists.
- Add texture compression and channel validation only when an official backend is verified.

## Priority 4 — simulation, editing and animation

- **Done (0.6.0):** Teardown simulator pages and films (`teardown-build`, `teardown-film`), separate from game-engine meshes.
- **Done (0.7.0):** Audio. Voice lines (Qwen3-TTS voice design and cloning, Dia nonverbals, Kokoro), sound effects (MOSS-SoundEffect v2), finishing and level checks, and Minecraft sound export.
- **Done (0.8.0):** Music. `audio-music` renders ACE-Step 1.5 through comfy-forge.
- Loop points for game music: planned.
- Graphite: documented manual/interchange workflow; no invented headless CLI.
- Rigging validation and UniRig after the core mesh path is stable.

## Priority 5 — distribution and agent surface

- Additional export profiles (Unity, Unreal, web, Skyrim) through the exporter contract.
- Optional MCP server over the same service layer.
- Optional remote GPU execution; never a core requirement.

## Explicitly not done

- img2threejs image-to-spec reconstruction and visual approval.
- Graphite automation and Roblox/Unity engine imports.
- AI 3D generation, rigging, MCP and batch/remote GPU support.

Those items stay marked as planned or unverified until executed with recorded evidence.
