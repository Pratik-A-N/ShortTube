# Phase 1 — Ingest & Render Spike

> **Goal:** Prove yt-dlp + ffmpeg work end-to-end via CLI scripts, before writing any FastAPI or LangGraph code.
>
> **Time budget:** 3 hours.
>
> **Why this phase exists:** The two highest-risk dependencies in this project are external tools we don't control. If yt-dlp can't download YouTube videos in our environment, or ffmpeg can't burn captions cleanly, the rest of the project is dead. We find that out in hour 1, not on Day 3.

---

## Pre-flight

Pick a canonical demo YouTube video now. Requirements:
- Public, English, auto-captions available
- 8–15 minutes long
- Has clear "hook moments" — strong opening lines, specific claims, emotional peaks
- Save the URL — we'll use it everywhere

Recommended candidates:
- A founder interview clip on YouTube
- A short educational video (Veritasium, Ali Abdaal, etc.)
- A podcast highlight clip

**Lock the URL in your head before starting.** Don't change it during development.

---

## Files to create

```
viral-chopper/
└── backend/
    ├── spike/
    │   ├── 01_download.py      # yt-dlp wrapper, downloads video + VTT
    │   ├── 02_chunk.py         # parses VTT, prints 90-sec windows
    │   ├── 03_render_clip.py   # ffmpeg cuts + reformats to 9:16 + burns caps
    │   └── README.md           # how to run each spike
    ├── requirements.txt
    └── .gitignore
```

These spike scripts will be **deleted** at the end of Phase 3. They exist to de-risk, not to ship.

---

## File 1: `backend/requirements.txt`

Initial minimal set. We'll add to it in later phases.

```
yt-dlp>=2024.1.0
webvtt-py>=0.5.0
python-dotenv>=1.0.0
```

---

## File 2: `backend/spike/01_download.py`

**Purpose:** Download a YouTube video and its English auto-captions to a local `tmp/` folder.

**Inputs:** Hardcoded YouTube URL at top of file (your canonical demo URL).

**Outputs:**
- `tmp/video.mp4` — the video file
- `tmp/captions.en.vtt` — auto-captions in WebVTT format

**Implementation requirements:**
- Use `yt-dlp` Python module (not subprocess) so we can read it programmatically later.
- Request `bestvideo[height<=720]+bestaudio` — 720p is plenty for clip generation, smaller files = faster.
- Request English auto-captions (`writeautomaticsub=True`, `subtitleslangs=['en']`, `subtitlesformat='vtt'`).
- Print metadata after download: video title, duration in seconds, has_captions (bool).

**Acceptance test:**
```bash
cd backend
python spike/01_download.py
# Should print:
# Downloaded: <video title>
# Duration: <seconds>s
# Captions: True
# Files: tmp/video.mp4 (<size>), tmp/captions.en.vtt (<size>)
```

**If it fails:**
- Bot detection error: try `yt-dlp` upgrade to latest, or add a custom User-Agent.
- No captions: pick a different demo video. Don't fall back to Whisper yet — that's a Phase 3 concern.
- Region lock: pick a different demo video.

**Do NOT proceed to File 3 until this spike works.**

---

## File 3: `backend/spike/02_chunk.py`

**Purpose:** Parse the VTT file and print 90-second sliding windows with timestamps.

**Inputs:** `tmp/captions.en.vtt` from File 2.

**Outputs:** Print to stdout — each window:
```
[Window 1] 00:00 → 01:30
<concatenated caption text>

[Window 2] 00:30 → 02:00
<concatenated caption text>
```

**Implementation requirements:**
- Use `webvtt-py` to parse the VTT.
- Sliding windows: 90 seconds wide, stride 30 seconds (so we get overlapping coverage).
- For each window, concatenate all caption cues whose start time falls within the window.
- Strip VTT formatting tags (`<c>`, `<00:01:23.456>`, etc.) — Whisper-style auto-captions are noisy.

**Acceptance test:** Eyeball the output. The text should be coherent English sentences. If it looks like garbage with HTML-style tags, your stripping logic is broken — fix it now, because the Scanner agent will choke on noisy text.

