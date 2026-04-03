"""
OTT Monitor - Stream Analysis Engine
Uses ffprobe to extract QoS/QoE metrics from HLS/DASH streams.
Falls back to simulation when SIMULATE_MODE=True.
"""

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional

from config import settings
from db.models import ErrorSeverity, ErrorType

logger = logging.getLogger(__name__)


@dataclass
class StreamAnalysisResult:
    """Raw ffprobe analysis output for a single stream check."""
    stream_url: str
    is_available: bool = False
    response_time_ms: int = 0

    # Video
    bitrate_kbps: Optional[int] = None
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None
    fps: Optional[float] = None
    codec_video: Optional[str] = None
    video_jitter_ms: Optional[float] = None

    # Audio
    codec_audio: Optional[str] = None
    audio_level_dbfs: Optional[float] = None
    audio_sample_rate: Optional[int] = None

    # HLS specific
    segment_duration: Optional[float] = None

    # Quality events detected
    detected_errors: List[dict] = field(default_factory=list)
    raw_output: Optional[str] = None
    error_message: Optional[str] = None

    def add_error(self, error_type: ErrorType, severity: ErrorSeverity, message: str):
        self.detected_errors.append({
            "error_type": error_type,
            "severity": severity,
            "message": message,
        })


async def analyze_stream(stream_url: str) -> StreamAnalysisResult:
    """
    Analyze a stream using ffprobe.
    If SIMULATE_MODE is True, returns realistic simulated data.
    """
    if settings.SIMULATE_MODE:
        return _simulate_stream_analysis(stream_url)

    return await _run_ffprobe(stream_url)


async def _run_ffprobe(stream_url: str) -> StreamAnalysisResult:
    """Execute ffprobe and parse its JSON output."""
    result = StreamAnalysisResult(stream_url=stream_url)
    start = time.monotonic()

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        "-timeout", str(settings.WORKER_TIMEOUT * 1_000_000),  # microseconds
        "-i", stream_url,
    ]

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=settings.WORKER_TIMEOUT + 5,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=settings.WORKER_TIMEOUT + 5,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        result.response_time_ms = elapsed_ms

        if proc.returncode != 0:
            result.is_available = False
            result.error_message = stderr.decode(errors="replace")[:500]
            result.add_error(
                ErrorType.STREAM_DOWN,
                ErrorSeverity.CRITICAL,
                f"ffprobe exited with code {proc.returncode}",
            )
            return result

        data = json.loads(stdout.decode())
        result.is_available = True
        result.raw_output = stdout.decode()

        _parse_ffprobe_output(result, data)
        _detect_quality_issues(result)

    except asyncio.TimeoutError:
        result.is_available = False
        result.response_time_ms = settings.WORKER_TIMEOUT * 1000
        result.error_message = "ffprobe timed out"
        result.add_error(
            ErrorType.STREAM_DOWN,
            ErrorSeverity.CRITICAL,
            f"Stream timed out after {settings.WORKER_TIMEOUT}s",
        )
    except FileNotFoundError:
        result.is_available = False
        result.error_message = "ffprobe not found — install ffmpeg"
        logger.error("ffprobe binary not found. Install ffmpeg.")
        result.add_error(
            ErrorType.STREAM_DOWN,
            ErrorSeverity.CRITICAL,
            "ffprobe not installed",
        )
    except Exception as e:
        result.is_available = False
        result.error_message = str(e)
        result.add_error(
            ErrorType.STREAM_DOWN,
            ErrorSeverity.CRITICAL,
            f"Analysis failed: {e}",
        )
        logger.exception(f"ffprobe analysis failed for {stream_url}")

    return result


def _parse_ffprobe_output(result: StreamAnalysisResult, data: dict) -> None:
    """Parse ffprobe JSON output and populate result fields."""
    fmt = data.get("format", {})
    streams = data.get("streams", [])

    # Overall bitrate from format
    if "bit_rate" in fmt:
        result.bitrate_kbps = int(fmt["bit_rate"]) // 1000

    # Segment duration (for HLS)
    if "duration" in fmt:
        result.segment_duration = float(fmt["duration"])

    for stream in streams:
        codec_type = stream.get("codec_type", "")

        if codec_type == "video":
            result.codec_video = stream.get("codec_name")
            result.resolution_width = stream.get("width")
            result.resolution_height = stream.get("height")

            # Parse FPS from avg_frame_rate "30/1"
            fps_str = stream.get("avg_frame_rate", "0/1")
            try:
                num, den = fps_str.split("/")
                result.fps = round(int(num) / int(den), 2) if int(den) else None
            except Exception:
                result.fps = None

            # Use stream-level bitrate if format didn't have it
            if not result.bitrate_kbps and "bit_rate" in stream:
                result.bitrate_kbps = int(stream["bit_rate"]) // 1000

        elif codec_type == "audio":
            result.codec_audio = stream.get("codec_name")
            result.audio_sample_rate = int(stream.get("sample_rate", 0)) or None


