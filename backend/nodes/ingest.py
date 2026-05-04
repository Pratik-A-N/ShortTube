import asyncio
import base64
import os
import shutil
import tempfile
import time
import yt_dlp

from schemas import PipelineState
from utils.progress import emit, ProgressEvent, progress_queue
from utils.logger import get_logger
from utils.engagement import parse_description_timestamps

log = get_logger("nodes.ingest")

# Absolute path to the bundled demo assets (baked into the Docker image).
_DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "demo")


async def _ingest_demo(state: PipelineState, job_dir: str) -> dict:
    """Skip yt-dlp entirely and use the pre-bundled demo video + captions."""
    demo_video = os.path.join(_DEMO_DIR, "video.mp4")
    demo_vtt = os.path.join(_DEMO_DIR, "captions.en.vtt")

    if not os.path.exists(demo_video) or not os.path.exists(demo_vtt):
        raise FileNotFoundError(
            f"Demo assets missing in {_DEMO_DIR}. "
            "Ensure demo/video.mp4 and demo/captions.en.vtt are present in the image."
        )

    video_path = os.path.join(job_dir, "video.mp4")
    vtt_path = os.path.join(job_dir, "captions.en.vtt")
    shutil.copy2(demo_video, video_path)
    shutil.copy2(demo_vtt, vtt_path)

    log.info(f"[{state.job_id[:8]}] INGEST demo mode — using bundled assets")
    await emit(ProgressEvent(
        type="node_complete",
        node="ingest",
        message="Loaded demo video (Inside the Mind of a Master Procrastinator — Tim Urban)",
        progress=100,
    ))

    return {
        "video_path": video_path,
        "vtt_path": vtt_path,
        "duration_sec": 843.0,
        "video_title": "Inside the Mind of a Master Procrastinator | Tim Urban | TED",
        "heatmap": [],
        "chapters": [],
        "description_timestamps": [],
    }


async def ingest_node(state: PipelineState) -> dict:
    log.info(f"[{state.job_id[:8]}] INGEST start | url={state.youtube_url}")
    await emit(ProgressEvent(type="node_start", node="ingest", message="Downloading video...", progress=0))

    job_dir = f"tmp/jobs/{state.job_id}"
    os.makedirs(job_dir, exist_ok=True)

    if os.getenv("USE_DEMO_VIDEO", "").strip().lower() == "true":
        return await _ingest_demo(state, job_dir)

    loop = asyncio.get_event_loop()
    queue = progress_queue.get(None)
    last_pct = [-1]

    def _progress_hook(d):
        if d["status"] != "downloading" or queue is None:
            return
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        if total <= 0:
            return
        pct = int(d.get("downloaded_bytes", 0) / total * 100)
        if pct >= last_pct[0] + 5:
            last_pct[0] = pct
            event = ProgressEvent(
                type="node_start",
                node="ingest",
                message=f"Downloading... {pct}%",
                progress=pct,
            )
            loop.call_soon_threadsafe(queue.put_nowait, event)

    ydl_opts = {
        "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(job_dir, "video.%(ext)s"),
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
        "subtitlesformat": "vtt",
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_progress_hook],
        "extractor_args": {"youtube": {"player_client": ["web_creator", "tv_embedded", "android", "web"]}},
        "sleep_interval_requests": 1,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
        },
    }

    # Residential proxy — routes around YouTube's datacenter IP blocklist.
    # Set YTDLP_PROXY in Render env vars: http://user:pass@host:port
    proxy = os.getenv("YTDLP_PROXY", "").strip()
    if proxy:
        ydl_opts["proxy"] = proxy
        log.info(f"[{state.job_id[:8]}] INGEST using proxy")

    # Cookies support — two options (B64 env var takes priority):
    # 1. YTDL_COOKIES_B64: base64-encoded cookies.txt — works on any host (no secret files needed)
    # 2. YTDL_COOKIES_FILE: path to cookies.txt on disk — for local dev or Render paid plan
    _cookies_tmp = None
    cookies_b64 = os.getenv("YTDL_COOKIES_B64", "").strip()
    cookies_file = os.getenv("YTDL_COOKIES_FILE", "").strip()

    if cookies_b64:
        _cookies_tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        _cookies_tmp.write(base64.b64decode(cookies_b64).decode("utf-8"))
        _cookies_tmp.flush()
        ydl_opts["cookiefile"] = _cookies_tmp.name
        log.info(f"[{state.job_id[:8]}] INGEST using cookies from YTDL_COOKIES_B64")
    elif cookies_file and os.path.exists(cookies_file):
        ydl_opts["cookiefile"] = cookies_file
        log.info(f"[{state.job_id[:8]}] INGEST using cookies file: {cookies_file}")

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(state.youtube_url, download=True)

    t0 = time.time()
    try:
        info = await loop.run_in_executor(None, _download)
    finally:
        if _cookies_tmp:
            try:
                os.unlink(_cookies_tmp.name)
            except OSError:
                pass

    title = info.get("title", "Untitled")
    duration_sec = float(info.get("duration", 0))
    video_path = os.path.join(job_dir, "video.mp4")
    video_size_mb = os.path.getsize(video_path) / (1024 * 1024) if os.path.exists(video_path) else 0
    log.info(
        f"[{state.job_id[:8]}] INGEST downloaded in {time.time()-t0:.1f}s "
        f"| title='{title}' | duration={duration_sec:.0f}s | size={video_size_mb:.1f}MB"
    )

    # --- Engagement signals ---
    raw_heatmap = info.get("heatmap") or []
    heatmap = raw_heatmap if isinstance(raw_heatmap, list) else []

    raw_chapters = info.get("chapters") or []
    chapters = raw_chapters if isinstance(raw_chapters, list) else []

    description_timestamps = parse_description_timestamps(info.get("description", ""))

    log.info(
        f"[{state.job_id[:8]}] INGEST signals — "
        f"heatmap:{len(heatmap)} ({'available' if heatmap else 'unavailable'}) "
        f"| chapters:{len(chapters)} "
        f"| desc_timestamps:{len(description_timestamps)}"
    )

    vtt_candidates = [
        os.path.join(job_dir, "video.en.vtt"),
        os.path.join(job_dir, "video.en-US.vtt"),
    ]
    vtt_path = next((p for p in vtt_candidates if os.path.exists(p)), None)

    if vtt_path and vtt_path != os.path.join(job_dir, "captions.en.vtt"):
        canonical = os.path.join(job_dir, "captions.en.vtt")
        os.rename(vtt_path, canonical)
        vtt_path = canonical

    if not vtt_path or not os.path.exists(vtt_path):
        log.error(f"[{state.job_id[:8]}] INGEST no English auto-captions found")
        await emit(ProgressEvent(
            type="error",
            node="ingest",
            message="No English auto-captions found. Please use a video with auto-captions enabled.",
        ))
        raise ValueError("No English auto-captions found")

    vtt_size_kb = os.path.getsize(vtt_path) // 1024
    log.info(f"[{state.job_id[:8]}] INGEST captions OK | vtt_size={vtt_size_kb}KB")

    await emit(ProgressEvent(
        type="node_complete",
        node="ingest",
        message=f"Downloaded '{title}' ({duration_sec:.0f}s)",
        progress=100,
    ))

    return {
        "video_path": video_path,
        "vtt_path": vtt_path,
        "duration_sec": duration_sec,
        "video_title": title,
        "heatmap": heatmap,
        "chapters": chapters,
        "description_timestamps": description_timestamps,
    }
