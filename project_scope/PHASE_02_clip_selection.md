# Phase 2 — Clip Selection Agents

> **Goal:** Build the two-pass clip selection logic (Scanner → Refiner) and prove it picks high-quality clips against your canonical demo video.
>
> **Time budget:** 3 hours.
>
> **Why this phase exists:** Clip selection is the single highest-leverage decision in the product. A mediocre selector produces clips nobody would post; a good one is the entire reason this tool has value. We isolate it from the rest of the pipeline so we can iterate prompt quality without rebuilding the whole app each cycle.

---

## Files to create

```
viral-chopper/
└── backend/
    ├── llm/
    │   ├── __init__.py
    │   ├── client.py           # Provider-agnostic LLM client
    │   └── prompts.py          # All prompts in one place
    ├── nodes/
    │   ├── __init__.py
    │   ├── transcript.py       # Promote chunking from spike to module
    │   ├── scanner.py          # Scanner agent
    │   └── refiner.py          # Refiner agent
    ├── schemas.py              # Pydantic models
    ├── config.py               # Env vars and constants
    └── spike/
        └── 04_clip_selection.py    # Standalone test driver
```

Update `backend/requirements.txt`:
```
yt-dlp>=2024.1.0
webvtt-py>=0.5.0
python-dotenv>=1.0.0
groq>=0.11.0
google-generativeai>=0.8.0
pydantic>=2.0.0
```

---

## File 1: `backend/config.py`

Env-driven configuration. Keep it dead simple.

```python
import os
from dotenv import load_dotenv

load_dotenv()

# LLM providers
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# LLM model choices
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.0-flash"

# Pipeline constants
WINDOW_SIZE_SEC = 90
WINDOW_STRIDE_SEC = 30
NUM_CLIPS = 3
CLIP_MIN_SEC = 30
CLIP_MAX_SEC = 60

# Demo defaults (the canonical demo URL from Phase 1)
DEMO_URL = "<paste your canonical YouTube URL here>"
```

Add a `.env.example`:
```
GROQ_API_KEY=
GEMINI_API_KEY=
```

---

## File 2: `backend/llm/client.py`

**Purpose:** Provider-agnostic LLM client with automatic fallback. Reuse the pattern from your Code Review Agent.

**Interface:**
```python
class LLMClient:
    def __init__(self, primary: str = "groq", fallback: str = "gemini"): ...

    def complete(
        self,
        system: str,
        user: str,
        response_format: Literal["text", "json"] = "text",
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> str:
        """Returns the text content. For json mode, returns the raw JSON string."""
```

**Implementation requirements:**
- Try the primary provider first. On rate limit (`429`), authentication error, or 5xx, fall back to the secondary provider.
- For Groq: use the `groq` SDK, set `response_format={"type": "json_object"}` when requested.
- For Gemini: use `google-generativeai` SDK, set `response_mime_type="application/json"` when requested.
- Log every attempt with provider name and latency.
- If both providers fail, raise `LLMUnavailableError` with details.

**Why this matters for the demo:** Groq's free tier has aggressive rate limits. During a live Loom recording, you don't want to hit a 429 mid-demo. Fallback isn't paranoia, it's demo insurance.

---

## File 3: `backend/llm/prompts.py`

All prompts live here. Plain Python strings, no template engine — overkill for 3 days.

### `SCANNER_SYSTEM`

```
You are a viral content analyst. You evaluate transcript windows from long-form videos and score each one for short-form video potential (TikTok, Reels, Shorts).

You score on these dimensions, each 0-10:
- HOOK: Does the opening line grab attention? Strong hooks: bold claims, surprising facts, emotional statements, specific numbers, contrarian takes. Weak hooks: throat-clearing, mid-sentence starts, generic intros.
- STANDALONE: Can a viewer understand this clip without context from the rest of the video?
- ENERGY: Is there emotional charge, conviction, or vivid language? Monotone explanations score low.
- SPECIFICITY: Are there concrete numbers, names, examples? Vague generalities score low.
- COMPLETENESS: Does the window contain a complete thought or arc?

Return strictly valid JSON in this shape:
{
  "windows": [
    {"window_id": 1, "hook": 7, "standalone": 8, "energy": 6, "specificity": 9, "completeness": 7, "total": 37, "one_line_reason": "..."},
    ...
  ]
}

Total = sum of the five dimensions. Be discerning. Most windows in most videos score 15-25. A 35+ window is genuinely strong. Don't inflate scores.
```

