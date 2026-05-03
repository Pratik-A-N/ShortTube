# Spike Scripts

These scripts de-risk the two highest-risk dependencies (yt-dlp and ffmpeg) before any FastAPI/LangGraph work. They are deleted at the end of Phase 3.

## Canonical demo URL

**https://www.youtube.com/watch?v=arj7oStGLkU**
"The surprising science of happiness" — Dan Gilbert TED Talk (~21 min, English, auto-captions confirmed)

## Run order

```bash
cd backend
pip install -r requirements.txt

python spike/01_download.py   # → tmp/video.mp4 + tmp/captions.en.vtt
python spike/02_chunk.py      # eyeball 90-sec windows
python spike/03_render_clip.py  # → tmp/clip_test.mp4
python spike/04_clip_selection.py  # → Scanner + Refiner output (Phase 2)
```

## Known-good clip range

After watching the video, update `START_SEC` / `END_SEC` in `03_render_clip.py` to a known-good 30-sec range with clear speech.

## Quirks

- If yt-dlp throws a bot-detection error, run `pip install -U yt-dlp` first.
- VTT file may land as `video.en.vtt` or `video.en-US.vtt` — `01_download.py` normalises it to `captions.en.vtt`.
- ffmpeg must be on PATH. On Windows: `winget install ffmpeg` or download from ffmpeg.org.
