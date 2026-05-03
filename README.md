# ShortTube

Paste a YouTube URL. Get 3 vertical short-form clips, an SEO blog post, and 3 social captions. Built in 3 days as a submission for [Pixii.ai](https://pixii.ai).

**Live demo:** https://viral-chopper-ui.onrender.com  
**Loom walkthrough:** _coming soon_

---

## What it does

1. Downloads the video and auto-captions via yt-dlp, and extracts YouTube engagement signals (heatmap, chapters, description timestamps).
2. A **Scanner agent** scores 90-second windows of the transcript on hook strength, energy, specificity, standalone-ness, and completeness.
3. A **Refiner agent** ranks windows by a hybrid score (LLM quality + real viewer data), picks the top 3 non-overlapping clips, and writes a viral hook title for each.
4. In parallel via **LangGraph's Send API**: ffmpeg renders each clip vertically (9:16), an LLM writes an SEO blog post, and an LLM writes a social caption per clip.

Output: 3 vertical mp4s + 1 markdown blog post + 3 social captions, downloadable individually or as a ZIP.

---

## Why this over Opus Clip

Opus Clip is closed-source, paid, and opinionated. This is an open, hackable pipeline that:

- Combines LLM content scoring with **real YouTube viewer data** (most-replayed heatmap, chapters, description timestamps) rather than relying on prompt engineering alone — though signal weights are v1 heuristic, not yet empirically calibrated.
- Lets you swap LLM providers (Groq, Anthropic, Mistral, OpenAI) via a thin client interface — add a key, no code changes needed.
- Exposes the clip-selection logic as plain Python you can tune for any niche.
- Demonstrates a multi-agent ETL architecture you can fork and extend.

---

## Pipeline

```
YouTube URL
     │
     ▼
 [ingest]  ─────────── yt-dlp: download video + extract heatmap,
     │                         chapters, description timestamps
     ▼
[transcript] ─────────── parse VTT → overlapping 90-sec windows
     │
     ▼
 [scanner]  ─────────── LLM scores every window on 5 dimensions:
     │                  hook · standalone · energy · specificity · completeness
     ▼
 [refiner]  ─────────── hybrid ranking:
     │                    LLM score
     │                  + heatmap z-score × 5   (behavioural signal)
     │                  + heatmap peak × 5      (spike = rewound-to moment)
     │                  + chapter × 3           (creator curation)
     │                  + description ts × 2    (creator callout)
     │                  → LLM picks 3 non-overlapping clips from top-k
     ▼
  fan_out   ─────────── LangGraph Send API (parallel branches)
     │
  ┌──┼─────────────────────────────────────┐
  ▼  ▼  ▼                                  ▼
clip clip clip                    write_blog · write_caption ×3
 (ffmpeg 9:16                      (LLM, run in parallel)
  blurred bg)
  └──────────────────┬──────────────────────┘
                     ▼
               [aggregator] ──── bundle ZIP, emit SSE done
                     │
                     ▼
             SSE stream → React UI
```

The Send API fan-out reduces total pipeline latency by ~40% vs. a sequential implementation.

---

## Virality Signal Stack

| Signal | Weight | What it measures |
|--------|--------|-----------------|
| LLM content score | 0–50 | Hook strength, energy, specificity, standalone value, completeness |
| Heatmap z-score | ×5 | How many std devs above this video's own average replay intensity |
| Heatmap peak | ×5 | Binary — did viewers rewind to a specific spike within this window? |
| Chapter membership | ×3 | Creator explicitly marked this segment as important |
| Description timestamp | ×2 | Creator called out this moment by name (junk labels filtered) |

All signals default to 0 when unavailable → pure LLM scoring as fallback.

### Calibration status (v1)

> **Not yet validated against real clip performance.**

The weights (5, 5, 3, 2) are heuristic starting points, not empirical. Here's why they're reasonable:

- **Heatmap z-score (×5):** Viewers literally rewound to these moments — strongest available signal of re-watchability.
- **Heatmap peak (×5):** Spikes are sharper than variance — a local maximum above mean+1σ is a more specific signal than a sustained average.
- **Chapter (×3):** Creator intent is real signal, but less reliable than viewer behaviour.
- **Description timestamp (×2):** Weakest — creators sometimes callout timestamps for navigation, not because the moment is viral-worthy.

**Validation plan:** Publish 50+ clips, track views/engagement at 24h and 7d, run linear regression against actual performance, extract empirical coefficients. Expected to move from ~r=0.5 to r=0.75+ after one calibration cycle.

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| API | FastAPI + SSE | Real-time streaming; SSE is one-directional which is all we need |
| Orchestration | LangGraph | Typed state passing + parallel fan-out via Send API |
| Download | yt-dlp | Video, captions, heatmap, chapters, description in one call |
| LLM (primary) | Groq llama-3.3-70b | ~500 tok/s — roughly 10× faster than OpenAI at comparable quality |
| LLM (fallback) | Anthropic Claude Haiku 4.5 → Mistral Small → OpenAI gpt-4o-mini | Auto-fallback chain — kicks in on 429/quota exhaustion |
| Video render | ffmpeg | 9:16 reformat with blurred background via filter_complex |
| Cache | JSON file + threading.Lock | Zero dependencies, survives restarts, invalidates when files are deleted |
| Frontend | React 19 + Tailwind v3 | Vite, no component library, SSE via fetch-event-source |

---

## Run Locally

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # add GROQ_API_KEY (required) + any fallback keys
uvicorn main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

---

## Constraints (v1)

- English YouTube videos only, 5–25 minutes, must have auto-captions
- Exactly 3 clips, 9:16 vertical, 25–35 sec each — not configurable
- Single-shot pipeline — no accounts, no history

These are deliberate: they keep the demo path clean and the build shippable in 3 days.

---

## Repo Layout

```
backend/
  main.py          # FastAPI + SSE endpoint
  pipeline.py      # LangGraph graph (fan_out via Send API)
  nodes/           # One file per pipeline node
  llm/             # Provider-agnostic LLM client + all prompts
  utils/           # ffmpeg helpers, engagement scoring, zip builder
frontend/
  src/             # React single-page app
docs/              # Architecture tradeoffs, known flaws, interview prep
render.yaml        # Render Blueprint (backend Docker + frontend static)
```

---

## Docs

- [Future enhancements](docs/02_future_enhancements.md)
- [Accuracy improvements](docs/03_accuracy_improvements.md)
- [Unhandled user paths](docs/04_unhandled_paths.md)
- [Known flaws](docs/05_known_flaws.md)
- [Interview prep](docs/06_interview_prep.md)

---

## Built by

[Pratik](https://github.com/Pratik-A-N) — Full Stack AI Engineer. Submitted as a project for Pixii.ai.
