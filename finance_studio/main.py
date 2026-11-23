#!/usr/bin/env python3
"""Finance Studio - automated 2D animated finance documentary production.

Usage:
  python main.py --topic "Why Americans Are Getting Poorer Even When They Earn More"
  python main.py doctor                      # inspect environment
  python main.py status --topic "..."        # show per-step progress
  python main.py produce --topic "..." [--only render] [--force render] [--stop-after scenes]
  python main.py approve --topic "..."       # human approval gate for publishing
  python main.py test-scene                  # render the 15-second prototype scene
"""
from __future__ import annotations

import argparse
import sys

from core.config import ConfigError, load_settings
from core.logging_setup import get_logger, setup_logging


def _settings():
    s = load_settings()
    setup_logging(s.path("paths.logs"), s.get("logging.level", "INFO"), s.get("logging.json_file", True))
    return s


def cmd_doctor(_args) -> int:
    from core.env_check import format_report, run_checks
    _settings()
    checks = run_checks()
    print(format_report(checks))
    return 0 if all(c.ok for c in checks if c.required) else 1


def cmd_produce(args) -> int:
    from core.pipeline import make_context
    from core.steps import build_pipeline
    s = _settings()
    ctx = make_context(s, args.topic)
    get_logger("main").info("Episode workspace: %s", ctx.episode.root)
    ok = build_pipeline().run(ctx, only=args.only, force=args.force, stop_after=args.stop_after)
    _print_status(ctx.state)
    return 0 if ok else 2


def cmd_status(args) -> int:
    from core.pipeline import make_context
    s = _settings()
    _print_status(make_context(s, args.topic).state)
    return 0


def cmd_approve(args) -> int:
    from core.pipeline import approval_path, make_context
    s = _settings()
    ctx = make_context(s, args.topic)
    if ctx.state.record("package").status.value != "done":
        print("Refusing: the publishing package has not been built and reviewed yet.")
        return 1
    answer = input(f"Type the episode slug '{ctx.episode.root.name}' to approve publishing: ")
    if answer.strip() != ctx.episode.root.name:
        print("Not approved.")
        return 1
    approval_path(ctx).write_text("approved\n")
    print("Approved.")
    return 0


def cmd_test_scene(args) -> int:
    from animation.prototype import run_prototype
    s = _settings()
    out = run_prototype(s, voice=args.voice, workers=args.workers)
    print(f"Prototype scene written to {out}")
    return 0


def cmd_episode(args) -> int:
    from pathlib import Path
    from animation.director import Director
    s = _settings()
    d = Director(s, Path(args.storyboard), voice=args.voice, workers=args.workers)
    out = d.run(only=args.only)
    print(f"Episode output: {out}")
    return 0


def _print_status(state) -> None:
    print("\nStep          Status            Note")
    print("-" * 70)
    for name, status, msg in state.summary():
        print(f"{name:<13} {status:<17} {msg[:60]}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="finance_studio", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--topic", help="shorthand for: produce --topic ...")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    pr = sub.add_parser("produce")
    pr.add_argument("--topic", required=True)
    pr.add_argument("--only", nargs="*")
    pr.add_argument("--force", nargs="*", help="re-run these steps even if up to date")
    pr.add_argument("--stop-after")
    pr.set_defaults(fn=cmd_produce)
    st = sub.add_parser("status")
    st.add_argument("--topic", required=True)
    st.set_defaults(fn=cmd_status)
    ap = sub.add_parser("approve")
    ap.add_argument("--topic", required=True)
    ap.set_defaults(fn=cmd_approve)
    ts = sub.add_parser("test-scene")
    ts.add_argument("--voice", default=None, help="TTS provider override (elevenlabs|espeak|file:<dir>)")
    ts.add_argument("--workers", type=int, default=2, help="parallel Blender processes")
    ts.set_defaults(fn=cmd_test_scene)
    ep = sub.add_parser("episode", help="render a full episode from a storyboard")
    ep.add_argument("storyboard", help="path to storyboard.py")
    ep.add_argument("--voice", default=None)
    ep.add_argument("--workers", type=int, default=2)
    ep.add_argument("--only", nargs="*", help="render only these scene ids")
    ep.set_defaults(fn=cmd_episode)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd is None:
        if not args.topic:
            build_parser().print_help()
            return 1
        args.cmd, args.fn, args.only, args.force, args.stop_after = "produce", cmd_produce, None, None, None
    try:
        return args.fn(args)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
