# Textures and sprites

Everything a 2D asset or a surface material needs, one command each. The image model is comfy-forge's; every other step is plain image arithmetic or Blender, so it gives the same result every time.

| You have | You want | Recipe |
| --- | --- | --- |
| a description of a surface | a tileable PBR material | `texture-generate` |
| a picture of a surface | the same picture, repeating without a seam | `texture-tileable` |
| a colour map | normal, height, roughness, occlusion, metallic, ORM | `texture-pbr` |
| three grey maps | one ORM texture | `texture-pack` |
| a description of an object | a transparent sprite | `sprite-generate` |
| a picture on a plain background | a transparent, trimmed sprite | `image-cutout` |
| any picture | pixel art on a palette | `pixel-art` |
| a sheet | its frames | `sprite-slice` |
| frames | a sheet with frame rectangles | `sprite-atlas` |
| a 3D model | sprites in 8 facings, per animation | `sprite-render` |
| a picture of one object | a game-ready 3D model | `comfy-3d` |
| a PNG | DDS (DXT1/DXT5, mipmaps) or TGA | `image-prep --set format=dds` |

`assetforge probe <file>` reads a picture and prints the commands that fit it: a subject on a plain background, a cut-out sprite and a surface are told apart.

## A material from a prompt

```bat
assetforge.cmd run texture-generate --set "prompt=worn oak floor planks" --set name=oak-planks
assetforge.cmd export ASSET --target godot
```

Describe the surface only. `prompt_suffix` already asks for a flat, top-down, evenly lit picture; change it if your model wants other words. The export holds:

```text
textures/oak-planks-basecolor.png     sRGB
textures/oak-planks-normal.png        linear, +Y up (opengl)
textures/oak-planks-height.png        linear
textures/oak-planks-roughness.png     linear
textures/oak-planks-occlusion.png     linear
textures/oak-planks-metallic.png      linear
textures/oak-planks-orm.png           R occlusion, G roughness, B metallic
textures/oak-planks-material.json     the list above, as data
```

Set `convention=directx` for Unreal, Skyrim or Fallout: their normal maps have green pointing down. `metallic=1` for bare metal. `strength` deepens the normal map; lower it when `TEX-NORMAL` warns that the map leans.

### What is measured and what is not

| Check | Meaning |
| --- | --- |
| `TEX-SEAM` | How much the wrap-around edge differs from one pixel to the next, against the busiest ordinary lines of the same picture. `PASS` up to 1.3, `WARNING` up to 2.0, `FAIL` above. |
| `TEX-NORMAL` | The normal map points out of the surface and does not lean. |
| `TEX-DERIVED` | Always `NOT_TESTED`. Height is the picture's brightness; normal, roughness and occlusion follow from it. That is an estimate. A dark stain reads as a hollow. |
| `TEX-VISUAL`, `GEN-VISUAL` | Always `NOT_TESTED`. Nobody looked. Open the `-tiled.png` preview: a model that drew perspective or a light direction gives a texture whose repeat shows, whatever the seam measures. |

### How a picture is made to tile

The last 15 % of the picture (`blend`) is laid over the first 15 % and removed, on each axis, and the result is scaled back to its size. The two layers are joined in two parts. Broad tones fade into each other across the whole overlap, so a lighting drift disappears. Detail switches from one layer to the other along the path where the two differ least, so the join follows a mortar line or a plank edge and no brick is drawn twice. A picture that already tiles is not touched.

`seamless=true` asks SwarmUI to render the picture tiling in the first place. Not every model supports it; when it fails the run says so, and leaving it off always works.

## A sprite from a prompt

```bat
assetforge.cmd run sprite-generate --set "prompt=a red health potion in a round glass bottle, game item icon" --set name=health-potion
assetforge.cmd run pixel-art --input assets\<id>\outputs\health-potion-cutout.png --set size=48 --set palette=sweetie16
```

`sprite-generate` asks for a plain white background (`prompt_suffix`), then runs the cut-out. The cut-out needs that plain background: it reads the colour off the border (`key=auto`, or `key=#rrggbb`), removes it from the border inwards up to `tolerance`, and keeps anything of the same colour that the subject encloses. `mode=key` removes the colour everywhere instead. Along the edge, each pixel's alpha is its coverage and the background's tint is taken out of it; fully transparent pixels are given the colour of the nearest subject edge, so a texture filter does not blend toward white.

`CUT-BACKGROUND` warns when less than half the border is one colour, or when almost nothing was removed.

The sidecar `<name>-cutout.json` records the sprite's size, its anchor (the middle of its bottom edge) and where it sat in the source picture.

### Redrawing a picture (image to image)

With a comfy-forge that has image to image (0.11.0 or later):

```bat
assetforge.cmd run comfy-generate --input init=frame.png --set "prompt=the same knight, inked comic style" --set creativity=0.5
```

`creativity` runs from 0 (keep the picture) to 1 (ignore it). `negative`, `lora`, `transparent` and `upscale` are passed the same way. An older comfy-forge is refused with a message that names the missing option, before anything renders.

## Pixel art

