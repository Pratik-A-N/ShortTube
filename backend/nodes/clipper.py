import asyncio
import os
import time

from schemas import ClipperTask, RenderedClip
from utils.ffmpeg_utils import extract_segment_vtt, render_vertical_clip
from utils.progress import emit, ProgressEvent
from utils.logger import get_logger

log = get_logger("nodes.clipper")

# Render starter tier has 512MB RAM — cap concurrent ffmpeg processes to 1.
_ffmpeg_sem = asyncio.Semaphore(1)


async def render_one_clip(task: ClipperTask) -> dict:
    clip = task.clip
    job_dir = f"tmp/jobs/{task.job_id}"
    os.makedirs(job_dir, exist_ok=True)

    duration = clip.end_sec - clip.start_sec
    log.info(f"[{task.job_id[:8]}] CLIPPER_{clip.rank} start | '{clip.hook_title}' | {clip.start_sec:.1f}s->{clip.end_sec:.1f}s ({duration:.0f}s)")

    await emit(ProgressEvent(
        type="node_start",
        node="render_clip",
        message=f"Rendering clip {clip.rank}: {clip.hook_title}",
    ))

    segment_vtt = os.path.join(job_dir, f"clip_{clip.rank}.vtt")
    output_path = os.path.join(job_dir, f"clip_{clip.rank}.mp4")

    extract_segment_vtt(task.vtt_path, clip.start_sec, clip.end_sec, segment_vtt)
    log.info(f"[{task.job_id[:8]}] CLIPPER_{clip.rank} VTT extracted → {segment_vtt}")

    t0 = time.time()
    async with _ffmpeg_sem:
        await asyncio.to_thread(
            render_vertical_clip, task.video_path, segment_vtt, clip.start_sec, clip.end_sec, output_path
        )
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    log.info(f"[{task.job_id[:8]}] CLIPPER_{clip.rank} ffmpeg done in {time.time()-t0:.1f}s | size={file_size_mb:.1f}MB | output={output_path}")

    rendered = RenderedClip(
        rank=clip.rank,
        file_path=output_path,
        hook_title=clip.hook_title,
        duration_sec=duration,
        rationale=clip.rationale,
        signal_tags=clip.signal_tags,
    )

    await emit(ProgressEvent(
        type="artifact",
        node="render_clip",
        data={
            "type": "clip",
            "rank": clip.rank,
            "url": f"/files/{task.job_id}/clip_{clip.rank}.mp4",
            "hook_title": clip.hook_title,
            "rationale": clip.rationale,
            "signal_tags": clip.signal_tags,
        },
    ))
    await emit(ProgressEvent(type="node_complete", node="render_clip"))

    return {"rendered_clips": [rendered]}
