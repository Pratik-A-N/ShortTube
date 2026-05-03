import asyncio
import time

from llm.client import get_llm_client
from llm.prompts import CAPTION_WRITER_SYSTEM, CAPTION_WRITER_USER
from schemas import CaptionTask
from utils.progress import emit, ProgressEvent
from utils.logger import get_logger

log = get_logger("nodes.caption_writer")


async def write_caption(task: CaptionTask) -> dict:
    rank = task.clip.rank
    log.info(f"[{task.job_id[:8]}] CAPTION_{rank} start | hook='{task.clip.hook_title}'")
    await emit(ProgressEvent(
        type="node_start",
        node="write_caption",
        message=f"Writing caption for clip {rank}...",
    ))

    user_prompt = CAPTION_WRITER_USER.format(
        hook_title=task.clip.hook_title,
        clip_transcript=task.clip_transcript[:1500],
    )

    t0 = time.time()
    caption = await asyncio.to_thread(
        get_llm_client().complete, CAPTION_WRITER_SYSTEM, user_prompt, "text", 200, 0.7
    )
    log.info(f"[{task.job_id[:8]}] CAPTION_{rank} LLM done in {time.time()-t0:.1f}s | chars={len(caption)}")

    formatted = f"[Clip {rank}] {task.clip.hook_title}\n\n{caption.strip()}"

    await emit(ProgressEvent(
        type="artifact",
        node="write_caption",
        data={"type": "caption", "rank": rank, "text": formatted},
    ))
    await emit(ProgressEvent(type="node_complete", node="write_caption"))

    return {"social_captions": [formatted]}
