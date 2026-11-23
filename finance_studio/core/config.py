"""Configuration: config.yaml + .env + FINSTUDIO__SECTION__KEY overrides.

Secrets are read from the environment only, never from config.yaml, and are
never logged (see ``Settings.redacted``).
"""
from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PREFIX = "FINSTUDIO__"
SECRET_KEYS = (
    "ELEVENLABS_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "FRED_API_KEY",
    "BLS_API_KEY",
)


class ConfigError(RuntimeError):
    pass


def _coerce(value: str) -> Any:
    """Parse an env override with YAML rules so '30' -> 30, 'true' -> True."""
    try:
        return yaml.safe_load(value)
    except yaml.YAMLError:
        return value


def _apply_env_overrides(data: dict, environ: dict[str, str]) -> dict:
    out = deepcopy(data)
    for key, raw in environ.items():
        if not key.startswith(ENV_PREFIX):
            continue
        parts = [p.lower() for p in key[len(ENV_PREFIX):].split("__") if p]
        if not parts:
            continue
        node = out
        for p in parts[:-1]:
            node = node.setdefault(p, {})
            if not isinstance(node, dict):
                raise ConfigError(f"Override {key} targets a non-section value")
        node[parts[-1]] = _coerce(raw)
    return out


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # minimal fallback parser
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        return
    load_dotenv(path, override=False)


class Settings:
    """Thin, dotted-path access wrapper around the merged config dict."""

    def __init__(self, data: dict, root: Path = PROJECT_ROOT):
        self._data = data
        self.root = root

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def require(self, dotted: str) -> Any:
        sentinel = object()
        val = self.get(dotted, sentinel)
        if val is sentinel:
            raise ConfigError(f"Missing required config value: {dotted}")
        return val

    def path(self, dotted: str) -> Path:
        p = Path(self.require(dotted))
        return p if p.is_absolute() else self.root / p

    @staticmethod
    def secret(name: str) -> str | None:
        val = os.environ.get(name)
        return val or None

    def redacted(self) -> dict:
        """Config plus a presence map of secrets - values are never exposed."""
        return {
            "config": deepcopy(self._data),
            "secrets_present": {k: bool(os.environ.get(k)) for k in SECRET_KEYS},
        }

    @property
    def data(self) -> dict:
        return deepcopy(self._data)


def load_settings(
    config_path: Path | None = None,
    env_file: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Settings:
    config_path = config_path or PROJECT_ROOT / "config.yaml"
    _load_dotenv(env_file or PROJECT_ROOT / ".env")
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")
    with config_path.open() as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError("config.yaml must contain a mapping at the top level")
    data = _apply_env_overrides(data, dict(os.environ if environ is None else environ))
    _validate(data)
    return Settings(data, root=config_path.parent)


def _validate(data: dict) -> None:
    v = data.get("video", {})
    for key in ("width", "height", "fps"):
        if not isinstance(v.get(key), int) or v[key] <= 0:
            raise ConfigError(f"video.{key} must be a positive integer")
    if data.get("pipeline", {}).get("require_publish_approval") is not True:
        raise ConfigError("pipeline.require_publish_approval must stay true")
