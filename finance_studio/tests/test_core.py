import json
import logging
from pathlib import Path

import pytest

from core.cache import AssetCache, stable_hash
from core.config import ConfigError, load_settings
from core.episode import Episode, slugify
from core.logging_setup import SecretScrubber
from core.pipeline import (ApprovalRequired, Context, NotImplementedStep, Pipeline, Step,
                           StepResult)
from core.progress import EpisodeState, Status
from core.retry import PermanentError, retry
from core.steps import build_pipeline

ROOT = Path(__file__).resolve().parent.parent


def test_config_loads_and_env_override(tmp_path):
    s = load_settings(ROOT / "config.yaml", env_file=tmp_path / "none",
                      environ={"FINSTUDIO__VIDEO__FPS": "24", "FINSTUDIO__TTS__ELEVENLABS__STYLE": "0.3"})
    assert s.get("video.fps") == 24
    assert s.get("tts.elevenlabs.style") == 0.3
    assert s.get("video.width") == 1920
    assert s.get("missing.key", "d") == "d"


def test_config_rejects_disabling_publish_gate(tmp_path):
    with pytest.raises(ConfigError):
        load_settings(ROOT / "config.yaml", env_file=tmp_path / "none",
                      environ={"FINSTUDIO__PIPELINE__REQUIRE_PUBLISH_APPROVAL": "false"})


def test_config_rejects_bad_video(tmp_path):
    with pytest.raises(ConfigError):
        load_settings(ROOT / "config.yaml", env_file=tmp_path / "none",
                      environ={"FINSTUDIO__VIDEO__FPS": "0"})


def test_redacted_never_contains_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-super-secret-123")
    s = load_settings(ROOT / "config.yaml", env_file=tmp_path / "none")
    dumped = json.dumps(s.redacted())
    assert "sk-super-secret-123" not in dumped
    assert s.redacted()["secrets_present"]["ELEVENLABS_API_KEY"] is True


def test_log_scrubber(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "abcdef123456")
    rec = logging.LogRecord("x", logging.INFO, "f", 1, "key is %s", ("abcdef123456",), None)
    SecretScrubber().filter(rec)
    assert "abcdef123456" not in rec.getMessage()


def test_retry_succeeds_after_failures():
    calls = {"n": 0}

    @retry(attempts=3, backoff=0, sleep=lambda _: None)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise IOError("boom")
        return "ok"

    assert flaky() == "ok" and calls["n"] == 3


def test_retry_gives_up_and_respects_permanent():
    @retry(attempts=2, backoff=0, sleep=lambda _: None)
    def always():
        raise IOError("x")

    with pytest.raises(IOError):
        always()

    n = {"c": 0}

    @retry(attempts=5, backoff=0, sleep=lambda _: None)
    def perm():
        n["c"] += 1
        raise PermanentError("bad key")

    with pytest.raises(PermanentError):
        perm()
    assert n["c"] == 1


def test_cache_roundtrip(tmp_path):
    c = AssetCache(tmp_path / "cache")
    src = tmp_path / "a.wav"
    src.write_bytes(b"data")
    key = stable_hash("tts", "hello", {"voice": 1})
    assert c.get("tts", key, ".wav") is None
    stored = c.put("tts", key, src)
    assert c.get("tts", key, ".wav") == stored
    assert stable_hash("tts", "hello", {"voice": 2}) != key


def test_slugify():
    assert slugify("Why Your First $10,000 Is the Hardest!") == "why-your-first-10-000-is-the-hardest"
    assert slugify("???") == "untitled"


def _ctx(tmp_path, options=None):
    s = load_settings(ROOT / "config.yaml", env_file=tmp_path / "none")
    ep = Episode.create("Test Topic", tmp_path / "out")
    return Context(s, ep, ep.state, AssetCache(tmp_path / "c"), options or {})


def test_pipeline_resume_and_invalidation(tmp_path):
    runs = []

    def a(ctx):
        runs.append("a")
        p = ctx.episode.p("script", "a.txt")
        p.write_text(f"run {len(runs)}")  # content changes each run
        return StepResult([p])

    def b(ctx):
        runs.append("b")
        return StepResult([])

    pipe = Pipeline([Step("a", "A", a), Step("b", "B", b, ("a",))])
    ctx = _ctx(tmp_path)
    assert pipe.run(ctx)
    assert pipe.run(ctx)  # everything fresh -> skipped
    assert runs == ["a", "b"]
    ctx.episode.p("script", "a.txt").unlink()  # missing output -> re-run
    pipe.run(ctx)
    assert runs == ["a", "b", "a", "b"]
    ctx2 = _ctx(tmp_path, options={"a": {"variant": 2}})  # changed input -> re-run downstream too
    pipe.run(ctx2)
    assert runs[-2:] == ["a", "b"]
    state = EpisodeState(ctx.episode.p("state.json"))
    assert state.record("b").status == Status.DONE


def test_pipeline_records_failures_and_todo(tmp_path):
    def boom(ctx):
        raise ValueError("bad")

    def todo(ctx):
        raise NotImplementedStep("later")

    ctx = _ctx(tmp_path)
    assert not Pipeline([Step("x", "X", boom)]).run(ctx)
    assert ctx.state.record("x").status == Status.FAILED
    assert not Pipeline([Step("y", "Y", todo)]).run(ctx)
    assert ctx.state.record("y").status == Status.NOT_IMPLEMENTED


def test_pipeline_rejects_bad_dependency_order():
    with pytest.raises(ValueError):
        Pipeline([Step("b", "B", lambda c: StepResult(), ("a",)), Step("a", "A", lambda c: StepResult())])


def test_publish_is_gated(tmp_path):
    from core.steps import publish
    ctx = _ctx(tmp_path)
    with pytest.raises(ApprovalRequired):
        publish(ctx)


def test_full_pipeline_definition_is_valid():
    names = [s.name for s in build_pipeline().steps]
    assert names[0] == "research" and names[-1] == "publish"
    assert len(names) == 15
