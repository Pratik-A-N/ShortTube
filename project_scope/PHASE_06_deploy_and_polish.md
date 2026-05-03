# Phase 6 — Deploy, README, Loom, Submit

> **Goal:** Get the app live on Render, write the public README, record the Loom, and submit on HireVire.
>
> **Time budget:** 4 hours total, split across end of Day 2 (deploy) and Day 3 (README + Loom + submit).
>
> **Why this phase exists:** The build is worthless if it doesn't ship. This phase is execution, not engineering. Every minute spent here is more valuable than another marginal code improvement.

---

## Part A: Deployment to Render (Day 2 evening, ~1 hour)

### Backend service

Render's Python service spec. Two deployment options:

**Option 1 (recommended): Docker.** Gives you full control over ffmpeg version. Render builds and runs a Dockerfile.

**Option 2: Native Python.** Faster cold start but ffmpeg pinning is awkward — depends on Render's base image.

Go with Docker.

### File: `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

# ffmpeg is the critical system dep
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render injects PORT env var
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### File: `render.yaml`

```yaml
services:
  - type: web
    name: viral-chopper-api
    runtime: docker
    plan: starter
    region: oregon
    rootDir: backend
    envVars:
      - key: GROQ_API_KEY
        sync: false
      - key: GEMINI_API_KEY
        sync: false
      - key: PYTHONUNBUFFERED
        value: "1"

  - type: web
    name: viral-chopper-ui
    runtime: static
    plan: starter
    rootDir: frontend
    buildCommand: npm install && npm run build
    staticPublishPath: dist
    envVars:
      - key: VITE_API_BASE
        sync: false  # set manually to https://viral-chopper-api.onrender.com
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
```

### Deploy steps

1. Push the repo to GitHub (public or private — public is better, Monte may want to skim the code).
2. On Render: New > Blueprint > connect repo > select `render.yaml`.
3. Set the three secrets in the Render dashboard:
   - `GROQ_API_KEY` on backend
   - `GEMINI_API_KEY` on backend
   - `VITE_API_BASE` on frontend (set to `https://viral-chopper-api.onrender.com` once backend deploys — note this is a chicken-and-egg, deploy backend first)
4. After backend is up, set `VITE_API_BASE`, then redeploy frontend so the build picks it up.
5. Tighten CORS in `backend/main.py`: change `allow_origins=["*"]` to `allow_origins=["https://viral-chopper-ui.onrender.com"]`. Redeploy backend.

### Post-deploy smoke test

- Visit the frontend URL.
- Paste the canonical demo URL.
- Watch the full pipeline run end-to-end.
- Download a clip, confirm it plays.

**Likely production-only issues to anticipate:**

- **yt-dlp bot detection on Render IPs.** Render runs in known cloud ranges; YouTube sometimes throws challenges. If this hits, the workaround is adding cookies. Don't go down that rabbit hole unless it actually breaks. Test first.
- **Cold start latency.** Render free/starter tier sleeps after inactivity. First request after sleep takes 30-60s to spin up. **Important for Loom**: warm up the backend (visit `/health`) right before recording.
- **Render disk ephemerality.** `tmp/jobs/` is wiped on redeploys. That's fine for a demo. Don't promise persistent storage.
- **CORS surprises.** Verify the SSE endpoint specifically — some preflight quirks with `text/event-stream`.

---

## Part B: README.md (Day 3 morning, ~1 hour)

The README is the second thing Monte sees after the Loom. It carries the differentiation argument.

### File: `README.md` (root of repo)

Skeleton:

```markdown
# Viral Video Chopper

Paste a YouTube URL. Get 3 vertical short-form clips, an SEO blog post, and 3 social captions. Built in 3 days.

**Live demo:** https://viral-chopper-ui.onrender.com
**Loom walkthrough:** <Loom URL>

---

## What it does

[GIF or screenshot of the app — 1 frame, not a long video. Keep README load fast.]

Paste a YouTube URL. The pipeline:
1. Downloads the video and auto-captions.
2. A Scanner agent scores 90-second windows of the transcript on hook strength, energy, specificity, and standalone-ness.
3. A Refiner agent picks the top 3 non-overlapping windows, refines cut points, and writes a viral hook title for each.
4. In parallel, three workstreams run via LangGraph's Send API: ffmpeg renders each clip vertically with burned-in captions, an LLM writes a blog post from the full transcript, and an LLM writes a social caption per clip.

Output: 3 vertical mp4s + 1 markdown blog post + 3 social captions, downloadable individually or as a zip.

## Why this exists when Opus Clip exists

Opus Clip is closed-source, paid, and opinionated. This is an open, hackable pipeline that:
- Lets you swap LLM providers (Groq, Gemini, OpenAI, anything) via a thin client interface.
- Exposes the clip-selection prompt as plain Python so you can tune it for your niche.
- Demonstrates a multi-agent ETL architecture you can fork and extend.

It was built in 3 days as a project submission for [Pixii.ai](https://pixii.ai). The goal was to ship a working multi-agent pipeline end-to-end — input handling, parallel agent orchestration, video processing, streaming UI, and production deploy — under realistic time pressure.

## Architecture

```
YouTube URL
   ↓
