import numpy as np
import pytest

from app.services.audio_analysis import analyse_samples, host_allowed

SR = 22050


def click_track(bpm=120, seconds=30):
    y = np.zeros(SR * seconds, dtype=np.float32)
    step = int(SR * 60 / bpm)
    t = np.arange(int(0.05 * SR)) / SR
    burst = (np.sin(2 * np.pi * 1000 * t) * np.exp(-t * 60)).astype(np.float32)
    for i in range(0, y.size - burst.size, step):
        y[i:i + burst.size] += burst
    return y


def chord(freqs, seconds=12):
    t = np.arange(SR * seconds) / SR
    return sum(np.sin(2 * np.pi * f * t) for f in freqs).astype(np.float32) / len(freqs)


def test_bpm_detected_close():
    res = analyse_samples(click_track(120), SR)
    assert res["bpm"] is not None and abs(res["bpm"] - 120) <= 3


def test_key_c_major_triad():
    res = analyse_samples(chord([261.63, 329.63, 392.00]), SR)
    assert res["key"] == "8B"  # C major in Camelot


def test_highlight_is_estimated_and_finds_loud_section():
    y = np.concatenate([0.05 * chord([220], 40), 0.9 * chord([220, 330], 30), 0.05 * chord([220], 30)])
    h = analyse_samples(y, SR)["highlight"]
    assert h["source"] == "estimated"  # never claimed as 'most popular'
    assert 38 <= h["in_sec"] <= 52 and h["out_sec"] > h["in_sec"]


def test_short_audio_returns_none_not_guess():
    res = analyse_samples(np.zeros(SR * 2, dtype=np.float32), SR)
    assert res["bpm"] is None and res["key"] is None and res["highlight"] is None


def test_waveform_shape():
    wf = analyse_samples(click_track(100, 20), SR)["waveform"]
    assert len(wf) == 120 and max(wf) == 1.0


@pytest.mark.parametrize("url,ok", [
    ("https://prod-1.storage.jamendo.com/?trackid=1", True),
    ("http://prod-1.storage.jamendo.com/x", False),
    ("https://evil.com/jamendo.com", False),
    ("https://jamendo.com.evil.com/x", False),
    ("file:///etc/passwd", False),
    ("https://169.254.169.254/latest", False),
])
def test_analysis_host_allowlist_blocks_ssrf(url, ok):
    assert host_allowed(url) is ok


def test_test_host_is_ignored_outside_test_env(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "TEST_AUDIO_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert host_allowed("http://127.0.0.1/a.mp3") is False
    monkeypatch.setattr(settings, "APP_ENV", "test")
    assert host_allowed("http://127.0.0.1/a.mp3") is True
