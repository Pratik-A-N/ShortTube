import os
import re
import subprocess
from typing import Optional

import webvtt


def _vtt_time_to_sec(t: str) -> float:
    parts = t.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    m, s = parts
    return int(m) * 60 + float(s)


def _sec_to_vtt_time(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:06.3f}"


def _strip_vtt_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split())


def extract_segment_vtt(
    input_vtt: str,
    start_sec: float,
    end_sec: float,
    output_vtt: str,
) -> None:
    """Write a VTT with only cues in [start_sec, end_sec], timestamps shifted to t=0."""
    lines = ["WEBVTT\n\n"]
    for caption in webvtt.read(input_vtt):
        cue_start = _vtt_time_to_sec(caption.start)
        cue_end = _vtt_time_to_sec(caption.end)
        if cue_start >= start_sec and cue_start < end_sec:
            new_start = cue_start - start_sec
            new_end = min(cue_end - start_sec, end_sec - start_sec)
            text = _strip_vtt_tags(caption.text)
            if text:
                lines.append(f"{_sec_to_vtt_time(new_start)} --> {_sec_to_vtt_time(new_end)}\n")
                lines.append(f"{text}\n\n")

    with open(output_vtt, "w", encoding="utf-8") as f:
        f.writelines(lines)


def render_vertical_clip(
    input_video: str,
    segment_vtt: str,
    start_sec: float,
    end_sec: float,
    output_path: str,
    ffmpeg_path: Optional[str] = None,
) -> None:
    """Cut video, reformat to 9:16 with blurred background."""
    duration = end_sec - start_sec
    ffmpeg_bin = ffmpeg_path or "ffmpeg"

    vf = (
        "[0:v]scale=720:1280:force_original_aspect_ratio=increase,"
        "crop=720:1280,boxblur=20:5[bg];"
        "[0:v]scale=720:1280:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[out]"
    )

    cmd = [
        ffmpeg_bin, "-y",
        "-ss", str(start_sec),
        "-i", input_video,
        "-t", str(duration),
        "-filter_complex", vf,
        "-map", "[out]",
        "-map", "0:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr[-3000:]
        )
