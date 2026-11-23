"""Bake a validated Scene into per-frame data for Blender (and SFX timing)."""
from __future__ import annotations

import math
import zlib
from pathlib import Path

from .motion import CharacterAnimator, CharacterDirection, Skeleton, Track, rot
from .scene_schema import Scene

ROOT = Path(__file__).resolve().parent.parent


def joint_world(ch: dict, i: int, sk: Skeleton, joint: str) -> tuple[float, float, float]:
    """World (x, y, angle_deg) of a hand joint at frame i - mirrors the Blender rig hierarchy."""
    side = joint[-1]
    if joint not in ("hand_f", "hand_b"):
        raise ValueError(f"FK only implemented for hands, got {joint}")
    hip = sk.hip
    sh = sk.shoulder_front if side == "f" else sk.shoulder_back
    ang = ch["torso"][i]
    off = rot((sh[0] - hip[0], sh[1] - hip[1]), ang)
    p = [hip[0] + off[0], hip[1] + off[1]]
    for seg, ln in ((f"arm_{side}_up", sk.upper_arm), (f"arm_{side}_lo", sk.forearm)):
        ang += ch[seg][i]
        d = rot((0.0, -ln), ang)
        p[0] += d[0]
        p[1] += d[1]
    ang += ch[f"hand_{side}"][i]
    f = ch["facing"][i]
    return ch["x"][i] + f * p[0], ch["y"][i] + p[1], f * ang


def foot_contacts(ch: dict, fps: int) -> list[float]:
    """Times where a foot plants during locomotion (for footstep SFX)."""
    out, prev = [], None
    for i in range(1, len(ch["x"])):
        moving = abs(ch["x"][i] - ch["x"][i - 1]) > 1e-4
        lower = "f" if ch["leg_f_up"][i] > ch["leg_b_up"][i] else "b"  # leading leg plants
        if moving and prev is not None and lower != prev:
            out.append(i / fps)
        prev = lower if moving else None
    return out


def bake_scene(scene: Scene) -> dict:
    fps = scene.fps
    n = int(round(scene.duration * fps))
    chars, channels = [], {}
    for c in scene.characters:
        def direction(start_x):
            return CharacterDirection(c.character, start_x=start_x, facing=c.facing,
                                      actions=[a.model_dump(exclude_none=True) for a in c.actions],
                                      expressions=[e.model_dump() for e in c.expressions],
                                      looks=[k.model_dump() for k in c.looks], blink_seed=zlib.crc32(c.id.encode()) % 997)
        start_x = c.start_x
        if c.end_x is not None:  # solve start so the walk lands exactly at end_x
            probe = CharacterAnimator(direction(0.0), fps).bake(n)
            start_x = c.end_x - probe["x"][-1]
        ch = CharacterAnimator(direction(start_x), fps).bake(n)
        ch["y"] = [y + scene.ground_y for y in ch["y"]]
        channels[c.id] = ch
        chars.append({"id": c.id, "spec": str(ROOT / f"characters/specs/{c.character}.json"), "channels": ch,
                      "z": c.z, "character": c.character})
    props = []
    for p in scene.props:
        d = {"id": p.id, "kind": p.kind, "z": p.z}
        if p.label:
            d["label"] = p.label
        if p.color:
            d["color"] = p.color
        tracks: dict = {}
        if p.keys:
            for comp in ("x", "y", "s", "rot"):
                keys = [(k.t, getattr(k, comp), k.ease) for k in p.keys if getattr(k, comp) is not None]
                if keys:
                    tr = Track(keys)
                    tracks[comp] = [round(tr(i / fps), 4) for i in range(n)]
        if p.bob and "y" in tracks:
            tracks["y"] = [y + p.bob * math.sin(2 * math.pi * 0.6 * i / fps + zlib.crc32(p.id.encode()) % 7) for i, y in
                           enumerate(tracks["y"])]
            tracks["rot"] = [r + 3.0 * math.sin(2 * math.pi * 0.45 * i / fps) for i, r in
                             enumerate(tracks.get("rot", [0.0] * n))]
        if p.attach:
            a = p.attach
            d["attach"] = {"character": a.character, "joint": a.joint, "offset": a.offset, "rot": a.rot, "z": a.z}
            if a.upright is not None:
                ch = channels[a.character]
                sk = Skeleton.load(next(c.character for c in scene.characters if c.id == a.character))
                tracks["rot"] = [round(a.upright - joint_world(ch, i, sk, a.joint)[2], 3) for i in range(n)]
        if p.follow:  # e.g. a puff spawned at a hand position at time t
            fo = p.follow
            ch = channels[fo["character"]]
            sk = Skeleton.load(next(c.character for c in scene.characters if c.id == fo["character"]))
            i0 = min(n - 1, int(fo["t"] * fps))
            hx, hy, _ = joint_world(ch, i0, sk, fo["joint"])
            ox, oy = fo.get("offset", [0, 0])
            tracks["x"] = [hx + ox] * n
            tracks["y"] = [hy + oy] * n
            tracks["progress"] = [max(0.0, min(1.0, (i / fps - fo["t"]) / fo.get("duration", 0.6)))
                                  if i / fps >= fo["t"] else 0.0 for i in range(n)]
            d["count"] = fo.get("count", 8)
        if tracks:
            d["tracks"] = tracks
        props.append(d)
    cam_tracks = {}
    for comp in ("x", "y", "width"):
        tr = Track([(k.t, getattr(k, comp), k.ease) for k in scene.camera])
        cam_tracks[comp] = [round(tr(i / fps), 4) for i in range(n)]
    return {"fps": fps, "frames": n, "characters": chars, "props": props, "camera": cam_tracks,
            "ground_y": scene.ground_y, "background": {**scene.background, "ground_y": scene.ground_y}}
