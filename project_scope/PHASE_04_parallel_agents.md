# Phase 4 — Parallel Agents (Send API) + Blog + Captions

> **Goal:** Add the blog writer and caption writer agents, and parallelize all three post-refiner workstreams (clip rendering, blog writing, caption writing) using LangGraph's Send API.
>
> **Time budget:** 2 hours.
>
> **Why this phase exists:** Two reasons. First, the blog post and social captions are committed deliverables in our scope. Second, the parallel Send API pattern is *the* architectural talking point you'll bring up in the Pixii interview — it directly mirrors your Code Review Agent. The pipeline must demonstrate it.

---

## What changes

After the refiner produces 3 selected clips, we currently run sequentially: render clip 1 → render clip 2 → render clip 3 → done. We replace that with a fan-out:

```
                    ┌─→ render_clip(clip 1)
                    │
                    ├─→ render_clip(clip 2)
                    │
refiner ──Send()──→ ├─→ render_clip(clip 3)
                    │
                    ├─→ write_blog(full transcript)
                    │
                    ├─→ write_caption(clip 1)
                    │
                    ├─→ write_caption(clip 2)
                    │
                    └─→ write_caption(clip 3)
                                    ↓
                                  aggregate
                                    ↓
                                   END
```

That's 7 parallel Send invocations from a single supervisor node.

---

## Files to create / modify

```
viral-chopper/
└── backend/
    ├── nodes/
    │   ├── clipper.py           # MODIFIED: now renders ONE clip per call
    │   ├── blog_writer.py       # NEW
    │   ├── caption_writer.py    # NEW
    │   └── aggregator.py        # NEW: collects parallel results
    ├── llm/
    │   └── prompts.py           # MODIFIED: add blog + caption prompts
    ├── pipeline.py              # MODIFIED: add Send-based fan-out
    └── schemas.py               # MODIFIED: add fields for new artifacts
```

---

## File 1: `backend/llm/prompts.py` — additions

### `BLOG_WRITER_SYSTEM`

```
You are a content writer turning a long-form video transcript into an SEO-optimized blog post.

Requirements:
- 800-1200 words.
- Opening hook in the first 2 sentences.
- 3-5 H2 section headings (use Markdown ## syntax).
- Include 1-2 specific quotes or claims from the transcript, attributed naturally ("In the video, the speaker explains...").
- Close with a 2-3 sentence summary and a question to drive comments.
- Voice: conversational but informed. Not corporate. Not clickbait.
- Output Markdown only. No frontmatter. No code fences.
```

### `BLOG_WRITER_USER` (template)

```
Video title: {video_title}
Duration: {duration_min} min

Full transcript:
{transcript_text}

Write the blog post.
```

### `CAPTION_WRITER_SYSTEM`

```
You write social media captions for short-form video clips (TikTok, Instagram Reels, YouTube Shorts).

Requirements:
- 1-3 sentences, total under 220 characters.
- Open with a hook line that creates curiosity or stakes.
- End with a soft CTA: a question, an invitation to follow, or "save this for later".
- 3-5 relevant hashtags at the end, lowercase, no spaces.
- No emoji spam. Max 2 emoji.
- Voice matches the clip's energy — punchy, not corporate.

Output the caption text only. No labels, no quotes around it.
```

### `CAPTION_WRITER_USER` (template)

```
Clip hook title: {hook_title}
Clip transcript:
{clip_transcript}

Write the caption.
```

---

## File 2: `backend/schemas.py` — additions

```python
class ClipperTask(BaseModel):
    """Sent to a single clipper invocation."""
    job_id: str
    clip: SelectedClip
    video_path: str
    vtt_path: str

class CaptionTask(BaseModel):
    """Sent to a single caption_writer invocation."""
    clip: SelectedClip
    clip_transcript: str

class BlogTask(BaseModel):
    """Sent to the single blog_writer invocation."""
    video_title: str
    duration_min: float
    transcript_text: str
```

Update `PipelineState` if needed. `rendered_clips`, `blog_post`, and `social_captions` should all use list-merge reducers so parallel writes don't clobber each other:

```python
from typing import Annotated
from operator import add

class PipelineState(BaseModel):
    ...
    rendered_clips: Annotated[List[RenderedClip], add] = []
    social_captions: Annotated[List[str], add] = []
    blog_post: str | None = None  # only one writer, no reducer needed
    video_title: str | None = None
```

