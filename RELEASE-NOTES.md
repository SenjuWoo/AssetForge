# AssetForge 0.4.0 — Any mesh in, checked rig out

Point AssetForge at whatever you were handed. It now tells you what the file is, converts it if it is not a GLB, and checks the parts that break in an engine: the rig, the materials and the textures inside the file.

## Included

- `assetforge probe PATH` looks at a file or a folder without a project and prints the recipe commands that fit, with the numbers behind the choice.
- `mesh-convert` turns FBX, OBJ, STL, PLY, glTF, USD, Alembic and `.blend` into one validated GLB through Blender, keeping rigs, skin weights and animations.
- Rig validation is real: joints, inverse bind matrices, skin weights and animation channels are checked for consistency.
- Material validation: dangling material, texture and image references fail; a textured surface with no UV set is flagged.
- Texture budgets now measure textures embedded in the GLB.

## Start here

```bat
assetforge.cmd probe model.fbx
assetforge.cmd run mesh-convert --input model.fbx
assetforge.cmd export <asset> --target roblox --dry-run
```

## Verified

- A rigged, animated FBX and an OBJ with its `.mtl` were converted with Blender 5.3 from a folder whose name has a space, `!`, parentheses and an accented letter. The rigged result kept 1 skin, 2 joints and a 1-second animation, passed the structural rig check, and the official glTF validator reported 0 errors.
- The new checks are covered by fixtures built from bytes: broken inverse bind counts, missing weights, out-of-range joint indices, mismatched animation keys, dangling materials and oversized embedded textures each fail or warn as documented.
- Hosted CI has no Blender, so the conversion tests skip there and run in the local suite.

## Boundaries

- A passing rig check means the data is consistent. Nothing renders the deformation.
- `mesh-gameready` still drops animations and now says so in the job.
- Roblox Studio, Unity, Godot and Unreal imports were not run.
- Collada (`.dae`) depends on the Blender build; recent builds no longer ship that importer.