**Edge cases to handle:**
- Empty windows (last window if video < 90s) — skip them.
- Captions with overlapping cues — just concatenate, don't dedupe yet.

---

## File 4: `backend/spike/03_render_clip.py`

**Purpose:** Cut a hardcoded 30-second segment from the video, reformat to 9:16 vertical with burned-in captions.

**Inputs:**
- `tmp/video.mp4`
- `tmp/captions.en.vtt`
- Hardcoded start_seconds and end_seconds at top of file (pick a known-good 30-sec range from your demo video).

**Outputs:**
- `tmp/clip_test.mp4` — vertical 9:16 clip with burned-in captions

**Implementation requirements:**

Use ffmpeg via `subprocess.run`. The command needs to:
1. Cut the segment by timestamp (`-ss` and `-to`).
2. Convert from horizontal (16:9) to vertical (9:16) by **center-cropping** to a square then padding top/bottom with blurred background, OR by **scaling and padding with black bars**. **Recommendation: blurred background** — looks more professional. If that takes more than 30 min to get working, fall back to black bars.
3. Burn in subtitles from the VTT, **only for the segment's time range**. This is the trickiest part.

**The subtitle burn-in challenge:** ffmpeg's `subtitles` filter expects the subtitle file to be aligned with t=0 of the video. After we cut a segment starting at, say, 02:30, the subtitle timestamps are still at 02:30+, not 00:00+. Two solutions:

- **Solution A (recommended):** Generate a temporary VTT containing only the cues in the target range, with timestamps shifted to start at 00:00. Pass that to ffmpeg's `subtitles` filter. Clean and reliable.
- **Solution B:** Use ffmpeg's `setpts` and subtitle offset options. More complex, easier to get wrong.

Go with A. Write a helper function `extract_segment_vtt(input_vtt, start_sec, end_sec, output_vtt)`.

**Subtitle styling:** Use ffmpeg's `force_style` option to make captions readable on mobile:
- Font: Arial (or system default), size 18-24
- Color: white with black outline
- Position: bottom-center
- Bold

**Acceptance test:**
```bash
python spike/03_render_clip.py
# Outputs tmp/clip_test.mp4
```
Open the file. It must be:
- Vertical (taller than wide)
- Have visible, readable captions
- Audio in sync with video
- 30 seconds long

**If burned captions are misaligned by a few seconds:** check VTT timestamp shift logic. Off-by-one is the usual culprit.

**Time-box this aggressively.** If you've spent 90 min and captions still aren't burning correctly, ship without burned captions for v1 and note it as v2 in the README. The project survives that compromise. It does not survive a 4-hour caption rabbit hole on Day 1.

---

## File 5: `backend/spike/README.md`

Brief notes for yourself on:
- The canonical demo URL
- Any quirks you hit (e.g. "had to upgrade yt-dlp", "bot detection on first run")
- The known-good 30-sec timestamp range from File 4

This becomes useful in Phase 6 when writing the public README.

---

## File 6: `backend/.gitignore`

```
__pycache__/
*.pyc
.env
tmp/
venv/
.venv/
```

---

## Phase 1 done criteria

- [ ] `python spike/01_download.py` produces `tmp/video.mp4` and `tmp/captions.en.vtt`
- [ ] `python spike/02_chunk.py` prints clean, readable 90-sec windows from the VTT
- [ ] `python spike/03_render_clip.py` produces a vertical 9:16 mp4 with burned-in captions
- [ ] You can play `tmp/clip_test.mp4` and it looks like something you'd actually post on TikTok
- [ ] All three risks (yt-dlp works, VTT is parseable, ffmpeg burns captions) are retired

**If any of these fail, do NOT move to Phase 2.** Fix the spike or scope down (e.g., ship without burned captions). Phase 2 assumes these tools work.

---

## What we're explicitly NOT doing in Phase 1

- No FastAPI, no React, no LangGraph
- No LLM calls
- No error handling beyond "let it crash and print a clear message"
- No Whisper fallback for missing captions
- No cleanup of `tmp/` between runs
- No tests beyond manual eyeball checks

These are all correct things to defer. The spike's only job is "do the external tools work."