(LangGraph uses these `Annotated[..., add]` reducers to merge state from parallel branches.)

---

## File 3: `backend/nodes/clipper.py` — refactored

The Phase 3 version handled all 3 clips in one node. Refactor to handle **one** clip per invocation, so it can be Send-fanned-out.

```python
async def render_one_clip(task: ClipperTask) -> dict:
    clip = task.clip
    await emit(ProgressEvent(
        type="node_start",
        node=f"clipper_{clip.rank}",
        message=f"Rendering clip {clip.rank}: {clip.hook_title}",
    ))

    segment_vtt = f"tmp/jobs/{task.job_id}/clip_{clip.rank}.vtt"
    output_path = f"tmp/jobs/{task.job_id}/clip_{clip.rank}.mp4"

    extract_segment_vtt(task.vtt_path, clip.start_sec, clip.end_sec, segment_vtt)
    render_vertical_clip(task.video_path, segment_vtt, clip.start_sec, clip.end_sec, output_path)

    rendered = RenderedClip(
        rank=clip.rank,
        file_path=output_path,
        hook_title=clip.hook_title,
        duration_sec=clip.end_sec - clip.start_sec,
    )

    await emit(ProgressEvent(
        type="artifact",
        node=f"clipper_{clip.rank}",
        data={"type": "clip", "rank": clip.rank, "url": f"/files/{task.job_id}/clip_{clip.rank}.mp4", "hook_title": clip.hook_title},
    ))
    await emit(ProgressEvent(type="node_complete", node=f"clipper_{clip.rank}"))

    return {"rendered_clips": [rendered]}  # list with one item; LangGraph merges via the `add` reducer
```

---

## File 4: `backend/nodes/blog_writer.py`

```python
async def write_blog(task: BlogTask) -> dict:
    await emit(ProgressEvent(type="node_start", node="blog_writer", message="Writing blog post..."))

    user_prompt = BLOG_WRITER_USER.format(
        video_title=task.video_title,
        duration_min=task.duration_min,
        transcript_text=task.transcript_text,
    )
    blog = llm.complete(BLOG_WRITER_SYSTEM, user_prompt, temperature=0.6, max_tokens=2500)

    # Save to disk so it can be downloaded
    output_path = f"tmp/jobs/{state.job_id}/blog.md"
    Path(output_path).write_text(blog)

    await emit(ProgressEvent(
        type="artifact",
        node="blog_writer",
        data={"type": "blog", "url": f"/files/{state.job_id}/blog.md"},
    ))
    await emit(ProgressEvent(type="node_complete", node="blog_writer"))
    return {"blog_post": blog}
```

(Note: pulling `state.job_id` inside a Send-task node requires either including it in `BlogTask` or using a context var. Cleaner: include `job_id` in `BlogTask`.)

---

## File 5: `backend/nodes/caption_writer.py`

```python
async def write_caption(task: CaptionTask) -> dict:
    rank = task.clip.rank
    await emit(ProgressEvent(type="node_start", node=f"caption_{rank}", message=f"Writing caption for clip {rank}..."))

    user_prompt = CAPTION_WRITER_USER.format(
        hook_title=task.clip.hook_title,
        clip_transcript=task.clip_transcript,
    )
    caption = llm.complete(CAPTION_WRITER_SYSTEM, user_prompt, temperature=0.7, max_tokens=200)

    formatted = f"[Clip {rank}] {task.clip.hook_title}\n\n{caption.strip()}"
    await emit(ProgressEvent(
        type="artifact",
        node=f"caption_{rank}",
        data={"type": "caption", "rank": rank, "text": formatted},
    ))
    await emit(ProgressEvent(type="node_complete", node=f"caption_{rank}"))
    return {"social_captions": [formatted]}
```

The clip transcript for each caption is the slice of `windows` text between `clip.start_sec` and `clip.end_sec`. Compute it in the supervisor.

---

## File 6: `backend/nodes/aggregator.py`

A trivial pass-through node that runs after all parallel branches complete. Mainly emits a "done" status so the SSE stream can show "All artifacts ready."

