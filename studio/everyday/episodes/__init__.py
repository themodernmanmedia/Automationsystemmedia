"""Episode registry."""
from importlib import import_module

EPISODES = {
    "ignore-everyone-30-days": "everyday.episodes.ignore_everyone_30_days",
}


def load(slug: str):
    if slug not in EPISODES:
        raise SystemExit(f"unknown episode {slug!r}; choose from {', '.join(EPISODES)}")
    return import_module(EPISODES[slug]).EPISODE