def _detect_quality_issues(result: StreamAnalysisResult) -> None:
    """Analyze parsed metrics and generate quality error events."""
    if not result.is_available:
        return

    # Bitrate sanity check
    if result.bitrate_kbps is not None and result.bitrate_kbps < 100:
        result.add_error(
            ErrorType.BITRATE_DROP,
            ErrorSeverity.WARNING,
            f"Bitrate very low: {result.bitrate_kbps} kbps",
        )

    # High response time
    if result.response_time_ms > settings.RESPONSE_TIME_THRESHOLD:
        result.add_error(
            ErrorType.HIGH_LATENCY,
            ErrorSeverity.INFO,
            f"High response time: {result.response_time_ms}ms",
        )

    # No video stream
    if not result.codec_video:
        result.add_error(
            ErrorType.STREAM_DOWN,
            ErrorSeverity.CRITICAL,
            "No video stream found in ffprobe output",
        )

    # No audio stream
    if not result.codec_audio:
        result.add_error(
            ErrorType.AUDIO_SILENCE,
            ErrorSeverity.MAJOR,
            "No audio stream found",
        )


# ── Simulation ─────────────────────────────────────────────────────────────────

_STREAM_STATE: dict[str, dict] = {}  # Persistent state for simulated streams


def _simulate_stream_analysis(stream_url: str) -> StreamAnalysisResult:
    """
    Generate realistic simulated stream data for testing without real streams.
    Uses per-stream state to simulate realistic degradation patterns.
    """
    result = StreamAnalysisResult(stream_url=stream_url)
    state = _get_or_init_state(stream_url)

    # 5% chance the stream goes down
    if random.random() < 0.05 or state["force_down"]:
        result.is_available = False
        result.response_time_ms = random.randint(8000, 15000)
        result.add_error(ErrorType.STREAM_DOWN, ErrorSeverity.CRITICAL, "Simulated stream timeout")
        state["down_count"] = state.get("down_count", 0) + 1
        state["force_down"] = state["down_count"] < random.randint(1, 3)
        return result

    state["force_down"] = False
    state["down_count"] = 0
    result.is_available = True

    # Gradually drift bitrate up/down for realism
    base_bitrate = state["base_bitrate"]
    drift = random.uniform(-50, 50)
    state["base_bitrate"] = max(500, min(8000, base_bitrate + drift))
    result.bitrate_kbps = int(state["base_bitrate"] + random.gauss(0, 20))

    # Resolution
    result.resolution_width = state["width"]
    result.resolution_height = state["height"]
    result.fps = state["fps"] + random.uniform(-0.5, 0.5)

    # Codecs
    result.codec_video = state["vcodec"]
    result.codec_audio = state["acodec"]

    # Audio level fluctuations
    result.audio_level_dbfs = round(random.uniform(-30, -3), 1)
    result.audio_sample_rate = 48000

    # Response time
    result.response_time_ms = int(random.gauss(state["base_latency"], 50))
    result.response_time_ms = max(50, result.response_time_ms)

    # Video jitter
    result.video_jitter_ms = round(random.uniform(0, 20), 2)

    # Segment duration (HLS)
    result.segment_duration = round(random.uniform(5.8, 6.2), 3)

    # Occasional quality issues (10% chance of some issue)
    if random.random() < 0.10:
        _inject_simulated_issue(result)

    return result


def _inject_simulated_issue(result: StreamAnalysisResult) -> None:
    """Randomly inject a quality issue for simulation variety."""
    issue = random.choice([
        (ErrorType.VIDEO_FREEZE, ErrorSeverity.MAJOR, "Simulated video freeze detected"),
        (ErrorType.AUDIO_SILENCE, ErrorSeverity.MAJOR, "Simulated audio silence > 60s"),
        (ErrorType.BITRATE_DROP, ErrorSeverity.WARNING, "Simulated bitrate drop below threshold"),
        (ErrorType.VIDEO_JITTER, ErrorSeverity.CRITICAL, "Simulated excessive video jitter"),
        (ErrorType.HLS_SEGMENT_DELAY, ErrorSeverity.WARNING, "Simulated HLS segment delay"),
        (ErrorType.LIP_SYNC_OUT, ErrorSeverity.WARNING, "Simulated audio/video lip sync error"),
        (ErrorType.HIGH_LATENCY, ErrorSeverity.INFO, "Simulated high latency event"),
    ])
    result.add_error(*issue)


def _get_or_init_state(stream_url: str) -> dict:
    """Initialize or retrieve persistent simulation state for a stream URL."""
    if stream_url not in _STREAM_STATE:
        rng = random.Random(hash(stream_url))  # Deterministic seed per URL
        resolutions = [(1920, 1080), (1280, 720), (854, 480), (3840, 2160)]
        w, h = rng.choice(resolutions)
        _STREAM_STATE[stream_url] = {
            "base_bitrate": rng.uniform(1500, 6000),
            "base_latency": rng.uniform(100, 800),
            "width": w,
            "height": h,
            "fps": rng.choice([23.98, 25.0, 29.97, 50.0, 59.94]),
            "vcodec": rng.choice(["h264", "h265", "av1"]),
            "acodec": rng.choice(["aac", "mp3", "ac3"]),
            "force_down": False,
            "down_count": 0,
        }
    return _STREAM_STATE[stream_url]
