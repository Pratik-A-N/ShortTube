# Phase 3 — FastAPI + LangGraph Pipeline with SSE

> **Goal:** Wire the building blocks from Phases 1 and 2 into a real FastAPI app with a LangGraph pipeline, streaming progress events via SSE.
>
> **Time budget:** 3 hours.
>
> **Why this phase exists:** Up to now we have CLI scripts. This phase produces a server you can `curl` against and watch a stream of events. Frontend in Phase 5 plugs into this stream.

---

## Files to create

```
viral-chopper/
└── backend/
    ├── main.py                    # FastAPI app + SSE endpoint
    ├── pipeline.py                # LangGraph graph definition
    ├── nodes/
    │   ├── ingest.py              # yt-dlp wrapper (promote from spike)
    │   └── clipper.py             # ffmpeg wrapper (promote from spike)
    └── utils/
        ├── __init__.py
        ├── ffmpeg_utils.py        # subtitle extraction, vertical reformat
        └── progress.py            # SSE event helpers
```

Update `backend/requirements.txt`:
```
yt-dlp>=2024.1.0
webvtt-py>=0.5.0
python-dotenv>=1.0.0
groq>=0.11.0
google-generativeai>=0.8.0
pydantic>=2.0.0
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sse-starlette>=2.0.0
langgraph>=0.2.0
```

After Phase 3, **delete** `backend/spike/` and add a note in the README that the spike scripts existed during Day 1 development. The git history preserves them.

---

## File 1: `backend/utils/ffmpeg_utils.py`

Promote the ffmpeg work from `spike/03_render_clip.py` into reusable functions.

```python
def extract_segment_vtt(
    input_vtt: str,
    start_sec: float,
    end_sec: float,
    output_vtt: str,
) -> None:
    """Write a VTT containing only cues in [start_sec, end_sec], with timestamps shifted to start at 00:00."""

def render_vertical_clip(
    input_video: str,
    segment_vtt: str,
    start_sec: float,
    end_sec: float,
    output_path: str,
) -> None:
    """Cut, reformat to 9:16, burn captions. Raises CalledProcessError on ffmpeg failure."""
```

Implementation matches the spike. The vertical reformat uses blurred-background scaling (your Phase 1 default) — if that didn't work in Phase 1 and you fell back to black bars, keep black bars here.

**Key requirement:** all ffmpeg output goes to a job-specific tmp directory like `tmp/jobs/<job_id>/`, not a shared `tmp/`. Concurrent requests must not collide.

---

## File 2: `backend/utils/progress.py`

SSE event helpers. Same shape as your Code Review Agent.

```python
from typing import Literal
from pydantic import BaseModel

EventType = Literal["status", "node_start", "node_complete", "artifact", "error", "done"]

class ProgressEvent(BaseModel):
    type: EventType
    node: str | None = None
    message: str | None = None
    data: dict | None = None

    def to_sse(self) -> str:
        """Format as SSE 'data: <json>\\n\\n'."""
```

A queue-based pattern works well for streaming from LangGraph nodes back to the SSE endpoint:

```python
import asyncio
from contextvars import ContextVar

progress_queue: ContextVar[asyncio.Queue] = ContextVar("progress_queue")

async def emit(event: ProgressEvent):
    queue = progress_queue.get(None)
    if queue:
        await queue.put(event)
```

Nodes call `emit(...)` at start and end of their work. The SSE endpoint reads from the queue and forwards to the client.

---

## File 3: `backend/nodes/ingest.py`

Promote `spike/01_download.py` to a node.

```python
async def ingest_node(state: PipelineState) -> dict:
    """Downloads video + captions. Returns state updates."""
    await emit(ProgressEvent(type="node_start", node="ingest", message="Downloading video..."))

    # yt-dlp logic from spike, writing to tmp/jobs/<job_id>/
    # Set state.video_path, state.vtt_path, state.duration_sec

    await emit(ProgressEvent(type="node_complete", node="ingest", message=f"Downloaded {duration_sec:.0f}s video"))
    return {"video_path": ..., "vtt_path": ..., "duration_sec": ...}
```

**Validation:** if no captions are returned by yt-dlp, fail loudly with a clear error event. Whisper fallback is out of scope (stated constraint).

**Job IDs:** generate one per request (UUID4). Pass via state. Use it as the tmp subdirectory name.

---

## File 4: `backend/nodes/clipper.py`

Wraps `render_vertical_clip` for use in the graph. Note: in Phase 3 we render **sequentially** (one clip at a time) inside this node. Parallel rendering becomes a Phase 4 concern via Send API.

```python
async def clipper_node(state: PipelineState) -> dict:
    rendered = []
    for clip in state.selected_clips:
        await emit(ProgressEvent(
            type="node_start",
            node="clipper",
            message=f"Rendering clip {clip.rank}/3: {clip.hook_title}",
        ))

        segment_vtt = f"tmp/jobs/{job_id}/clip_{clip.rank}.vtt"
        output_path = f"tmp/jobs/{job_id}/clip_{clip.rank}.mp4"

        extract_segment_vtt(state.vtt_path, clip.start_sec, clip.end_sec, segment_vtt)
        render_vertical_clip(state.video_path, segment_vtt, clip.start_sec, clip.end_sec, output_path)

        rendered.append(RenderedClip(
            rank=clip.rank,
            file_path=output_path,
            hook_title=clip.hook_title,
            duration_sec=clip.end_sec - clip.start_sec,
        ))

        await emit(ProgressEvent(type="artifact", data={"clip_rank": clip.rank, "url": f"/files/{job_id}/clip_{clip.rank}.mp4"}))

    return {"rendered_clips": rendered}
```