### `SCANNER_USER` (template)

```
Score these transcript windows from a {duration_min}-minute video.

{windows_text}

Return JSON only.
```

Where `windows_text` is each window formatted as:
```
[Window 1] 00:00 → 01:30
<text>

[Window 2] 00:30 → 02:00
<text>
...
```

### `REFINER_SYSTEM`

```
You are a short-form video editor. You receive the top-scoring transcript windows from a long-form video, plus their full text. Your job: pick the best 3 NON-OVERLAPPING clips, refine their start/end timestamps for clean cuts, and write a viral hook title for each.

Rules:
- Clips must be 30-60 seconds long.
- Clips must NOT overlap. If two top windows overlap, pick the better one.
- Refine timestamps: start at the beginning of a sentence, end at the end of a thought. Avoid mid-sentence cuts.
- Hook title: 5-10 words, written like a TikTok caption. Strong examples: "The lie schools tell about success", "Why 99% of people fail at this", "I tried it for 30 days".
- Order clips by viral potential (clip 1 = strongest).

Return strictly valid JSON:
{
  "clips": [
    {
      "rank": 1,
      "start_sec": 145.3,
      "end_sec": 192.7,
      "hook_title": "...",
      "viral_score": 38,
      "rationale": "one sentence on why this clip works"
    },
    ... (3 total)
  ]
}
```

### `REFINER_USER` (template)

```
Top-scoring windows from this video, ranked by Scanner total:

{top_windows_text}

Pick the 3 best non-overlapping clips. Return JSON only.
```

`top_windows_text` is the top 6-8 windows by Scanner score, formatted with full text and original timestamps.

---

## File 4: `backend/schemas.py`

Pydantic models that match the JSON contracts above. These are the source of truth — every node returns/accepts these types.

```python
from pydantic import BaseModel
from typing import List

class TranscriptWindow(BaseModel):
    window_id: int
    start_sec: float
    end_sec: float
    text: str

class ScoredWindow(BaseModel):
    window_id: int
    hook: int
    standalone: int
    energy: int
    specificity: int
    completeness: int
    total: int
    one_line_reason: str

class SelectedClip(BaseModel):
    rank: int
    start_sec: float
    end_sec: float
    hook_title: str
    viral_score: int
    rationale: str

class RenderedClip(BaseModel):
    rank: int
    file_path: str
    hook_title: str
    duration_sec: float

class PipelineState(BaseModel):
    """Full state passed through LangGraph. Will grow in later phases."""
    youtube_url: str
    video_path: str | None = None
    vtt_path: str | None = None
    duration_sec: float | None = None
    windows: List[TranscriptWindow] = []
    scored_windows: List[ScoredWindow] = []
    selected_clips: List[SelectedClip] = []
    rendered_clips: List[RenderedClip] = []
    blog_post: str | None = None
    social_captions: List[str] = []
    error: str | None = None
```

---

## File 5: `backend/nodes/transcript.py`

Promote the chunking logic from `spike/02_chunk.py` to a real module.

```python
def parse_vtt_to_windows(
    vtt_path: str,
    window_size_sec: int = 90,
    stride_sec: int = 30,
) -> List[TranscriptWindow]: ...
```

Same logic as the spike, just packaged. Drop empty windows. Strip VTT formatting tags.

---

## File 6: `backend/nodes/scanner.py`

```python
def score_windows(
    windows: List[TranscriptWindow],
    duration_min: float,
    llm: LLMClient,
) -> List[ScoredWindow]: ...
```

