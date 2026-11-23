"""Blender entry point: blender -b --factory-startup -P bl_render.py -- job.json

Builds the scene described by the job (environment, characters, props,
camera), keys all baked animation, and renders PNG frames. Existing frames are
skipped (use_overwrite=False + placeholders), so renders are resumable and can
be split across processes.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import bl_character  # noqa: E402
import bl_lib as L  # noqa: E402
import bl_props  # noqa: E402
import bl_world  # noqa: E402

CAM_DIST = 22.222  # camera height above z=0; with 50mm lens / 36mm sensor -> 16 units visible width


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_render(job):
    sc = bpy.context.scene
    sc.render.engine = job.get("engine", "BLENDER_EEVEE")
    sc.render.resolution_x, sc.render.resolution_y = job["resolution"]
    sc.render.resolution_percentage = job.get("resolution_percentage", 100)
    sc.render.fps = job["fps"]
    sc.frame_start, sc.frame_end = job["frame_start"], job["frame_end"]
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.compression = 15
    sc.render.use_overwrite = False
    sc.render.use_placeholder = True
    sc.render.filepath = os.path.join(job["output_dir"], "f_")
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.film_transparent = False
    if sc.render.engine == "BLENDER_EEVEE":
        sc.eevee.taa_render_samples = job.get("samples", 8)
        sc.eevee.use_bloom = job.get("bloom", False)
        sc.eevee.use_gtao = False
        sc.eevee.use_ssr = False
        sc.eevee.use_soft_shadows = False
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = L.hex_rgba(job.get("clear_color", "#20203A"))
    sc.world = world
    if job.get("threads"):
        sc.render.threads_mode = "FIXED"
        sc.render.threads = job["threads"]


def setup_camera(job):
    cam_data = bpy.data.cameras.new("camera")
    cam_data.lens = 50
    cam_data.sensor_width = 36
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.clip_start = 0.5
    cam_data.clip_end = 400
    cam = bpy.data.objects.new("camera", cam_data)
    L.link(cam)
    bpy.context.scene.camera = cam
    cj = job["camera"]
    n = len(cj["x"])
    for i in range(n):
        f = job["frame_start"] + i
        # visible width at z=0 scales linearly with camera height
        cam.location = (cj["x"][i], cj["y"][i], CAM_DIST * cj["width"][i] / 16.0)
        cam.rotation_euler = (0, 0, math.radians(cj.get("roll", [0] * n)[i]))
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
    L.linear_interpolation([cam])
    return cam


def main():
    job_path = sys.argv[sys.argv.index("--") + 1]
    with open(job_path) as fh:
        job = json.load(fh)
    reset_scene()
    setup_render(job)
    os.makedirs(job["output_dir"], exist_ok=True)
    fonts = job["fonts"]
    bl_world.build(job.get("background", {"kind": "solid"}), fonts, CAM_DIST)
    rigs = {}
    for c in job.get("characters", []):
        with open(c["spec"]) as fh:
            spec = json.load(fh)
        rig = bl_character.build(spec, name=c["id"])
        rig["root"].location.z = c.get("z", 0.0)
        bl_character.apply_channels(rig, c["channels"], job["frame_start"])
        rigs[c["id"]] = rig
        if c.get("shadow", True):
            bl_props.ground_shadow(c["id"], c["channels"], job["frame_start"], job.get("ground_y", 0.0),
                                   c.get("z", 0.0))
    for p in job.get("props", []):
        bl_props.build_prop(p, rigs, fonts, job["frame_start"])
    setup_camera(job)
    if job.get("save_blend"):
        bpy.ops.wm.save_as_mainfile(filepath=job["save_blend"])
    if job.get("still_frame") is not None:
        sc = bpy.context.scene
        sc.frame_set(job["still_frame"])
        sc.render.filepath = job["still_path"]
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)
    print("FINSTUDIO_RENDER_OK")


if __name__ == "__main__":
    main()