```python
async def aggregator_node(state: PipelineState) -> dict:
    await emit(ProgressEvent(
        type="status",
        message=f"All artifacts ready: {len(state.rendered_clips)} clips, blog post, {len(state.social_captions)} captions",
    ))

    # Build a zip bundle for download-all
    zip_path = build_zip(state)
    await emit(ProgressEvent(type="artifact", data={"type": "zip", "url": f"/files/{state.job_id}/bundle.zip"}))

    return {}
```

`build_zip` is a small util in `utils/zip_utils.py` — zip up all clips + blog.md + captions.txt.

---

## File 7: `backend/pipeline.py` — modified

Replace the Phase 3 sequential post-refiner with a Send-based fan-out.

```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

def fan_out(state: PipelineState) -> list[Send]:
    """Build the parallel send list after refiner completes."""
    sends = []

    # One Send per clip render
    for clip in state.selected_clips:
        sends.append(Send("render_clip", ClipperTask(
            job_id=state.job_id,
            clip=clip,
            video_path=state.video_path,
            vtt_path=state.vtt_path,
        )))

    # One Send for blog
    full_transcript_text = "\n\n".join(w.text for w in state.windows)
    sends.append(Send("write_blog", BlogTask(
        job_id=state.job_id,
        video_title=state.video_title or "Untitled",
        duration_min=state.duration_sec / 60,
        transcript_text=full_transcript_text,
    )))

    # One Send per caption
    for clip in state.selected_clips:
        clip_text = extract_text_for_range(state.windows, clip.start_sec, clip.end_sec)
        sends.append(Send("write_caption", CaptionTask(
            clip=clip,
            clip_transcript=clip_text,
        )))

    return sends


def build_graph():
    g = StateGraph(PipelineState)

    g.add_node("ingest", ingest_node)
    g.add_node("transcript", transcript_node)
    g.add_node("scanner", scanner_node)
    g.add_node("refiner", refiner_node)
    g.add_node("render_clip", render_one_clip)
    g.add_node("write_blog", write_blog)
    g.add_node("write_caption", write_caption)
    g.add_node("aggregator", aggregator_node)

    g.add_edge(START, "ingest")
    g.add_edge("ingest", "transcript")
    g.add_edge("transcript", "scanner")
    g.add_edge("scanner", "refiner")

    # Conditional fan-out from refiner
    g.add_conditional_edges("refiner", fan_out, ["render_clip", "write_blog", "write_caption"])

    # All three Send'd nodes converge to aggregator
    g.add_edge("render_clip", "aggregator")
    g.add_edge("write_blog", "aggregator")
    g.add_edge("write_caption", "aggregator")

    g.add_edge("aggregator", END)

    return g.compile()
```

**Key LangGraph semantics:** when multiple Send invocations target the same node, they run in parallel. When all converge to a downstream node (aggregator), the graph waits for all of them before running the aggregator. This is exactly the pattern you used in Code Review Agent.

---

## Latency expectation

Sequential (Phase 3): ~ingest (30s) + scanner (10s) + refiner (5s) + clipper×3 (45s) + blog (15s) + captions×3 (10s) = ~115s

Parallel (Phase 4): ~ingest (30s) + scanner (10s) + refiner (5s) + max(clipper, blog, caption) (≈25s) = ~70s

That's a ~40% reduction. Mention it in the README and Loom: "Send API parallelization reduces total pipeline latency by ~40% on the demo input."

---

## Phase 4 done criteria

- [ ] All three post-refiner workstreams (clips, blog, captions) run in parallel — verifiable by watching SSE events stream interleaved
- [ ] Final state has 3 rendered clips, 1 blog post, 3 social captions
- [ ] `tmp/jobs/<job_id>/bundle.zip` exists and contains all artifacts
- [ ] Total pipeline time for canonical demo: under 90 seconds
- [ ] Test: kill the network mid-pipeline. Errors stream to client; no zombie processes left.

---

## What we're explicitly NOT doing in Phase 4

- No retry logic on parallel branch failures (one failed branch fails the whole job — that's correct for a demo)
- No partial-result delivery (you don't get clips early if blog is slow — fine, aggregator waits for all)
- No optimization of LLM batch calls (e.g., one prompt for all 3 captions) — keep them as separate Send invocations to demonstrate the pattern
- No streaming of LLM tokens to the client — only node-level events