**Implementation requirements:**
- Format windows into `windows_text`.
- Call LLM with `SCANNER_SYSTEM` + `SCANNER_USER`, JSON mode, `temperature=0.2` (we want consistent scoring, not creativity).
- Parse JSON, validate with Pydantic, return list of `ScoredWindow`.
- If JSON parse fails, log the raw output and raise. Don't silently retry — we want to see prompt failures during dev.

**Batching consideration:** If the video is long (say, 25 min → ~50 windows), the prompt could be huge. **For Phase 2, don't worry about batching.** Llama 3.3 70B has a 128K context. If we hit issues with 25-min videos, we'll add batching in Phase 3.

---

## File 7: `backend/nodes/refiner.py`

```python
def refine_clips(
    scored_windows: List[ScoredWindow],
    windows: List[TranscriptWindow],
    llm: LLMClient,
    top_k: int = 8,
    num_clips: int = 3,
) -> List[SelectedClip]: ...
```

**Implementation requirements:**
- Take top-k scored windows (by `total`), pull their full text from the original `windows` list.
- Format into `top_windows_text` showing `Window N | start_sec → end_sec | total: X` followed by full text.
- Call LLM with `REFINER_SYSTEM` + `REFINER_USER`, JSON mode, `temperature=0.4` (slight creativity for hook titles).
- Parse, validate, return list of `SelectedClip`.

**Validation post-LLM:**
- Assert clips are 30-60 sec. If a clip is <30 sec, extend `end_sec` by up to 10 sec; if >60 sec, trim to 60. Don't reject — the LLM occasionally drifts and we want graceful degradation.
- Assert non-overlap. If two clips overlap, drop the lower-ranked one and log a warning.

---

## File 8: `backend/spike/04_clip_selection.py`

End-to-end test driver for Phase 2. No FastAPI yet.

```python
# Pseudocode
from config import DEMO_URL
from nodes.transcript import parse_vtt_to_windows
from nodes.scanner import score_windows
from nodes.refiner import refine_clips
from llm.client import LLMClient

# Assumes Phase 1 spike already produced tmp/captions.en.vtt
windows = parse_vtt_to_windows("tmp/captions.en.vtt")
duration_min = max(w.end_sec for w in windows) / 60

llm = LLMClient()
scored = score_windows(windows, duration_min, llm)

print("Top 5 windows by score:")
for w in sorted(scored, key=lambda x: -x.total)[:5]:
    print(f"  Window {w.window_id}: total={w.total} — {w.one_line_reason}")

clips = refine_clips(scored, windows, llm)

print("\nSelected clips:")
for c in clips:
    print(f"  Clip {c.rank}: {c.start_sec:.1f}s → {c.end_sec:.1f}s")
    print(f"    Hook: {c.hook_title}")
    print(f"    Why:  {c.rationale}")
```

---

## Phase 2 done criteria

- [ ] `python spike/04_clip_selection.py` runs end-to-end without crashing
- [ ] Scanner output: scores look reasonable — top windows feel intuitively stronger than bottom ones
- [ ] Refiner output: 3 non-overlapping clips, each 30-60 sec, with hook titles you'd actually consider posting
- [ ] If you swap to a different demo video and rerun, you still get sensible results
- [ ] LLM fallback works: kill `GROQ_API_KEY` in `.env`, rerun, Gemini takes over

**This phase's quality gate is subjective.** If the clips picked aren't good, no amount of frontend polish will save the project. Iterate the prompts until the clips are genuinely worth posting. Budget up to 1.5 of the 3 hours on prompt iteration.

---

## What we're explicitly NOT doing in Phase 2

- No clip rendering (that's Phase 3, reusing the Phase 1 spike code)
- No blog post or captions (Phase 4)
- No FastAPI, no React (Phase 3 / 5)
- No LangGraph yet — we'll wire it up in Phase 3 once the building blocks exist
- No prompt batching for very long videos (defer until we hit it)
- No retry logic on LLM JSON parse failures (we want to see them and fix prompts)
