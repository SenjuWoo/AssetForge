# AssetForge 0.3.1 — Game-ready mesh cap

A generated GLB at sculpt density does not ship. `mesh-gameready` imports it in Blender, collapses it, shrinks the textures, and fails the job if the written file is over the triangle cap.

## Included

- Default budget `game`: 20,000 triangles and a 1024 texture. That is the Roblox MeshPart ceiling and the handheld-prop ceiling used here.
- `hero`: 30,000 triangles and a 2048 texture. Close-up only. It is not a Roblox mesh.
- `accessory`: 4,000 triangles and a 1024 texture. A Roblox accessory worn on an avatar.
- A 700,000-triangle sculpt is rejected. This recipe has no 50,000-triangle budget.
- `glb-optimize` still does not simplify. `blender-optimize` and `blender-retopo-uv` still need a `.blend`.
- Guide: `docs/GAME-READY.md`.

## One command

```bat
assetforge.cmd run mesh-gameready --input mesh=model.glb
```

## Verified

- One PBR prop went from 699,878 triangles and 61.5 MB to 17,000 triangles, 21,186 vertices, 6,192,808 bytes, and three 1024 maps.
- Official glTF validator on that file: 0 errors, 0 warnings. No skins or animations, so that check was not applicable.
- Engine import was not run.
- Hosted CI has no Blender, so the Blender pass skips there. It runs in the local suite when Blender is installed.

## Boundaries

- Roblox Studio, Unity, Godot, and Unreal imports were not run.
- The cap is one prop mesh. It does not guess a full-character budget.
- Blender is optional and independently installed.
