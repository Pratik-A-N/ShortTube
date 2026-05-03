import asyncio
import os

from schemas import PipelineState
from utils.progress import emit, ProgressEvent
from utils.zip_utils import build_zip
from utils.logger import get_logger

log = get_logger("nodes.aggregator")


async def aggregator_node(state: PipelineState) -> dict:
    log.info(
        f"[{state.job_id[:8]}] AGGREGATOR | clips={len(state.rendered_clips)} "
        f"blog={'yes' if state.blog_post else 'no'} captions={len(state.social_captions)}"
    )

    await emit(ProgressEvent(type="node_start", node="aggregator", message="Packaging outputs..."))

    await emit(ProgressEvent(
        type="status",
        message=f"All artifacts ready: {len(state.rendered_clips)} clips, blog post, {len(state.social_captions)} captions",
    ))

    zip_path = await asyncio.to_thread(build_zip, state)
    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024) if os.path.exists(zip_path) else 0
    log.info(f"[{state.job_id[:8]}] AGGREGATOR zip built | size={zip_size_mb:.1f}MB | path={zip_path}")

    await emit(ProgressEvent(
        type="artifact",
        data={"type": "zip", "url": f"/files/{state.job_id}/bundle.zip"},
    ))

    await emit(ProgressEvent(type="node_complete", node="aggregator"))

    return {}
