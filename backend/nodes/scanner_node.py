import time

from schemas import PipelineState
from nodes.scanner import score_windows
from llm.client import get_llm_client
from utils.progress import emit, ProgressEvent
from utils.logger import get_logger

log = get_logger("nodes.scanner")


async def scanner_node(state: PipelineState) -> dict:
    log.info(f"[{state.job_id[:8]}] SCANNER start | windows={len(state.windows)}")
    await emit(ProgressEvent(type="node_start", node="scanner", message="Scoring transcript windows...", progress=0))

    duration_min = (state.duration_sec or 0) / 60

    async def on_batch_done(done: int, total: int) -> None:
        pct = int(done / total * 100)
        await emit(ProgressEvent(
            type="node_start",
            node="scanner",
            message=f"Scoring... batch {done}/{total}",
            progress=pct,
        ))

    t0 = time.time()
    scored = await score_windows(state.windows, duration_min, get_llm_client(), on_batch_done=on_batch_done)

    top3 = sorted(scored, key=lambda x: -x.total)[:3]
    top_summary = " | ".join(f"W{w.window_id}(total={w.total})" for w in top3)
    log.info(f"[{state.job_id[:8]}] SCANNER done in {time.time()-t0:.1f}s | scored={len(scored)} windows | top3: {top_summary}")

    await emit(ProgressEvent(
        type="node_complete",
        node="scanner",
        message=f"Scored {len(scored)} windows. Top: {', '.join(f'W{w.window_id}({w.total})' for w in top3)}",
    ))

    return {"scored_windows": scored}
