"""Deterministic Blender background test asset.

Run by the Blender adapter:
    blender -b --factory-startup --python blender_sample.py -- --out model.glb
"""

import argparse
import sys

import bpy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    obj = bpy.context.object
    obj.name = "AssetForge_Sample"

    material = bpy.data.materials.new("AssetForge_Sample_Mat")
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = (0.18, 0.45, 0.72, 1.0)
        principled.inputs["Roughness"].default_value = 0.55
    obj.data.materials.append(material)

    bevel = obj.modifiers.new("Bevel", "BEVEL")
    bevel.width = 0.04
    bevel.segments = 2
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=bevel.name)

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=args.out, export_format="GLB", use_selection=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
