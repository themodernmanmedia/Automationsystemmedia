"""Episode registry."""
from importlib import import_module

EPISODES = {
    "ignore-everyone-30-days": "everyday.episodes.ignore_everyone_30_days",
    "last-to-leave-circle": "everyday.episodes.last_to_leave_circle",
    "last-to-leave-circle-3d": "everyday.episodes.last_to_leave_circle_3d",
}


def load(slug: str):
    if slug not in EPISODES:
        raise SystemExit(f"unknown episode {slug!r}; choose from {', '.join(EPISODES)}")
    return import_module(EPISODES[slug]).EPISODE