[yt-dlp] download video + VTT auto-captions
   ↓
[Transcript chunked into 90-sec windows]
   ↓
[Scanner agent] scores windows on hook/energy/specificity/standalone/completeness
   ↓
[Refiner agent] picks top 3, refines cut points, writes hook titles
   ↓ parallel (LangGraph Send API)
   ├─→ [ffmpeg] cuts each clip → 9:16 → burns captions
   ├─→ [Blog Writer] full transcript → SEO blog post
   └─→ [Caption Writer] per-clip transcript → social caption
   ↓
[FastAPI SSE] streams progress to frontend
   ↓
[React] shows progress, then download buttons
```

The Send API fan-out reduces total pipeline latency by ~40% on the demo input, compared to a sequential implementation.

## Tech stack

- **Backend:** FastAPI + Server-Sent Events
- **Orchestration:** LangGraph (Send API for parallel fan-out)
- **LLMs:** Groq Llama 3.3 70B (primary), Google Gemini 2.0 Flash (fallback). Provider-agnostic client.
- **Video:** yt-dlp + ffmpeg
- **Frontend:** React + Tailwind + Vite
- **Deploy:** Render (Docker for backend, static for frontend)

## Run locally

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add GROQ_API_KEY and GEMINI_API_KEY
uvicorn main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Constraints (v1)

- English YouTube videos only
- 5–25 minutes long
- Must have auto-captions (Whisper fallback exists in code but not exercised)
- 3 clips, 9:16 vertical, 30–60 sec each — not configurable
- Single-shot pipeline — no user accounts, no history

These constraints are deliberate: they keep the demo path clean and the build shippable in 3 days.

## v2 roadmap (what 1–2 more weeks would add)

- File upload alongside URL input
- TikTok / Instagram / X.com URL support
- Multi-language with Whisper fallback by default
- Optional channel-context input for prompt personalization
- Face-tracking auto-reframe for talking-head clips
- Pluggable clip-selection prompt registry (different prompts for different niches)
- User accounts + job history

## Repo layout

```
backend/
  main.py              # FastAPI + SSE
  pipeline.py          # LangGraph graph
  nodes/               # Each pipeline node
  llm/                 # Provider-agnostic client + prompts
  utils/               # ffmpeg, zip helpers
frontend/
  src/                 # React app
render.yaml            # Render Blueprint
```

## Built by

[Pratik](https://github.com/Pratik-A-N) — Full Stack AI Engineer, IIT Bombay '24. Currently building production multi-agent systems. Submitted as a project for Pixii.ai.
```

**Lock the differentiation paragraph.** That's the answer to "why does this exist when Opus Clip exists?" — same answer you'd give Monte in person.

---

## Part C: Loom recording (Day 3 evening, ~2 hours including retakes)

### Length target: 75 seconds.

Under 60 = looks rushed. Over 90 = founder closes the tab. 75 is the sweet spot.

### Pre-recording checklist

