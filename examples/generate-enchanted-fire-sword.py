"""Artisan procedural low-poly flame sword for AssetForge.

This is a genuine multi-part 3D mesh kit (layered blade, ember core, leather
wrap, finial and sparks), unlike a flat generated image relief. The concept
image was used only as art direction. Preview camera/lights are not exported.
"""

import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    parser.add_argument("--glb", required=True)
    parser.add_argument("--png", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


ARGS = parse_args()
random.seed(0xF17E)

def material(name, base, metallic, roughness, emission=(0, 0, 0, 1), emission_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "OPAQUE"
    node = mat.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (*base, 1.0)
    node.inputs["Metallic"].default_value = metallic
    node.inputs["Roughness"].default_value = roughness
    node.inputs["Emission Color"].default_value = emission
    node.inputs["Emission Strength"].default_value = emission_strength
    return mat


def mesh_from_points_extruded(name, points, depth, mat, bevel=0.02, smooth=False):
    vertices = [(x, y, depth / 2) for x, y in points]
    vertices += [(x, y, -depth / 2) for x, y in points]
    count = len(points)
    faces = [list(range(count)), list(reversed(range(count, count * 2)))]
    for index in range(count):
        nxt = (index + 1) % count
        faces.append([index, nxt, nxt + count, index + count])
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(mat)
    if bevel > 0:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        modifier = obj.modifiers.new("Bevel", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        modifier.limit_method = "ANGLE"
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        obj.select_set(False)
    if smooth:
        mesh = obj.data
        for polygon in mesh.polygons:
            polygon.use_smooth = True
    return obj


def plane_on_faces(name, points, mat):
    front = mesh_from_points_extruded(f"{name}_Front", points, 0.020, mat, bevel=0.004)
    back = mesh_from_points_extruded(f"{name}_Back", points, 0.020, mat, bevel=0.004)
    front.location.z = 0.095
    back.location.z = -0.095
    return front, back


def add_cylinder_y(name, radius, depth, y, mat, segments=14):
    bpy.ops.mesh.primitive_cylinder_add(vertices=segments, radius=radius, depth=depth, location=(0, y, 0), rotation=(math.pi / 2, 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def add_ico(name, radius, location, mat, scale=(1, 1, 1), segments=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=segments + 1, radius=radius, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def add_ring(name, radius, tube, y, mat, segments=16):
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=tube, location=(0, y, 0), rotation=(math.pi / 2, 0, 0), major_segments=segments, minor_segments=6)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def tube(name, points, radius, mat, resolution=5):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 7
    curve.bevel_depth = radius
    curve.bevel_resolution = min(resolution, 3)
    spline = curve.splines.new("NURBS")
    spline.points.add(len(points) - 1)
    for index, point in enumerate(points):
        spline.points[index].co = (*point, 1.0)
    spline.use_endpoint_u = True
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    curve.materials.append(mat)
    return obj


def star_polygon(cx, cy, outer, inner, rays=8):
    points = []
    for index in range(rays * 2):
        angle = math.pi / 2 + index * math.pi / rays
        radius = outer if index % 2 == 0 else inner
        points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return points


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = False
    return scene


def build():
    scene = clear_scene()
    collection = bpy.data.collections.new("EnchantedFireSword")
    scene.collection.children.link(collection)

    steel_dark = material("Obsidian_Steel", (0.020, 0.025, 0.038), 0.90, 0.34)
    steel = material("Charcoal_Steel", (0.075, 0.086, 0.110), 0.88, 0.39)
    silver = material("Starlight_Silver", (0.42, 0.45, 0.48), 0.92, 0.22)
    bronze = material("Magma_Bronze", (0.115, 0.043, 0.015), 0.72, 0.34, (0.20, 0.035, 0.006, 1), 0.18)
    bronze_hot = material("Magma_Bronze_Hot", (0.34, 0.070, 0.014), 0.55, 0.31, (0.62, 0.085, 0.010, 1), 0.65)
    leather = material("Charred_Leather", (0.025, 0.008, 0.006), 0.0, 0.92)
    leather_hi = material("Singed_Leather", (0.092, 0.018, 0.012), 0.0, 0.82)
    ember_dark = material("Ember_Dark", (0.28, 0.012, 0.003), 0.10, 0.43, (0.45, 0.014, 0.003, 1), 1.05)
    ember = material("Ember_Orange", (0.39, 0.035, 0.004), 0.0, 0.36, (0.92, 0.095, 0.006, 1), 2.25)
    ember_gold = material("Ember_Gold", (0.44, 0.115, 0.008), 0.0, 0.31, (1.0, 0.225, 0.008, 1), 3.15)
    white_hot = material("White_Hot", (0.54, 0.28, 0.055), 0.0, 0.20, (1.0, 0.55, 0.12, 1), 4.0)
    ruby = material("Ember_Core", (0.26, 0.008, 0.004), 0.0, 0.20, (0.98, 0.030, 0.006, 1), 3.4)

    def collect(obj):
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        collection.objects.link(obj)
        return obj

    # Outer blade shell: broad ember profile, faceted and dark.
    blade_profile = [
        (0.0, 4.08), (0.20, 3.78), (0.29, 3.38), (0.29, 2.86),
        (0.30, 2.08), (0.35, 1.32), (0.46, 0.91), (0.49, 0.55),
        (0.26, 0.47), (0.0, 0.47), (-0.26, 0.47), (-0.49, 0.55),
        (-0.46, 0.91), (-0.35, 1.32), (-0.30, 2.08), (-0.29, 2.86),
        (-0.29, 3.38), (-0.20, 3.78),
    ]
    outer = mesh_from_points_extruded("BladeShell", blade_profile, 0.19, steel_dark, bevel=0.030)
    collect(outer)

    # Three layered fire panels make the core emissive in physical depth.
    outer_fire = [
        (0.0, 3.82), (0.16, 3.48), (0.215, 3.05), (0.215, 2.38),
        (0.235, 1.52), (0.325, 0.94), (0.26, 0.65), (0.0, 0.61),
        (-0.26, 0.65), (-0.325, 0.94), (-0.235, 1.52), (-0.215, 2.38),
        (-0.215, 3.05), (-0.16, 3.48),
    ]
    for idx, obj in enumerate(plane_on_faces("Ember_Fire", outer_fire, ember_dark)):
        collect(obj)

    middle_fire = [
        (0.0, 3.66), (0.11, 3.33), (0.155, 2.86), (0.155, 2.22),
        (0.18, 1.36), (0.235, 0.97), (0.17, 0.74), (0.0, 0.70),
        (-0.17, 0.74), (-0.235, 0.97), (-0.18, 1.36), (-0.155, 2.22),
        (-0.155, 2.86), (-0.11, 3.33),
    ]
    for index, obj in enumerate(plane_on_faces("Ember_Core", middle_fire, ember)):
        obj.location.z += 0.027 if index == 0 else -0.027
        collect(obj)

    hot_core = [
        (0.0, 3.38), (0.065, 3.05), (0.055, 2.55), (0.100, 2.12),
        (0.055, 1.72), (0.095, 1.27), (0.045, 1.02), (0.0, 0.83),
        (-0.045, 1.02), (-0.095, 1.27), (-0.055, 1.72), (-0.100, 2.12),
        (-0.055, 2.55), (-0.065, 3.05),
    ]
    for index, obj in enumerate(plane_on_faces("WhiteHot_Core", hot_core, white_hot)):
        obj.location.z += 0.045 if index == 0 else -0.045
        collect(obj)

    # Rune chain: raised emissive strokes, not a texture-only symbol strip.
    rune_paths = [
        [(0.0, 2.78), (0.075, 2.62), (0.0, 2.46)],
        [(-0.105, 2.31), (0.0, 2.16), (0.105, 2.31)],
        [(0.0, 1.91), (0.070, 1.78), (0.0, 1.62), (-0.070, 1.49), (0.0, 1.34)],
        [(-0.105, 1.18), (0.0, 1.04), (0.105, 1.18)],
    ]
    for index, points in enumerate(rune_paths, start=1):
        front = tube(f"Rune_{index}_Front", [(x, y, 0.170) for x, y in points], 0.012, bronze_hot, 2)
        back = tube(f"Rune_{index}_Back", [(x, y, -0.170) for x, y in points], 0.012, bronze_hot, 2)
        collect(front)
        collect(back)

    # Engraved scroll facets: low-contrast seams, not floating trim.
    scroll_paths = [
        [(0.0, 3.24), (0.12, 2.96), (0.16, 2.63), (0.14, 2.34)],
        [(0.0, 3.24), (-0.12, 2.96), (-0.16, 2.63), (-0.14, 2.34)],
        [(0.0, 1.18), (0.095, 1.31), (0.14, 1.54)],
        [(0.0, 1.18), (-0.095, 1.31), (-0.14, 1.54)],
    ]
    for index, points in enumerate(scroll_paths, start=1):
        front = tube(f"Scrollwork_{index}_Front", [(x, y, 0.132) for x, y in points], 0.006, steel_dark, 2)
        back = tube(f"Scrollwork_{index}_Back", [(x, y, -0.132) for x, y in points], 0.006, steel_dark, 2)
        collect(front)
        collect(back)

    # Bat-wing crossguard: slimmer sweep, narrowed depth and pointed wingtips.
    wing = [
        (0.0, 0.66), (0.12, 0.67), (0.24, 0.58), (0.36, 0.53),
        (0.50, 0.58), (0.65, 0.68), (0.78, 0.74), (0.98, 0.72),
        (1.10, 0.58), (1.02, 0.42), (0.82, 0.25), (0.60, 0.02),
        (0.35, -0.03), (0.16, 0.03), (0.0, 0.0), (-0.16, 0.03),
        (-0.35, -0.03), (-0.60, 0.02), (-0.82, 0.25), (-1.02, 0.42),
        (-1.10, 0.58), (-0.98, 0.72), (-0.78, 0.74), (-0.65, 0.68),
        (-0.50, 0.58), (-0.36, 0.53), (-0.24, 0.58), (-0.12, 0.67),
    ]
    guard = mesh_from_points_extruded("Crossguard", wing, 0.145, steel, bevel=0.026)
    collect(guard)
    guard_ridge = [
        (0.0, 0.675), (0.12, 0.685), (0.24, 0.59), (0.37, 0.55),
        (0.51, 0.60), (0.66, 0.70), (0.79, 0.755), (0.95, 0.73),
        (1.04, 0.58), (0.91, 0.39), (0.68, 0.15), (0.42, 0.035),
        (0.0, -0.055), (-0.42, 0.035), (-0.68, 0.15), (-0.91, 0.39),
        (-1.04, 0.58), (-0.95, 0.73), (-0.79, 0.755), (-0.66, 0.70),
        (-0.51, 0.60), (-0.37, 0.55), (-0.24, 0.59), (-0.12, 0.685),
    ]
    ridge = mesh_from_points_extruded("GuardRidge", guard_ridge, 0.070, bronze, bevel=0.012)
    ridge.location.z = 0.088
    collect(ridge)
    ridge_back = mesh_from_points_extruded("GuardRidge_Back", guard_ridge, 0.070, bronze, bevel=0.012)
    ridge_back.location.z = -0.088
    collect(ridge_back)

    # Central 8-point star and ember eye.
    collect(add_cylinder_y("GuardPalm", 0.245, 0.19, 0.36, steel, 10))
    outer_star = mesh_from_points_extruded("GuardStar", star_polygon(0, 0.43, 0.29, 0.145, 8), 0.095, silver, bevel=0.016)
    outer_star.location.z = 0.18
    collect(outer_star)
    outer_star_back = mesh_from_points_extruded("GuardStar_Back", star_polygon(0, 0.43, 0.29, 0.145, 8), 0.095, silver, bevel=0.016)
    outer_star_back.location.z = -0.18
    collect(outer_star_back)
    collect(add_ico("GuardCore_Front", 0.115, (0, 0.43, 0.25), ruby, (1, 1, 0.56), 2))
    collect(add_ico("GuardCore_Back", 0.115, (0, 0.43, -0.25), ruby, (1, 1, 0.56), 2))

    # Hilt: obsidian core with two twisted charred leather cords.
    collect(add_cylinder_y("HiltCore", 0.135, 1.33, -0.54, steel, 10))
    collect(add_cylinder_y("HiltWrap", 0.190, 1.18, -0.55, leather, 14))
    for phase in (0.0, math.pi):
        points = []
        for index in range(31):
            t = index / 30
            angle = phase + t * math.pi * 9.0
            y = 0.08 - t * 1.27
            points.append((math.cos(angle) * 0.195, y, math.sin(angle) * 0.195))
        collect(tube(f"LeatherCord_{phase:.1f}", points, 0.030, leather_hi, 3))
    collect(add_ring("HiltCapTop", 0.205, 0.026, 0.095, bronze, 16))
    collect(add_ring("HiltCapBottom", 0.205, 0.026, -1.18, bronze, 16))

    # Finial: one continuous spindled spear-charm with an ember inlay.
    collect(add_cylinder_y("PommelNeck", 0.150, 0.44, -1.33, bronze, 12))
    collect(add_ring("PommelNeckCollarTop", 0.174, 0.022, -1.13, bronze, 16))
    collect(add_ring("PommelNeckCollarMiddle", 0.164, 0.019, -1.51, silver, 16))
    collect(add_ring("PommelCollar", 0.195, 0.028, -1.27, bronze, 16))
    pommel_outer = [
        (0.0, -1.16), (0.175, -1.30), (0.235, -1.56), (0.205, -1.83),
        (0.12, -2.06), (0.0, -2.29), (-0.12, -2.06), (-0.205, -1.83),
        (-0.235, -1.56), (-0.175, -1.30),
    ]
    collect(mesh_from_points_extruded("PommelSpine", pommel_outer, 0.155, steel, bevel=0.026))
    pommel_inlay = [
        (0.0, -1.28), (0.105, -1.38), (0.145, -1.57), (0.125, -1.79),
        (0.060, -1.96), (0.0, -2.09), (-0.060, -1.96), (-0.125, -1.79),
        (-0.145, -1.57), (-0.105, -1.38),
    ]
    collect(mesh_from_points_extruded("PommelEmberOuter", pommel_inlay, 0.045, ember_dark, bevel=0.008)).location.z = 0.080
    pommel_heart = [
        (0.0, -1.42), (0.060, -1.49), (0.083, -1.60), (0.065, -1.73),
        (0.0, -1.88), (-0.065, -1.73), (-0.083, -1.60), (-0.060, -1.49),
    ]
    collect(mesh_from_points_extruded("PommelEmberHeart", pommel_heart, 0.026, ruby, bevel=0.004)).location.z = 0.112
    collect(mesh_from_points_extruded("PommelEmberOuterBack", pommel_inlay, 0.045, ember_dark, bevel=0.008)).location.z = -0.080
    collect(mesh_from_points_extruded("PommelEmberHeartBack", pommel_heart, 0.026, ruby, bevel=0.004)).location.z = -0.112
    collect(add_cylinder_y("PommelTip", 0.040, 0.28, -2.34, bronze, 8))

    # Floating ember octahedra sell the flame enchantment without hiding silhouette.
    for index in range(14):
        y = random.uniform(0.65, 3.85)
        radius = random.uniform(0.025, 0.052)
        x = random.choice((-1, 1)) * random.uniform(0.30, 0.58) if index % 3 else random.uniform(-0.18, 0.18)
        z = random.choice((1, -1)) * random.uniform(0.16, 0.32)
        obj = add_ico(f"EmberSpark_{index + 1:02d}", radius, (x, y, z), ember_gold if index % 4 else white_hot, (1.0, 0.62, 1.0), 0)
        collect(obj)


def preview_scene():
    scene = bpy.context.scene
    scene.world = bpy.data.worlds.new("PreviewWorld")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.006, 0.005, 0.006, 1.0)
    background.inputs["Strength"].default_value = 0.36
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass

    bpy.ops.object.light_add(type="AREA", location=(2.8, 2.3, 4.6), rotation=(0.72, 0, -0.25))
    key = bpy.context.object
    key.name = "PreviewKey"
    key.data.energy = 690
    key.data.shape = "DISK"
    key.data.size = 4.3
    bpy.ops.object.light_add(type="AREA", location=(-3.2, 0.4, 3.0), rotation=(0.9, 0, 0.6))
    fill = bpy.context.object
    fill.name = "PreviewFill"
    fill.data.energy = 300
    fill.data.shape = "RECTANGLE"
    fill.data.size = 4.0
    fill.data.size_y = 2.0
    bpy.ops.object.light_add(type="POINT", location=(0, 2.0, 0.45))
    warm = bpy.context.object
    warm.name = "BladeFlameLight"
    warm.data.energy = 88
    warm.data.color = (1.0, 0.16, 0.025)
    bpy.ops.object.light_add(type="POINT", location=(0, -1.55, 0.55))
    core = bpy.context.object
    core.name = "PommelEmberLight"
    core.data.energy = 42
    core.data.color = (1.0, 0.07, 0.016)

    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "PreviewCamera"
    camera.location = (0, 0.86, 8.7)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 7.55
    camera.rotation_euler = (0, 0, 0)
    scene.camera = camera
    scene.render.resolution_x = 1150
    scene.render.resolution_y = 1600
    scene.render.filepath = ""


def main():
    args = ARGS
    args.blend = str(Path(args.blend).resolve())
    args.glb = str(Path(args.glb).resolve())
    args.png = str(Path(args.png).resolve())
    build()
    preview_scene()
    sword_objects = list(bpy.data.collections.get("EnchantedFireSword").objects)
    bpy.ops.wm.save_as_mainfile(filepath=args.blend)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in sword_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = sword_objects[0]
    bpy.ops.export_scene.gltf(
        filepath=args.glb,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_materials="EXPORT",
        export_yup=True,
    )
    scene = bpy.context.scene
    scene.render.filepath = args.png
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print(json.dumps({
        "blend": args.blend,
        "glb": args.glb,
        "png": args.png,
        "objects": len(sword_objects),
        "triangles": sum(sum(len(p.vertices) - 2 for p in obj.data.polygons) for obj in sword_objects if hasattr(obj.data, "polygons")),
    }, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
