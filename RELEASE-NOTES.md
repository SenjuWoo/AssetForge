# AssetForge 0.9.0 — Textures, sprites and image to 3D

Everything a game needs that a text-and-code agent cannot draw, one command each. Nothing was removed and no existing format changed.

## New

- **Materials from words.** `texture-generate` renders a surface through comfy-forge, makes it repeat without a seam, measures the seam and writes a full PBR set: base colour, normal (OpenGL or DirectX), height, roughness, occlusion, metallic, packed ORM and `material.json`.
- **Sprites from words.** `sprite-generate` renders a subject on a plain background and cuts it out with real transparency, a clean edge and a recorded anchor. `pixel-art` turns any picture into pixel art on a palette.
- **Sprites from a 3D model.** `sprite-render` renders a GLB at your game's camera angle in 1 to 16 facings, every animation, all at one scale, and writes a sheet plus a JSON with each frame's rectangle and anchor.
- **A 3D model from a picture.** `comfy-3d` sends one picture to comfy-forge's image-to-3D and collapses the result to a validated, game-ready GLB.
- **Work on pictures you have.** `texture-tileable`, `texture-pbr`, `image-cutout` and `sprite-slice` run with no model. `image-prep` writes DDS (with mipmaps) and TGA.
- **No manual server start.** The image recipes start comfy-forge's SwarmUI for the job when it is not running and stop it afterwards. Seeds are picked and recorded; newer comfy-forge options (negative prompt, image to image, LoRA, transparency) are passed when installed.

## Fixed

- `mesh-gameready` output passes the official glTF validator when the collapse leaves a triangle with no UV area (Blender wrote a zero tangent there).
- Exports now include the records that belong beside a picture; an atlas used to ship without `atlas.json`.
- A second export no longer leaves stale files behind; two pictures with the same name are refused instead of one overwriting the other.
- Out-of-range image sizes and quality are clear errors.
- Every command starts about 0.7 s faster.

## Verified

Windows 11, Python 3.14, Blender 5.3, Godot 4.7.2, ImageMagick 7.1.2, comfy-forge with SwarmUI 0.9.8.4 on an RTX 4080 SUPER: the full suite passed with every provider present; a real prompt-to-material run, sprite renders of a generated axe and the showcase sword, and the game-ready fix on a real Pixal3D mesh (official validator 0 errors, Godot import and load).

## Not verified

Nobody looked at generated pictures or derived maps as art (`GEN-VISUAL`, `TEX-DERIVED` stay `NOT_TESTED`). `comfy-3d` was tested against a stand-in for comfy-forge's 3D tool; starting SwarmUI for a job is covered by tests, not a live run. No engine other than Godot was launched.