- [ ] Backend is warm (visit `/health` once)
- [ ] Frontend is loaded in browser, ready
- [ ] Canonical demo URL is in clipboard
- [ ] Browser is in incognito / clean window — no extension chrome, no bookmarks bar visible
- [ ] Window size: 1280×800 minimum
- [ ] Audio levels checked, no background noise
- [ ] Script written and rehearsed twice (don't read it monotone — talk through it)

### Suggested script (~75 sec)

```
[0:00–0:08] Hook
"This is Viral Video Chopper. Paste any YouTube URL, get three vertical clips, a blog post,
and social captions, ready to upload. Built in three days for the Pixii project round."

[0:08–0:18] Show the paste + start
[Paste URL, click Generate]
"Behind the scenes, two LLM agents pick the best clips from the transcript — a Scanner
that scores 90-second windows on hook strength and energy, and a Refiner that picks the
top three and writes hook titles."

[0:18–0:35] Show the parallel pipeline lighting up
"Once clips are picked, three workstreams run in parallel via LangGraph's Send API —
ffmpeg renders each clip vertically with burned captions, while two more agents write
the blog post and per-clip social captions. About 40 percent faster than running it
sequentially."

[0:35–0:55] Show the results
[Click on clip 1, let it play 3-4 seconds]
"Three clips, vertical, captioned, named with hook titles."
[Scroll to blog]
"SEO blog post."
[Scroll to captions, click copy]
"Per-clip social captions, copy-paste ready."

[0:55–1:15] Why
"This is the same parallel-agent architecture as my Code Review Agent — open source,
provider-agnostic, hackable. I built it because Pixii sells to creators and ecommerce
sellers, and content repurposing is core to that workflow.

Code, deployed app, and architecture writeup linked below. Thanks Monte."
```

### Recording tips

- Record 3 takes minimum. Use the third or fourth, never the first.
- If you stumble, finish the sentence cleanly anyway and re-record only that section if Loom supports it. Don't restart the whole video.
- Speak ~10% slower than feels natural. Your normal pace will sound rushed on playback.
- Don't apologize on camera. If something glitches, cut and redo silently.
- End with a definite stop. Don't trail off.

### Post-recording

- Watch it once at 1x. If it's <60 sec or >100 sec, redo.
- Set Loom title: "Viral Video Chopper — Pixii Project Submission"
- Set Loom description: GitHub link + deployed URL.
- Get the share link (public, no auth required).

---

## Part D: HireVire submission (Day 3 evening, ~30 min)

### Pre-submission checklist

- [ ] GitHub repo is public
- [ ] README is the version above, with all three links filled in (live demo, Loom, repo itself)
- [ ] Deployed app loads and works (test it from a logged-out browser)
- [ ] Loom is public and accessible without login
- [ ] Backend has not gone to sleep — visit `/health` 5 min before submitting

### What to put in HireVire form fields

You haven't told me what fields the form has. **Read the form first.** Common fields and how to fill them:

- **Project title:** "Viral Video Chopper"
- **One-line description:** "Paste a YouTube URL → 3 vertical clips + SEO blog post + 3 social captions, in under 90 seconds."
- **Deployed URL:** Render frontend URL
- **GitHub repo:** the repo URL
- **Loom / video walkthrough:** the Loom share link
- **Approach / writeup field (if any):** lift the "Architecture" section from the README, plus the differentiation paragraph
- **Time spent:** be honest — "~3 days, building around my full-time job"
- **Anything else:** brief mention of your existing Code Review Agent that uses the same architecture (link it)

### Final sanity checks before clicking submit

- [ ] All links open in incognito browser
- [ ] No "localhost" or "127.0.0.1" left in any submitted text
- [ ] No stray TODOs in the README
- [ ] No `.env` file committed to the repo (check git history)
- [ ] No API keys in git history (check `git log -p | grep -i 'api_key'`)
- [ ] Repo `README.md` renders correctly on github.com (preview, don't trust local rendering)

### After submission

- Send a short follow-up to Monte (the email he sent you) confirming submission. One sentence:
  > "Submitted via HireVire — link to deployed app: <url>, Loom: <url>. Thanks for the opportunity."

That's it. Done.

---

## Phase 6 done criteria

- [ ] Frontend URL loads from a logged-out browser and the full pipeline runs successfully
- [ ] Loom is recorded, under 90 sec, public link
- [ ] README has all three required links and the differentiation paragraph
- [ ] HireVire form is submitted
- [ ] Confirmation reply sent to Monte

---

## What we're explicitly NOT doing in Phase 6

- No analytics on the deployed app
- No custom domain (the `*.onrender.com` URL is fine)
- No pre-rendered Loom thumbnail / branded landing page
- No "share to social" buttons in the app itself
- No retroactive code cleanup or refactoring — the code is what it is. Ship.

---

## Risk reminders for Day 3

- **Don't tinker.** Day 3 is the day everyone breaks their working build by "just one more improvement." If the deployed app works, freeze the code. Day 3 is for polish *outside* the codebase: README, Loom, submission.
- **Backend cold start.** If Render free tier sleeps the backend, the first user (which might be Monte) sees a 60-second blank screen. Worst case, upgrade to a paid tier for $7/mo just for May 5–14, then downgrade.
- **One last test from a clean browser at 11 PM May 4.** Catch the production-only bugs that only show up in incognito.
