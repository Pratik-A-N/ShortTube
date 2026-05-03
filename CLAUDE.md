# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Viral Video Chopper** — paste a YouTube URL, get 3 vertical (9:16) short-form clips with burned captions, 1 SEO blog post, and 3 social captions. Built as a 3-day submission for Pixii.ai (deadline May 5, 2026).

## Commands

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # add GROQ_API_KEY and GEMINI_API_KEY

uvicorn main:app --reload --port 8000   # dev server
```

Smoke test the SSE endpoint:
```bash
curl -N "http://localhost:8000/api/process?youtube_url=<url>"
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # starts on port 5173
npm run build    # production build
```

### Spike scripts (Phase 1 only, deleted after Phase 3)

```bash
cd backend
python spike/01_download.py    # download video + captions
python spike/02_chunk.py       # parse VTT into 90-sec windows
python spike/03_render_clip.py # cut + reformat to 9:16 + burn captions
python spike/04_clip_selection.py  # Scanner + Refiner agents end-to-end
```

## Architecture

The pipeline is a LangGraph graph driven by a FastAPI SSE endpoint. Every node emits `ProgressEvent` objects into a per-request `asyncio.Queue`; the SSE endpoint drains that queue to the browser in real time.

### Pipeline flow

```
YouTube URL → ingest → transcript → scanner → refiner → [fan-out via Send API]
                                                          ├─ render_clip (×3, parallel)
                                                          ├─ write_blog
                                                          └─ write_caption (×3, parallel)
                                                                    ↓
                                                               aggregator → END
```

The `fan_out` function in `pipeline.py` returns a list of `Send` objects (LangGraph Send API). State fields that receive parallel writes (`rendered_clips`, `social_captions`) use `Annotated[List[...], operator.add]` reducers.

### Key files

| File | Role |
|---|---|
| `backend/main.py` | FastAPI app, `/api/process` SSE endpoint, `/files/{job_id}/{filename}` artifact serving |
| `backend/pipeline.py` | LangGraph graph definition, `build_graph()`, `fan_out()` |
| `backend/schemas.py` | Pydantic models — `PipelineState` is the graph's state type |
| `backend/config.py` | Env vars and constants (`GROQ_MODEL`, `GEMINI_MODEL`, `DEMO_URL`, window sizes) |
| `backend/llm/client.py` | Provider-agnostic `LLMClient` — tries Groq first, falls back to Gemini on 429/5xx |
| `backend/llm/prompts.py` | All LLM prompts as plain Python strings |
| `backend/nodes/` | One file per graph node: `ingest`, `transcript`, `scanner`, `refiner`, `clipper`, `blog_writer`, `caption_writer`, `aggregator` |
| `backend/utils/ffmpeg_utils.py` | `extract_segment_vtt()` + `render_vertical_clip()` — subtitle shift + 9:16 blurred-background reformat |
| `backend/utils/progress.py` | `ProgressEvent` model, `emit()` helper, `progress_queue` context var |
| `frontend/src/App.jsx` | Top-level state machine: `idle → processing → complete | error` |
| `frontend/src/api.js` | `startProcessing()` using `@microsoft/fetch-event-source` |

### SSE event types

`status` | `node_start` | `node_complete` | `artifact` | `error` | `done`

Artifact events carry `data.type` = `"clip"` | `"blog"` | `"caption"` | `"zip"`.

### Job isolation

Each request gets a UUID `job_id` stored on `PipelineState`. All file I/O goes to `tmp/jobs/<job_id>/`. The `/files/{job_id}/{filename}` endpoint path-traversal-checks against the `tmp/jobs/` base before serving.

## Hard constraints — do not change

- Input: public YouTube URL only, English, 5–25 min, auto-captions required
- Output: exactly 3 clips, 9:16 aspect ratio, 30–60 sec each
- No user accounts, no auth, no file upload, no history
- No face-tracking, no background music, no multi-language

## LLM provider details

- Primary: Groq `llama-3.3-70b-versatile` (JSON mode via `response_format={"type":"json_object"}`)
- Fallback: Google Gemini `gemini-2.0-flash` (JSON mode via `response_mime_type="application/json"`)
- Scanner uses `temperature=0.2`; Refiner `0.4`; Blog `0.6`; Captions `0.7`

## ffmpeg subtitle approach

After cutting a segment starting at `T` seconds, VTT timestamps are still at `T+`. Solution: `extract_segment_vtt()` writes a temp VTT with only cues in range and timestamps shifted to start at 00:00, then passes it to ffmpeg's `subtitles` filter. Vertical reformat uses blurred-background scaling (center-crop + scale + overlay).

## Deployment

`render.yaml` defines two Render services: `viral-chopper-api` (Docker, `backend/`) and `viral-chopper-ui` (static, `frontend/`). Backend needs `GROQ_API_KEY` and `GEMINI_API_KEY` as secrets. Frontend needs `VITE_API_BASE` pointing to the backend URL.
