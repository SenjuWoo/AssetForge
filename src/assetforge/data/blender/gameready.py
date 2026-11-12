"""Import a GLB, collapse it to a triangle budget, shrink textures, export GLB.

Runs inside Blender. AssetForge sets ASSETFORGE_SRC so the triangle and
texture limits stay in assetforge.gameready and are not copied here.

    blender -b --factory-startup -P gameready.py -- --input in.glb --out out.glb --tris 17000 --texture 1024
"""

import json
import os
import sys

import bpy

_src = os.environ.get("ASSETFORGE_SRC")
if not _src:
    raise SystemExit("ASSETFORGE_SRC is not set")
if _src not in sys.path:
    sys.path.insert(0, _src)

from assetforge.gameready import fit_size  # noqa: E402


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--tris", type=int, required=True)
    parser.add_argument("--texture", type=int, required=True)
    return parser.parse_args(argv)


def _meshes():
    return [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.data]


def _activate(obj):
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for other in bpy.data.objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj])


def _faces(obj) -> int:
    return len(obj.data.polygons)


def _decimate(obj, ratio: float) -> None:
    mod = obj.modifiers.new("AF_Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    with _activate(obj):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def _resize_images(cap: int) -> list[dict]:
    report = []
    for image in bpy.data.images:
        width, height = int(image.size[0]), int(image.size[1])
        if width <= 0 or height <= 0:
            continue
        new_w, new_h = fit_size(width, height, cap)
        if (new_w, new_h) == (width, height):
            report.append({"name": image.name, "before": [width, height], "after": [width, height]})
            continue
        image.scale(new_w, new_h)
        report.append({"name": image.name, "before": [width, height], "after": [new_w, new_h]})
    return report


def main() -> int:
    args = _args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.input)
    meshes = _meshes()
    if not meshes:
        raise SystemExit("imported GLB has no mesh")

    for obj in meshes:
        with _activate(obj):
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    before = sum(_faces(obj) for obj in meshes)
    ratio = 1.0 if before <= args.tris else max(args.tris / before, 1.0 / before)
    if ratio < 1.0:
        for obj in list(meshes):
            if _faces(obj) <= 1:
                continue
            _decimate(obj, ratio)

    meshes = _meshes()
    after = sum(_faces(obj) for obj in meshes)
    textures = _resize_images(args.texture)
    has_uv = any(mesh.data.uv_layers for mesh in meshes)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=args.out,
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_tangents=has_uv,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_cameras=False,
        export_lights=False,
        export_animations=False,
        export_unused_images=False,
        export_unused_textures=False,
    )
    print("GAMEREADY " + json.dumps({
        "ok": True,
        "faces_before": before,
        "faces_after": after,
        "tris_target": args.tris,
        "texture_cap": args.texture,
        "textures": textures,
    }))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print("GAMEREADY " + json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        raise
