"""
Tests for the stream analyzer and monitoring worker logic.
"""

import pytest
from workers.stream_analyzer import (
    StreamAnalysisResult,
    _simulate_stream_analysis,
    _get_or_init_state,
    analyze_stream,
)
from db.models import ErrorSeverity, ErrorType
from config import settings


@pytest.mark.asyncio
async def test_simulate_returns_result():
    """Simulated analysis should always return a StreamAnalysisResult."""
    result = _simulate_stream_analysis("https://test.example.com/stream.m3u8")
    assert isinstance(result, StreamAnalysisResult)


@pytest.mark.asyncio
async def test_simulate_available_stream():
    """Most simulated streams should be available (statistically)."""
    available_count = 0
    for i in range(20):
        url = f"https://test.example.com/stream{i}.m3u8"
        result = _simulate_stream_analysis(url)
        if result.is_available:
            available_count += 1
    # At least 14/20 should be available (5% down rate)
    assert available_count >= 14


@pytest.mark.asyncio
async def test_simulate_has_metrics_when_up():
    """Available streams must have bitrate and resolution populated."""
    # Run multiple times to avoid the 5% down chance
    for _ in range(10):
        result = _simulate_stream_analysis("https://stable.example.com/live.m3u8")
        if result.is_available:
            assert result.bitrate_kbps is not None
            assert result.bitrate_kbps > 0
            assert result.resolution_width is not None
            assert result.resolution_height is not None
            assert result.fps is not None
            assert result.codec_video is not None
            break


@pytest.mark.asyncio
async def test_simulate_down_stream_has_error():
    """Down streams must include a STREAM_DOWN error."""
    # Force a known-down URL by exhausting its down state
    url = "https://forced-down.example.com/stream.m3u8"
    state = _get_or_init_state(url)
    state["force_down"] = True

    result = _simulate_stream_analysis(url)
    assert result.is_available is False
    assert any(e["error_type"] == ErrorType.STREAM_DOWN for e in result.detected_errors)


def test_add_error_populates_list():
    result = StreamAnalysisResult(stream_url="https://test.com/stream.m3u8")
    result.add_error(ErrorType.AUDIO_SILENCE, ErrorSeverity.MAJOR, "Test error")
    assert len(result.detected_errors) == 1
    assert result.detected_errors[0]["error_type"] == ErrorType.AUDIO_SILENCE
    assert result.detected_errors[0]["severity"] == ErrorSeverity.MAJOR


def test_state_is_deterministic():
    """Same URL should always produce same initial state (deterministic seed)."""
    url = "https://deterministic.example.com/ch1.m3u8"
    state1 = _get_or_init_state(url)
    # Clear to force re-init
    from workers.stream_analyzer import _STREAM_STATE
    del _STREAM_STATE[url]
    state2 = _get_or_init_state(url)
    assert state1["width"] == state2["width"]
    assert state1["height"] == state2["height"]
    assert state1["vcodec"] == state2["vcodec"]


@pytest.mark.asyncio
async def test_analyze_stream_simulate_mode():
    """With SIMULATE_MODE=True, analyze_stream should return simulated data."""
    assert settings.SIMULATE_MODE is True  # Default in tests
    result = await analyze_stream("https://sim.example.com/stream.m3u8")
    assert isinstance(result, StreamAnalysisResult)
    assert result.stream_url == "https://sim.example.com/stream.m3u8"
