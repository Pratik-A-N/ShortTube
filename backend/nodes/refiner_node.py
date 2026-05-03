import time

from schemas import PipelineState
from nodes.refiner import refine_clips
from llm.client import get_llm_client
from utils.progress import emit, ProgressEvent
from utils.logger import get_logger

log = get_logger("nodes.refiner")


async def refiner_node(state: PipelineState) -> dict:
    log.info(f"[{state.job_id[:8]}] REFINER start | scored_windows={len(state.scored_windows)}")
    await emit(ProgressEvent(type="node_start", node="refiner", message="Selecting best clips..."))

    t0 = time.time()
    clips = refine_clips(
        state.scored_windows,
        state.windows,
        get_llm_client(),
        video_duration=state.duration_sec or float("inf"),
        heatmap=state.heatmap,
        chapters=state.chapters,
        description_timestamps=state.description_timestamps,
    )

    for c in clips:
        log.info(f"[{state.job_id[:8]}] REFINER clip {c.rank} | {c.start_sec:.1f}s->{c.end_sec:.1f}s ({c.end_sec-c.start_sec:.0f}s) | score={c.viral_score} | hook='{c.hook_title}'")
    log.info(f"[{state.job_id[:8]}] REFINER done in {time.time()-t0:.1f}s | clips={len(clips)}")

    await emit(ProgressEvent(
        type="node_complete",
        node="refiner",
        message="Selected {} clips: {}".format(len(clips), ", ".join("'{}'".format(c.hook_title) for c in clips)),
    ))

    return {"selected_clips": clips}