---

## File 5: `backend/pipeline.py`

The LangGraph graph. Phase 3 version is **sequential** end-to-end. Phase 4 will replace the post-refiner section with parallel fan-out.

```python
from langgraph.graph import StateGraph, START, END
from schemas import PipelineState
from nodes.ingest import ingest_node
from nodes.transcript import transcript_node   # wraps parse_vtt_to_windows in a node
from nodes.scanner import scanner_node          # wraps score_windows
from nodes.refiner import refiner_node          # wraps refine_clips
from nodes.clipper import clipper_node

def build_graph():
    g = StateGraph(PipelineState)

    g.add_node("ingest", ingest_node)
    g.add_node("transcript", transcript_node)
    g.add_node("scanner", scanner_node)
    g.add_node("refiner", refiner_node)
    g.add_node("clipper", clipper_node)

    g.add_edge(START, "ingest")
    g.add_edge("ingest", "transcript")
    g.add_edge("transcript", "scanner")
    g.add_edge("scanner", "refiner")
    g.add_edge("refiner", "clipper")
    g.add_edge("clipper", END)

    return g.compile()
```

**Wrap the Phase 2 functions into nodes:** `transcript_node`, `scanner_node`, `refiner_node` should each emit a `node_start` and `node_complete` event around their work, then return the state dict.

---

## File 6: `backend/main.py`

```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio, uuid, json
from pathlib import Path

from pipeline import build_graph
from schemas import PipelineState
from utils.progress import progress_queue, ProgressEvent

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in Phase 6 to your Render frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = build_graph()

@app.get("/api/process")
async def process(youtube_url: str):
    """SSE endpoint. Streams ProgressEvents until done or error."""
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()

    async def event_generator():
        # Start the pipeline in a background task
        async def run_pipeline():
            token = progress_queue.set(queue)
            try:
                initial_state = PipelineState(youtube_url=youtube_url)
                # Inject job_id via context or extend state
                final = await graph.ainvoke(initial_state)
                await queue.put(ProgressEvent(type="done", data=final))
            except Exception as e:
                await queue.put(ProgressEvent(type="error", message=str(e)))
            finally:
                progress_queue.reset(token)
                await queue.put(None)  # sentinel

        asyncio.create_task(run_pipeline())

        while True:
            event = await queue.get()
            if event is None:
                break
            yield event.to_sse()

    return EventSourceResponse(event_generator())


@app.get("/files/{job_id}/{filename}")
async def get_file(job_id: str, filename: str):
    """Serve generated artifacts. Constrain path to prevent traversal."""
    safe = Path(f"tmp/jobs/{job_id}/{filename}").resolve()
    base = Path("tmp/jobs").resolve()
    if not str(safe).startswith(str(base)):
        raise HTTPException(403)
    if not safe.exists():
        raise HTTPException(404)
    return FileResponse(safe)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Job ID propagation:** the cleanest way is to put `job_id` on `PipelineState`. Add it to the schema. Every node that writes files uses `state.job_id` to scope the path.

---

## File 7: `backend/main.py` smoke test

Run:
```bash
cd backend
uvicorn main:app --reload --port 8000
```

In another terminal:
```bash
curl -N "http://localhost:8000/api/process?youtube_url=<your-demo-url>"
```

You should see a stream of SSE events. Roughly:
```
data: {"type":"node_start","node":"ingest","message":"Downloading video..."}

data: {"type":"node_complete","node":"ingest","message":"Downloaded 720s video"}

data: {"type":"node_start","node":"transcript","message":"Parsing captions..."}

...

data: {"type":"artifact","data":{"clip_rank":1,"url":"/files/<uuid>/clip_1.mp4"}}

data: {"type":"done","data":{...}}
```

Then visit `http://localhost:8000/files/<job_id>/clip_1.mp4` — the clip should download and play.

---

## Phase 3 done criteria

- [ ] `uvicorn main:app` starts cleanly
- [ ] `curl -N /api/process?youtube_url=...` streams events live (not buffered)
- [ ] Pipeline completes end-to-end on the canonical demo URL in under 3 min
- [ ] 3 vertical mp4 clips land in `tmp/jobs/<job_id>/` and are servable via `/files/...`
- [ ] If you kill `GROQ_API_KEY`, the pipeline still completes via Gemini fallback
- [ ] Errors anywhere in the graph stream as `error` events instead of HTTP 500s

---

## What we're explicitly NOT doing in Phase 3

- No parallel clip rendering or parallel agent fan-out (Phase 4)
- No blog post or social captions (Phase 4)
- No frontend (Phase 5)
- No persistent storage / job history — `tmp/jobs/` is ephemeral, that's fine
- No rate limiting on the API (it's a demo)
- No auth
- No tests beyond curl smoke test

---

## Cleanup

At the end of Phase 3:
- [ ] Delete `backend/spike/` directory (git preserves history)
- [ ] Commit with message: `Phase 3: FastAPI + LangGraph pipeline with SSE`
