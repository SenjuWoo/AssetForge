"""Deterministic procedural crate for the blender-skills pipeline.

Runs inside Blender. This is AssetForge glue, not a replacement for upstream
modeling skills: it creates one clean mesh that the upstream material, QA and
export skills then own.

    blender -b --factory-startup -P procedural_crate.py -- --out crate.blend
"""

import argparse
import json
import os
import sys

import bpy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    obj = bpy.context.object
    obj.name = "SM_Crate"
    obj.data.name = "SM_Crate_Mesh"
    obj.scale = (0.9, 0.65, 0.55)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.location.z = 0.275

    bevel = obj.modifiers.new("EdgeBevel", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 2
    bevel.limit_method = "ANGLE"
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=bevel.name)

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.out))
    print("@@JSON@@" + json.dumps({
        "ok": True,
        "blend": os.path.abspath(args.out),
        "objects": [obj.name],
        "polygons": len(obj.data.polygons),
        "vertices": len(obj.data.vertices),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
