import asyncio
import time
from pathlib import Path

from llm.client import get_llm_client
from llm.prompts import BLOG_WRITER_SYSTEM, BLOG_WRITER_USER
from schemas import BlogTask
from utils.progress import emit, ProgressEvent
from utils.logger import get_logger

log = get_logger("nodes.blog_writer")


async def write_blog(task: BlogTask) -> dict:
    log.info(f"[{task.job_id[:8]}] BLOG_WRITER start | video='{task.video_title}' | transcript_chars={len(task.transcript_text)}")
    await emit(ProgressEvent(type="node_start", node="write_blog", message="Writing blog post..."))

    user_prompt = BLOG_WRITER_USER.format(
        video_title=task.video_title,
        duration_min=task.duration_min,
        transcript_text=task.transcript_text[:8000],
    )

    t0 = time.time()
    blog = await asyncio.to_thread(
        get_llm_client().complete, BLOG_WRITER_SYSTEM, user_prompt, "text", 2500, 0.6
    )
    log.info(f"[{task.job_id[:8]}] BLOG_WRITER LLM done in {time.time()-t0:.1f}s | output_chars={len(blog)}")

    job_dir = Path(f"tmp/jobs/{task.job_id}")
    job_dir.mkdir(parents=True, exist_ok=True)
    output_path = job_dir / "blog.md"
    output_path.write_text(blog, encoding="utf-8")
    log.info(f"[{task.job_id[:8]}] BLOG_WRITER saved → {output_path}")

    await emit(ProgressEvent(
        type="artifact",
        node="write_blog",
        data={"type": "blog", "url": f"/files/{task.job_id}/blog.md"},
    ))
    await emit(ProgressEvent(type="node_complete", node="write_blog"))

    return {"blog_post": blog}
