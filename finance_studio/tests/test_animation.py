import math

import pytest

from animation.bake import bake_scene, foot_contacts, joint_world
from animation.motion import (EXPRESSIONS, MOUTHS, POSES, CharacterAnimator, CharacterDirection, Skeleton, Track,
                              fk_chain, two_bone_ik)
from animation.prototype import LINES, build_scene
from animation.scene_schema import Scene, validate_scene


@pytest.mark.parametrize("target,bend", [((0.6, 0.1), 1), ((0.2, 1.1), -1), ((1.2, -0.5), 1), ((-0.4, 0.3), -1)])
def test_ik_reaches_reachable_targets(target, bend):
    up, lo = two_bone_ik(target, 0.78, 0.72, bend)
    end = fk_chain((0, 0), [up, lo], [0.78, 0.72])[-1]
    assert math.hypot(end[0] - target[0], end[1] - target[1]) < 1e-3


def test_ik_clamps_unreachable():
    up, lo = two_bone_ik((5.0, 0.0), 0.78, 0.72)
    end = fk_chain((0, 0), [up, lo], [0.78, 0.72])[-1]
    assert abs(math.hypot(*end) - 1.5) < 1e-3 and end[0] > 1.4


def test_every_pose_target_is_reachable():
    for name, spec in POSES.items():
        for side in spec.values():
            assert math.hypot(*side["target"]) < 0.78 + 0.72, name


def test_expressions_use_known_mouths():
    for e in EXPRESSIONS.values():
        assert e["mouth"] in MOUTHS


def test_track_easing_and_hold():
    tr = Track([(0, 0.0), (1, 10.0, "linear"), (2, 20.0, "hold")])
    assert tr(-1) == 0 and tr(0.5) == pytest.approx(5.0) and tr(1.5) == 10.0 and tr(3) == 20.0


def _walk(n=120):
    d = CharacterDirection("maya", start_x=0.0, actions=[{"type": "walk", "start": 0, "end": 3.0}])
    return CharacterAnimator(d, 30).bake(n)


def test_walk_moves_forward_and_feet_stay_grounded():
    ch = _walk()
    assert ch["x"][-1] > 3.0  # covers ground
    assert all(b >= a - 1e-9 for a, b in zip(ch["x"], ch["x"][1:]))  # never slides backwards
    assert max(ch["y"]) <= 0.001 and min(ch["y"]) > -0.3  # hips bob, feet planted


def test_walk_has_no_foot_sliding():
    """The planted foot's world x must stay (nearly) fixed while it is the stance foot."""
    sk = Skeleton.load("maya")
    ch = _walk()
    slips = []
    for i in range(10, 80):
        feet = []
        for side, hip in (("f", sk.hip_front), ("b", sk.hip_back)):
            p = fk_chain(hip, [ch[f"leg_{side}_up"][i], ch[f"leg_{side}_lo"][i]], [sk.thigh, sk.shin])[-1]
            feet.append((ch["x"][i] + p[0], ch["y"][i] + p[1]))
        p_next = []
        for side, hip in (("f", sk.hip_front), ("b", sk.hip_back)):
            p = fk_chain(hip, [ch[f"leg_{side}_up"][i + 1], ch[f"leg_{side}_lo"][i + 1]], [sk.thigh, sk.shin])[-1]
            p_next.append((ch["x"][i + 1] + p[0], ch["y"][i + 1] + p[1]))
        low = min(f[1] for f in p_next)
        grounded = [k for k in range(2) if p_next[k][1] <= low + 0.03]
        slips.append(min(abs(p_next[k][0] - feet[k][0]) for k in grounded))  # some grounded foot is fixed
    assert max(slips) < 0.02, max(slips)


def test_blinks_happen_and_are_deterministic():
    a = CharacterAnimator(CharacterDirection("maya", blink_seed=3), 30).bake(300)
    b = CharacterAnimator(CharacterDirection("maya", blink_seed=3), 30).bake(300)
    assert a["eye_open"] == b["eye_open"]
    assert min(a["eye_open"]) < 0.3


def test_expression_drives_mouth():
    d = CharacterDirection("maya", expressions=[{"at": 0, "name": "happy"}, {"at": 1.0, "name": "surprised"}])
    ch = CharacterAnimator(d, 30).bake(60)
    assert ch["mouth"][5] == "smile" and ch["mouth"][55] == "gasp"


def _timings():
    t, out = 0.6, []
    for d in (0.9, 2.9, 3.0, 1.2, 1.2, 3.9):
        out.append((t, t + d))
        t += d + 0.35
    return out


def test_prototype_scene_is_valid_and_bakes():
    T = _timings()
    dur = T[-1][1] + 0.75
    scene = build_scene(T, dur, [f"audio/line_{i:02d}.wav" for i in range(len(LINES))])
    assert validate_scene(scene) == []
    baked = bake_scene(scene)
    assert baked["frames"] == round(dur * 30)
    maya = baked["characters"][0]["channels"]
    assert abs(maya["x"][-1] - (-4.3)) < 0.05  # walk solved to land on its mark
    pay = next(p for p in baked["props"] if p["id"] == "paycheck")
    sk = Skeleton.load("maya")
    for i in range(0, baked["frames"], 17):  # upright constraint holds every frame
        assert joint_world(maya, i, sk, "hand_f")[2] + pay["tracks"]["rot"][i] == pytest.approx(6.0, abs=1e-2)
    assert len(foot_contacts(maya, 30)) >= 3


def test_validator_catches_errors():
    bad = Scene.model_validate({
        "scene_id": "x", "duration": 5.0, "camera": [{"t": 0, "x": 0}],
        "background": {"kind": "moonbase"},
        "characters": [{"id": "c", "character": "nobody", "actions": [
            {"type": "pose", "name": "moonwalk", "start": 1, "end": 9}]}],
        "props": [{"id": "p", "kind": "badge"}],
        "sfx": [{"t": 7, "kind": "laser"}],
        "narration": [{"text": "a", "start": 1, "end": 2, "audio": "missing.wav"},
                      {"text": "b", "start": 1.5, "end": 3}],
    })
    errs = "\n".join(validate_scene(bad, base_dir=__import__("pathlib").Path("/nonexistent")))
    for needle in ("moonbase", "nobody", "moonwalk", "outside scene", "needs a label", "laser", "overlaps",
                   "audio missing"):
        assert needle in errs, needle