`pixel-art` scales the picture so its longer side is `size` pixels (a smaller picture is not enlarged), turns alpha on or off at half coverage, and maps the colours to:

- a built-in palette: `pico8`, `db16`, `sweetie16`, `cga`, `gameboy`, `1bit`;
- a palette file: `--input palette=colours.hex` (one `rrggbb` a line), a GIMP `.gpl`, or an image whose pixels are the colours;
- or `colors` colours picked from the picture itself.

`dither=true` dithers onto a fixed palette. The sprite is written at its real size, with an enlarged preview (`preview_scale`) for looking at.

## Sprites from a 3D model

```bat
assetforge.cmd run sprite-render --input hero.glb --set size=128 --set frames=8
assetforge.cmd export ASSET --target godot
```

Blender renders the model with a fixed orthographic camera and a transparent background.

| Parameter | Meaning |
| --- | --- |
| `directions` | 1, 4, 8 or 16 facings. The first is `south`: the model faces the viewer. Then `south-east`, `east`, and so on round. `yaw` turns the whole set (45 with `directions=4` gives the four diagonals an isometric game uses). |
| `pitch` | Camera height above the ground in degrees: 30 for 2:1 isometric, 35.264 for true isometric, 50 to 60 for top-down, 0 for a side view. |
| `animations` | `all`, `none`, or names separated by commas. Each is sampled as a loop into `frames` frames. |
| `engine` | `workbench` shaded and fast; `flat` the base colour with no shading; `eevee` lit, with materials and emission. |
| `antialias` | `false` gives hard edges for pixel-style sprites. |
| `pivot` | `auto` turns the facings about the model's origin when the model stands on it, so a character does not slide as it turns; otherwise about the middle of its bounds. |

Every frame of every facing shares one scale, so an animation does not pulse. The export holds the sheet and its record:

```json
{
  "image": "hero-sheet.png",
  "frame_size": [128, 128],
  "pixels_per_unit": 61.2,
  "directions": [{"name": "south", "yaw": 0.0, "anchor": [64.0, 112.5]}],
  "animations": [{"name": "walk", "frames": 8, "fps": 8.0, "seconds": 1.0, "loop": true}],
  "frames": [{"animation": "walk", "direction": "south", "index": 0, "x": 0, "y": 0, "w": 128, "h": 128, "anchor": [64.0, 112.5]}]
}
```

The anchor is the ground point under the model, in pixels from the frame's top-left corner. Draw each frame so its anchor sits on the character's position. A moving model gets one row per animation and facing; a still one puts its facings in a single row.

Reading it in Godot:

```gdscript
var record = JSON.parse_string(FileAccess.get_file_as_string("res://hero-sheet.json"))
var frames := SpriteFrames.new()
for f in record.frames:
    var key := "%s_%s" % [f.animation, f.direction]
    if not frames.has_animation(key):
        frames.add_animation(key)
    var piece := AtlasTexture.new()
    piece.atlas = preload("res://hero-sheet.png")
    piece.region = Rect2(f.x, f.y, f.w, f.h)
    frames.add_frame(key, piece)
```

`SPRITE-EMPTY` fails a run with a frame that shows nothing. `SPRITE-CLIP` warns when a frame touches its edge. `SPRITE-ANIM` warns when animations were left out. `SPRITE-VISUAL` is always `NOT_TESTED`: open the sheet.

Formats other than GLB go through `mesh-convert` first.

## A 3D model from a picture

```bat
assetforge.cmd run sprite-generate --set "prompt=a viking axe with a wolf-head pommel" --set name=axe
assetforge.cmd run comfy-3d --input assets\<id>\outputs\generated\axe.png
assetforge.cmd engine-check assets\<id>\outputs\axe-gameready.glb
```

`comfy-3d` hands the picture to comfy-forge's image-to-3D (Pixal3D; `variant=pixal3d-multi` takes a four-view turnaround sheet for a character) on its ComfyUI, running or started for the job. The sculpt that comes back has about 700,000 triangles and stays in the asset as the source mesh. The recipe then collapses it under the budget (`budget=game`, 20,000 triangles) exactly as `mesh-gameready` does and validates the result. It needs comfy-forge 0.11.0 or later with its 3D weights installed, and takes about four minutes on a 16 GB GPU.

One picture shows one side. The other sides are the model's guess, and `GEN-VISUAL` stays `NOT_TESTED`.

## Compressed and legacy formats

```bat
assetforge.cmd run image-prep --input wall-normal.png --set format=dds
```

DDS is written by ImageMagick with a full mipmap chain: `dds_compression=auto` picks DXT5 for a picture with alpha and DXT1 without; `none` writes it uncompressed. BC7 is not written. `format=tga` writes RLE TGA through Pillow.

## Limits

- Pictures up to 8192 px a side; atlases and sheets up to 8192 px a side and 33.5 million pixels.
- `sprite-atlas` takes up to 256 frames; `sprite-render` up to 1024 rendered frames.
- The cut-out is a colour key. A subject photographed on a busy background needs a matting model, which comfy-forge has (`transparent=true` on a comfy-forge that supports it).
- A derived normal map is not a baked one. For a hero asset, bake from geometry.
