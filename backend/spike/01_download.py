"""
Spike 01: Download a YouTube video + English auto-captions via yt-dlp.
Outputs: tmp/video.mp4, tmp/captions.en.vtt
"""

import os
import yt_dlp

# Canonical demo video — 10-min educational explainer with auto-captions
DEMO_URL = "https://www.youtube.com/watch?v=arj7oStGLkU"

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "tmp")
os.makedirs(OUT_DIR, exist_ok=True)

ydl_opts = {
    # Single-file format (no ffmpeg merging needed for download)
    "format": "best[height<=720][ext=mp4]/best[height<=720]/best",
    "outtmpl": os.path.join(OUT_DIR, "video.%(ext)s"),
    "writeautomaticsub": True,
    "subtitleslangs": ["en"],
    "subtitlesformat": "vtt",
    "quiet": False,
    "no_warnings": False,
}

print(f"Downloading: {DEMO_URL}")
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(DEMO_URL, download=True)

title = info.get("title", "Unknown")
duration = info.get("duration", 0)

video_path = os.path.join(OUT_DIR, "video.mp4")
vtt_candidates = [
    os.path.join(OUT_DIR, "video.en.vtt"),
    os.path.join(OUT_DIR, "video.en-US.vtt"),
]
vtt_path = next((p for p in vtt_candidates if os.path.exists(p)), None)

# Normalise caption file to captions.en.vtt
if vtt_path and vtt_path != os.path.join(OUT_DIR, "captions.en.vtt"):
    os.rename(vtt_path, os.path.join(OUT_DIR, "captions.en.vtt"))
    vtt_path = os.path.join(OUT_DIR, "captions.en.vtt")

has_captions = vtt_path is not None and os.path.exists(vtt_path)

video_size = os.path.getsize(video_path) // (1024 * 1024) if os.path.exists(video_path) else 0
vtt_size = os.path.getsize(vtt_path) // 1024 if has_captions else 0

print(f"\nDownloaded: {title}")
print(f"Duration: {duration}s")
print(f"Captions: {has_captions}")
print(f"Files: tmp/video.mp4 ({video_size}MB), tmp/captions.en.vtt ({vtt_size}KB)")

if not has_captions:
    print("\nWARNING: No auto-captions found. Pick a different demo video.")
