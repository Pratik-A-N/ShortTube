import asyncio
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from utils.logger import setup_logging, get_logger
setup_logging()

from pipeline import build_graph
from schemas import PipelineState
from utils.progress import progress_queue, ProgressEvent
from llm.client import get_llm_client, build_for_user, user_llm_override, _redact
import cache

log = get_logger("main")

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="ShortTube")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*", "X-User-Api-Key", "X-User-Provider"],
)

graph = build_graph()
log.info("LangGraph pipeline compiled and ready")
get_llm_client()  # eagerly init so provider chain logs appear at startup


_VALID_PROVIDERS = {"groq", "openai", "anthropic", "mistral", "together"}


@app.get("/api/process")
@limiter.limit("10/minute")
async def process(youtube_url: str, request: Request):
    job_id = str(uuid.uuid4())
    client_ip = request.client.host if request.client else "unknown"

    raw_key = request.headers.get("X-User-Api-Key", "").strip()
    raw_provider = request.headers.get("X-User-Provider", "groq").strip().lower()
    user_api_key = raw_key if raw_key else None
    user_provider = raw_provider if raw_provider in _VALID_PROVIDERS else "groq"

    log.info(
        f"[{job_id[:8]}] New request | url={youtube_url} | client={client_ip}"
        + (f" | user-key provider={user_provider}" if user_api_key else "")
    )

    queue: asyncio.Queue = asyncio.Queue()

    async def event_generator():
        # --- Cache hit: stream saved artifacts immediately ---
        cached = cache.get_cached(youtube_url)
        if cached:
            log.info(f"[{job_id[:8]}] Cache HIT | original_job={cached['job_id'][:8]} | url={youtube_url[:60]}")
            yield {"data": ProgressEvent(type="status", message="Loaded from cache").model_dump_json(exclude_none=True)}
            for artifact_data in cached["artifacts"]:
                yield {"data": ProgressEvent(type="artifact", data=artifact_data).model_dump_json(exclude_none=True)}
                await asyncio.sleep(0.02)
            yield {"data": ProgressEvent(type="done", data={"job_id": cached["job_id"]}).model_dump_json(exclude_none=True)}
            return

        # --- Cache miss: run the full pipeline ---
        log.info(f"[{job_id[:8]}] Cache MISS — running pipeline")
        collected_artifacts: list[dict] = []

        async def run_pipeline():
            t0 = time.time()
            token = progress_queue.set(queue)
            user_token = None
            if user_api_key:
                try:
                    user_client = build_for_user(user_provider, user_api_key)
                    user_token = user_llm_override.set(user_client)
                except ValueError as e:
                    log.warning(f"[{job_id[:8]}] Invalid user provider: {e} — falling back to server keys")
            try:
                initial_state = PipelineState(youtube_url=youtube_url, job_id=job_id)
                await graph.ainvoke(initial_state)
                elapsed = time.time() - t0
                log.info(f"[{job_id[:8]}] Pipeline DONE in {elapsed:.1f}s")
                await queue.put(ProgressEvent(type="done", data={"job_id": job_id}))
            except Exception as e:
                elapsed = time.time() - t0
                safe_msg = _redact(e)
                log.error(f"[{job_id[:8]}] Pipeline FAILED after {elapsed:.1f}s | {type(e).__name__}: {safe_msg}")
                await queue.put(ProgressEvent(type="error", message=safe_msg))
            finally:
                progress_queue.reset(token)
                if user_token is not None:
                    user_llm_override.reset(user_token)
                await queue.put(None)

        asyncio.create_task(run_pipeline())

        while True:
            event = await queue.get()
            if event is None:
                break
            if event.type == "artifact" and event.data:
                collected_artifacts.append(event.data)
            if event.type == "done":
                cache.save_result(youtube_url, job_id, collected_artifacts)
            yield {"data": event.model_dump_json(exclude_none=True)}

    return EventSourceResponse(event_generator())


@app.get("/files/{job_id}/{filename}")
async def get_file(job_id: str, filename: str):
    safe = Path(f"tmp/jobs/{job_id}/{filename}").resolve()
    base = Path("tmp/jobs").resolve()
    if not str(safe).startswith(str(base)):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not safe.exists():
        raise HTTPException(status_code=404, detail="File not found")
    log.info(f"[{job_id[:8]}] Serving file: {filename}")
    return FileResponse(safe)


@app.get("/health")
async def health():
    return {"status": "ok"}
