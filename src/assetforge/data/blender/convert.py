"""Import a mesh file in any format this Blender can read and export one GLB.

Runs inside Blender. Rigs, skin weights and animations are kept. Which formats
work depends on the Blender build, so the importer is looked up at run time
rather than assumed.

    blender -b --factory-startup -P convert.py -- --input in.fbx --out out.glb
"""

import json
import os
import sys

import bpy

# Extension -> importer operators to try, newest first. A Blender build that
# lacks one simply falls through to the next.
IMPORTERS = {
    ".fbx": ("import_scene.fbx", "wm.fbx_import"),
    ".obj": ("wm.obj_import", "import_scene.obj"),
    ".stl": ("wm.stl_import", "import_mesh.stl"),
    ".ply": ("wm.ply_import", "import_mesh.ply"),
    ".gltf": ("import_scene.gltf",),
    ".glb": ("import_scene.gltf",),
    ".dae": ("wm.collada_import",),
    ".abc": ("wm.alembic_import",),
    ".usd": ("wm.usd_import",),
    ".usda": ("wm.usd_import",),
    ".usdc": ("wm.usd_import",),
    ".usdz": ("wm.usd_import",),
}


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--animations", type=int, default=1)
    return parser.parse_args(argv)


def _operator(path: str):
    module, _, name = path.partition(".")
    group = getattr(bpy.ops, module, None)
    operator = getattr(group, name, None) if group is not None else None
    if operator is None:
        return None
    try:
        operator.get_rna_type()
    except Exception:
        return None
    return operator


def _load(source: str) -> str:
    suffix = os.path.splitext(source)[1].lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=source)
        return "wm.open_mainfile"
    candidates = IMPORTERS.get(suffix)
    if not candidates:
        raise RuntimeError(f"no importer is known for {suffix or 'a file without an extension'}")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    errors = []
    for path in candidates:
        operator = _operator(path)
        if operator is None:
            continue
        try:
            operator(filepath=source)
            return path
        except Exception as exc:  # try the next importer for this format
            errors.append(f"{path}: {exc}")
    if errors:
        raise RuntimeError("; ".join(errors))
    raise RuntimeError(f"this Blender build has no importer for {suffix}")


def main() -> int:
    args = _args()
    importer = _load(os.path.abspath(args.input))
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.data]
    if not meshes:
        raise RuntimeError("the file imported but contains no mesh")
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    has_uv = any(obj.data.uv_layers for obj in meshes)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=args.out,
        export_format="GLB",
        export_apply=not armatures,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_tangents=has_uv,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_cameras=False,
        export_lights=False,
        export_skins=True,
        export_animations=bool(args.animations),
    )
    print("CONVERT " + json.dumps({
        "ok": True,
        "importer": importer,
        "blender": bpy.app.version_string,
        "meshes": len(meshes),
        "faces": sum(len(obj.data.polygons) for obj in meshes),
        "armatures": len(armatures),
        "actions": len(bpy.data.actions),
        "materials": len(bpy.data.materials),
        "images": len([image for image in bpy.data.images if image.size[0] > 0]),
    }))
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except BaseException as exc:
        if isinstance(exc, SystemExit) and not exc.code:
            raise
        print("CONVERT " + json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        sys.stdout.flush()
        os._exit(1)
    raise SystemExit(code)
