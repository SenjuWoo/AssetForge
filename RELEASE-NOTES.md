# AssetForge 0.5.0 — A real engine import

Until now "exports to Godot" meant a correct package and nothing more. This release adds the missing claim: Godot itself imports the file and loads it.

## Included

- `assetforge engine-check FILE.glb` runs Godot 4 headless on a throwaway project, imports the GLB, loads and instantiates the result and reports meshes, skeletons, animation names and node classes. A file Godot cannot import fails.
- Godot, FFmpeg and ImageMagick are detected providers with a version, a path and a stated purpose in `doctor`, `providers` and `capabilities`.
- The agent runbook maps every external program to the job it does and to the install to ask for when it is missing.

## Verified

- Godot 4.7.2 on Windows imported and loaded the showcase sword (61 meshes) and the test triangle; a non-GLB file renamed `.glb` failed.
- Detection of Godot 4.7.2 (winget), FFmpeg 9.0.2 and ImageMagick 7.1.2-34 with none of them on the session PATH.
- The full suite, including the real Godot tests, on Windows.

## Not verified

- Rendering, materials on screen, animation playback and physics in Godot. The check proves import and load.
- Roblox Studio import. Export packaging for Roblox remains a file check.
- FFmpeg and ImageMagick are detected and documented; no recipe calls them.
- Godot discovery on Linux and macOS beyond `GODOT_EXE` and PATH.
