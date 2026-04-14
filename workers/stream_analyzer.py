# -*- coding: utf-8 -*-
"""OTT Monitor - Stream Analysis Engine"""
import asyncio, json, logging, random, time
from dataclasses import dataclass, field
from typing import List, Optional
from config import settings
from db.models import ErrorSeverity, ErrorType

logger = logging.getLogger(__name__)

@dataclass
class StreamAnalysisResult:
    stream_url: str; is_available: bool = False; response_time_ms: int = 0
    bitrate_kbps: Optional[int] = None; resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None; fps: Optional[float] = None
    codec_video: Optional[str] = None; video_jitter_ms: Optional[float] = None
    codec_audio: Optional[str] = None; audio_level_dbfs: Optional[float] = None
    audio_sample_rate: Optional[int] = None; segment_duration: Optional[float] = None
    detected_errors: List[dict] = field(default_factory=list)
    raw_output: Optional[str] = None; error_message: Optional[str] = None
    def add_error(self, error_type, severity, message):
        self.detected_errors.append({"error_type": error_type, "severity": severity, "message": message})

async def analyze_stream(stream_url: str) -> StreamAnalysisResult:
    if settings.SIMULATE_MODE: return _simulate_stream_analysis(stream_url)
    return await _run_ffprobe(stream_url)

async def _run_ffprobe(stream_url: str) -> StreamAnalysisResult:
    result = StreamAnalysisResult(stream_url=stream_url)
    start  = time.monotonic()
    cmd    = ["ffprobe","-v","quiet","-print_format","json","-show_streams","-show_format",
               "-timeout", str(settings.WORKER_TIMEOUT * 1_000_000), "-i", stream_url]
    try:
        proc = await asyncio.wait_for(asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE), timeout=settings.WORKER_TIMEOUT+5)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=settings.WORKER_TIMEOUT+5)
        result.response_time_ms = int((time.monotonic()-start)*1000)
        if proc.returncode != 0:
            result.is_available = False; result.error_message = stderr.decode(errors="replace")[:500]
            result.add_error(ErrorType.STREAM_DOWN, ErrorSeverity.CRITICAL, f"ffprobe exited {proc.returncode}")
            return result
        data = json.loads(stdout.decode()); result.is_available = True
        _parse_ffprobe_output(result, data); _detect_quality_issues(result)
    except asyncio.TimeoutError:
        result.is_available = False; result.response_time_ms = settings.WORKER_TIMEOUT*1000
        result.add_error(ErrorType.STREAM_DOWN, ErrorSeverity.CRITICAL, f"Stream timed out after {settings.WORKER_TIMEOUT}s")
    except FileNotFoundError:
        result.is_available = False; logger.error("ffprobe not found")
        result.add_error(ErrorType.STREAM_DOWN, ErrorSeverity.CRITICAL, "ffprobe not installed")
    except Exception as e:
        result.is_available = False; result.error_message = str(e)
        result.add_error(ErrorType.STREAM_DOWN, ErrorSeverity.CRITICAL, f"Analysis failed: {e}")
    return result

def _parse_ffprobe_output(result, data):
    fmt = data.get("format", {})
    if "bit_rate" in fmt: result.bitrate_kbps = int(fmt["bit_rate"]) // 1000
    if "duration" in fmt: result.segment_duration = float(fmt["duration"])
    for stream in data.get("streams", []):
        ct = stream.get("codec_type","")
        if ct == "video":
            result.codec_video = stream.get("codec_name"); result.resolution_width = stream.get("width"); result.resolution_height = stream.get("height")
            try:
                n,d = stream.get("avg_frame_rate","0/1").split("/"); result.fps = round(int(n)/int(d),2) if int(d) else None
            except: result.fps = None
            if not result.bitrate_kbps and "bit_rate" in stream: result.bitrate_kbps = int(stream["bit_rate"])//1000
        elif ct == "audio":
            result.codec_audio = stream.get("codec_name"); result.audio_sample_rate = int(stream.get("sample_rate",0)) or None

