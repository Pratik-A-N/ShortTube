# Viral Video Chopper — Project Overview

> **Read this file first before starting any phase.**
> Each phase file (`PHASE_01.md` through `PHASE_06.md`) is self-contained and executable in order.

---

## What we're building

A web app that takes a YouTube URL and returns:
- **3 vertical (9:16) short-form clips** — 30–60 sec, with burned-in captions, named with viral hook titles, energy-ranked
- **1 SEO blog post** — 800–1200 words in markdown
- **3 social captions** — one per clip, copy-paste ready

Target user: solo YouTuber repurposing their own long-form content into Shorts/TikTok/Reels.

## Submission context

This is a 3-day project for a job application at Pixii.ai. Deadline: **May 5, 2026**. Deliverables:
1. Public GitHub repo
2. Deployed URL on Render
3. 60–90 sec Loom demo
4. Submission on HireVire

## Hard constraints (do not deviate)

- **Input**: Public YouTube URL only. English. 5–25 min. Auto-captions available.
- **No user accounts, no history, no auth.** Single-shot pipeline.
- **No file upload.** No TikTok/Instagram/X URLs. No face-tracking. No background music.
- **One aspect ratio**: 9:16. Not configurable.
- **3 clips, not 5.** Not configurable.
- **English only.** No multi-language.

## Architecture (high level)

```
YouTube URL
   ↓
[yt-dlp] download video + VTT auto-captions
   ↓
[Transcript chunked into 90-sec windows]
   ↓
[LangGraph: Scanner agent] scores windows for viral potential
   ↓
[LangGraph: Refiner agent] picks top 3, finds clean cut points, generates hook titles
   ↓ parallel (LangGraph Send API)
   ├─ [ffmpeg] cuts each clip → 9:16 → burns captions
   ├─ [LLM] writes blog post from full transcript
   └─ [LLM] writes social caption per clip
   ↓
[FastAPI SSE] streams progress to frontend
   ↓
[React] shows progress, then download buttons + "Download all (zip)"
```

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend framework | FastAPI | Reuse Code Review Agent scaffolding |
| Orchestration | LangGraph (Send API for fan-out) | Signature pattern, demonstrates multi-agent ETL |
| LLM provider (primary) | Groq (Llama 3.3 70B) | Free tier, fast |
| LLM provider (fallback) | Google Gemini | Free tier, provider-agnostic layer |
| Video download | yt-dlp | Industry standard, handles captions |
| Video processing | ffmpeg (CLI subprocess) | Mature, fast, no Python lib needed |
| Transcription fallback | faster-whisper (CPU) | Only if no auto-captions; NOT exercised in demo |
| Frontend | React (single page) | Reuse Code Review Agent shell |
| Streaming | Server-Sent Events (SSE) | Reuse Code Review Agent pattern |
| Deployment | Render | Already have the workflow |

## Project layout (final state)

```
viral-chopper/
├── backend/
│   ├── main.py                       # FastAPI app, SSE endpoint
│   ├── pipeline.py                   # LangGraph graph definition
│   ├── nodes/
│   │   ├── ingest.py                 # yt-dlp wrapper
│   │   ├── transcript.py             # chunking + timestamp utils
│   │   ├── scanner.py                # Scanner agent (score windows)
│   │   ├── refiner.py                # Refiner agent (top 3 + hooks)
│   │   ├── clipper.py                # ffmpeg clip rendering
│   │   ├── blog_writer.py            # Blog post agent
│   │   └── caption_writer.py         # Social caption agent
│   ├── llm/
│   │   ├── client.py                 # Provider-agnostic LLM client
│   │   └── prompts.py                # All prompts in one place
│   ├── utils/
│   │   ├── ffmpeg_utils.py
│   │   └── zip_utils.py
│   ├── schemas.py                    # Pydantic models
│   ├── config.py                     # env vars
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                   # Main page
│   │   ├── components/
│   │   │   ├── URLInput.jsx
│   │   │   ├── ProgressStream.jsx
│   │   │   └── ResultsPanel.jsx
│   │   └── api.js                    # SSE client
│   ├── package.json
│   └── vite.config.js
├── render.yaml                       # Render deployment config
├── .gitignore
└── README.md                         # Public-facing project doc
```

## Phase order (strict)

| Phase | File | Goal |
|---|---|---|
| 1 | `PHASE_01_ingest_spike.md` | Spike: yt-dlp + ffmpeg working end-to-end via CLI |
| 2 | `PHASE_02_clip_selection.md` | Scanner + Refiner agents picking quality clips |
| 3 | `PHASE_03_backend_pipeline.md` | FastAPI + LangGraph wiring full pipeline with SSE |
| 4 | `PHASE_04_parallel_agents.md` | Blog writer + caption writer in parallel via Send API |
| 5 | `PHASE_05_frontend.md` | React UI consuming SSE, showing results |
| 6 | `PHASE_06_deploy_and_polish.md` | Render deploy, README, Loom prep |

## Working principles for Claude Code

1. **Ship vertical slices.** Each phase produces something runnable and verifiable. No "we'll wire it up later."
2. **Constraints are not weakness.** Stated constraints in code comments and README signal product thinking.
3. **Reuse, don't rebuild.** Code Review Agent has SSE, provider-agnostic LLM, React shell, Render deploy. Copy patterns aggressively.
4. **No premature abstraction.** This is a 3-day demo. Hardcoded values are fine. Don't build a plugin system.
5. **Fail loudly, locally.** Every node logs structured progress. Every error surfaces to the SSE stream.
6. **Test the demo path, not edge cases.** Pick one canonical demo video and make it perfect end-to-end before handling weird inputs.

## The canonical demo video

Pick ONE YouTube video, 8–15 minutes long, English with auto-captions, that you'll use throughout development and in the Loom demo. Recommendation: a podcast clip, founder interview, or educational explainer with clear "hook moments." Lock this URL in `backend/config.py` as `DEMO_URL` and use it for every test run.

## Done criteria

The project is **shippable** when:
- [ ] `https://viral-chopper.onrender.com` (or similar) loads
- [ ] Pasting the canonical demo URL produces 3 clips + blog + 3 captions in under 5 min
- [ ] All artifacts are downloadable individually and as a zip
- [ ] README explains architecture, differentiation vs Opus Clip, v2 roadmap
- [ ] 60–90 sec Loom demo recorded
- [ ] HireVire form submitted with all links
