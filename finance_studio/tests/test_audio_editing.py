import numpy as np
import pytest

from audio import mixer, synth
from editing.subtitles import build_srt, split_cues


def test_layout_lines_spacing():
    t = mixer.layout_lines([1.0, 2.0, 0.5], lead=0.5, gaps=[0.3, 0.4])
    assert t == [(0.5, 1.5), (1.8, 3.8), (4.2, 4.7)]


def test_music_and_sfx_are_generated_and_finite():
    m = synth.music_bed([{"start": 0, "end": 2, "chords": ["Cmaj7"], "mood": "hopeful"},
                         {"start": 2, "end": 4, "chords": ["Am"], "mood": "tension"}], 4.0)
    assert m.shape[1] == 2 and len(m) >= 4 * synth.SR and np.isfinite(m).all() and np.abs(m).max() > 0
    for k in synth.SFX_KINDS:
        x = synth.sfx(k)
        assert np.isfinite(x).all() and np.abs(x).max() > 0, k
    with pytest.raises(ValueError):
        synth.sfx("airhorn")


def test_ducking_lowers_music_under_voice():
    sr = synth.SR
    narr = np.zeros(sr * 4)
    narr[sr: 2 * sr] = 0.5 * np.sin(np.arange(sr) * 2 * np.pi * 200 / sr)
    music = np.full((sr * 4, 2), 0.5)
    out = mixer.mix(narr, music, np.zeros((sr * 4, 2)), music_gain_db=-20, duck_db=-10)
    quiet_part = np.abs(out[int(3.5 * sr):, 0]).mean()
    under_voice_music = np.abs(out[int(1.5 * sr): int(1.6 * sr), 0] - out[int(1.5 * sr): int(1.6 * sr), 0].mean())
    assert quiet_part > 0
    env = mixer.envelope(narr)
    assert env[int(1.5 * sr)] > env[int(3.5 * sr)]


def test_hz():
    assert synth.hz("A4") == pytest.approx(440.0)
    assert synth.hz("C4") == pytest.approx(261.63, abs=0.01)


def test_srt_format_and_wrapping():
    srt = build_srt([{"text": "Meet Maya.", "start": 0.6, "end": 1.44},
                     {"text": "And by the end of the month, that raise has quietly disappeared and nobody noticed "
                              "where it went at all.", "start": 11.5, "end": 16.0}])
    assert srt.startswith("1\n00:00:00,600 --> 00:00:01,440\nMeet Maya.\n")
    for block in srt.strip().split("\n\n"):
        text_lines = block.split("\n")[2:]
        assert len(text_lines) <= 2 and all(len(l) <= 42 for l in text_lines)


def test_split_cues_cover_the_line():
    cues = split_cues("word " * 40, 1.0, 9.0)
    assert cues[0][0] == 1.0 and cues[-1][1] == pytest.approx(9.0)
