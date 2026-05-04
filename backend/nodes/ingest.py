import asyncio
import os
import time
import yt_dlp

from schemas import PipelineState
from utils.progress import emit, ProgressEvent, progress_queue
from utils.logger import get_logger
from utils.engagement import parse_description_timestamps

log = get_logger("nodes.ingest")


async def ingest_node(state: PipelineState) -> dict:
    log.info(f"[{state.job_id[:8]}] INGEST start | url={state.youtube_url}")
    await emit(ProgressEvent(type="node_start", node="ingest", message="Downloading video...", progress=0))

    job_dir = f"tmp/jobs/{state.job_id}"
    os.makedirs(job_dir, exist_ok=True)

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
        "format": "best[height<=720][ext=mp4]/best[height<=720]/best",
        "outtmpl": os.path.join(job_dir, "video.%(ext)s"),
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
        "subtitlesformat": "vtt",
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_progress_hook],
        # Use the Android player client to bypass bot-detection without cookies.
        # Falls back to web if android is unavailable for the specific video.
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }

    # Optional: path to a Netscape-format cookies.txt exported from a logged-in
    # browser session. Set YTDL_COOKIES_FILE in .env for production deployments.
    cookies_file = os.getenv("YTDL_COOKIES_FILE", "").strip()
    if cookies_file and os.path.exists(cookies_file):
        ydl_opts["cookiefile"] = cookies_file
        log.info(f"[{state.job_id[:8]}] INGEST using cookies file: {cookies_file}")

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(state.youtube_url, download=True)

    t0 = time.time()
    info = await loop.run_in_executor(None, _download)

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