def _detect_quality_issues(result):
    if not result.is_available: return
    if result.bitrate_kbps and result.bitrate_kbps < 100:
        result.add_error(ErrorType.BITRATE_DROP, ErrorSeverity.WARNING, f"Bitrate very low: {result.bitrate_kbps} kbps")
    if result.response_time_ms > settings.RESPONSE_TIME_THRESHOLD:
        result.add_error(ErrorType.HIGH_LATENCY, ErrorSeverity.INFO, f"High response time: {result.response_time_ms}ms")
    if not result.codec_video:
        result.add_error(ErrorType.STREAM_DOWN, ErrorSeverity.CRITICAL, "No video stream found")
    if not result.codec_audio:
        result.add_error(ErrorType.AUDIO_SILENCE, ErrorSeverity.MAJOR, "No audio stream found")

_STREAM_STATE: dict = {}

def _get_or_init_state(stream_url):
    if stream_url not in _STREAM_STATE:
        rng = random.Random(hash(stream_url))
        w,h = rng.choice([(1920,1080),(1280,720),(854,480),(3840,2160)])
        _STREAM_STATE[stream_url] = {
            "base_bitrate": rng.uniform(1500,6000), "base_latency": rng.uniform(100,800),
            "width":w,"height":h,"fps":rng.choice([23.98,25.0,29.97,50.0,59.94]),
            "vcodec":rng.choice(["h264","h265","av1"]),"acodec":rng.choice(["aac","mp3","ac3"]),
            "force_down":False,"down_count":0,
        }
    return _STREAM_STATE[stream_url]

def _simulate_stream_analysis(stream_url):
    result = StreamAnalysisResult(stream_url=stream_url)
    state  = _get_or_init_state(stream_url)
    if random.random() < 0.05 or state["force_down"]:
        result.is_available = False; result.response_time_ms = random.randint(8000,15000)
        result.add_error(ErrorType.STREAM_DOWN, ErrorSeverity.CRITICAL, "Simulated stream timeout")
        state["down_count"] = state.get("down_count",0)+1
        state["force_down"] = state["down_count"] < random.randint(1,3); return result
    state["force_down"] = False; state["down_count"] = 0; result.is_available = True
    drift = random.uniform(-50,50); state["base_bitrate"] = max(500,min(8000,state["base_bitrate"]+drift))
    result.bitrate_kbps = int(state["base_bitrate"]+random.gauss(0,20))
    result.resolution_width=state["width"]; result.resolution_height=state["height"]
    result.fps=state["fps"]+random.uniform(-0.5,0.5); result.codec_video=state["vcodec"]; result.codec_audio=state["acodec"]
    result.audio_level_dbfs=round(random.uniform(-30,-3),1); result.audio_sample_rate=48000
    result.response_time_ms=max(50,int(random.gauss(state["base_latency"],50)))
    result.video_jitter_ms=round(random.uniform(0,20),2); result.segment_duration=round(random.uniform(5.8,6.2),3)
    if random.random() < 0.10:
        issue = random.choice([
            (ErrorType.VIDEO_FREEZE,ErrorSeverity.MAJOR,"Simulated video freeze"),
            (ErrorType.AUDIO_SILENCE,ErrorSeverity.MAJOR,"Simulated audio silence"),
            (ErrorType.BITRATE_DROP,ErrorSeverity.WARNING,"Simulated bitrate drop"),
            (ErrorType.VIDEO_JITTER,ErrorSeverity.CRITICAL,"Simulated video jitter"),
            (ErrorType.HLS_SEGMENT_DELAY,ErrorSeverity.WARNING,"Simulated HLS delay"),
            (ErrorType.LIP_SYNC_OUT,ErrorSeverity.WARNING,"Simulated lip sync error"),
            (ErrorType.HIGH_LATENCY,ErrorSeverity.INFO,"Simulated high latency"),
        ]); result.add_error(*issue)
    return result
