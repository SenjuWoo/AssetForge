# AssetForge 0.3.0 — Showcase and whitelisted Blender skill runner

Adds a project-generated showcase for low-poly stylized games and the first whitelisted, reusable runner for upstream Blender skills.

## Included

- `enchanted-fire-sword.glb`: a project-owned low-poly showcase prop for stylized/Roblox-style game work, built entirely in Blender without third-party artwork.
- Reproducible Blender generator for the GLB and preview PNG in `examples/`; CI now inspects the committed GLB.
- Concept exploration for the showcase used comfy-kit / SwarmUI locally. The shipped GLB is procedural Blender geometry and has no dependency on generated reference images.
- `blender-optimize`: whitelisted `blender-game-optimization` operations (`mesh-stats`, `make-lods`) with project-owned outputs.
- `blender-retopo-uv`: whitelisted `blender-retopology-uv` operations (`auto-retopo`, `uv-pack`, `texel-density`) with validation and immutable input `.blend` behavior.
- Generic `blender.skills.run`: documented operations only, with strict arguments and no arbitrary script paths.
- All prior 0.2.0 image, GLB, export, comfy-kit, img2threejs and blender-skills functionality remains available.

## Verified

- Full suite with blender-skills available: **97 tests passed**, 2 skipped, 0 failed.
- Full suite without blender-skills: **89 tests passed**, 4 skipped, 0 failed.
- Showcase GLB SHA-256: `2d4c4635950ba63c7409cce9fbb31a0fdbb6b7441f8a5f92ad30820f369e33db`.
- Showcase GLB: `21,856` triangles, `26,044` vertices, `12` materials, `830,584` bytes.
- Showcase inspection/validation: `PASS=12`, `WARNING=0`, `FAIL=0`, `NOT_TESTED=1` (`GLB-013`, no skins/animations).
- Regenerating the showcase GLB from the repository generator produced the same SHA-256.

## Boundaries

- Roblox Studio and Godot imports were not run. The Roblox-style showcase is an asset fit, not proof of engine import; engine integration remains `NOT_TESTED`.
- Showcase geometry is intentionally stylized low-poly work, not photoreal or hand-sculpted AAA modeling.
- The showcase has no rigging, skinning, animation, audio or VFX simulation.
- Blender integration tests are skipped in hosted CI because hosted CI has no Blender installation.
- comfy-kit remains an optional external owner; AssetForge does not install models or edit its configuration.

## Requirements

- Python 3.10 or newer; CI covers Python 3.12–3.14.
- Pillow is optional but recommended for image recipes.
- Blender and blender-skills are optional and independently installed.
- All external tools and model weights are optional.
