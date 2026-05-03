"""
Spike 03: Cut a segment from the video, reformat to 9:16 vertical, burn captions.
Input:  tmp/video.mp4, tmp/captions.en.vtt
Output: tmp/clip_test.mp4
"""

import os
import re
import subprocess
import webvtt

VIDEO_PATH = os.path.join(os.path.dirname(__file__), "..", "tmp", "video.mp4")
VTT_PATH   = os.path.join(os.path.dirname(__file__), "..", "tmp", "captions.en.vtt")
OUT_PATH   = os.path.join(os.path.dirname(__file__), "..", "tmp", "clip_test.mp4")

# Hardcode a known-good 30-sec range — update after watching the video
START_SEC = 60.0
END_SEC   = 90.0


def vtt_time_to_sec(t: str) -> float:
    parts = t.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    m, s = parts
    return int(m) * 60 + float(s)


def sec_to_vtt_time(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:06.3f}"


def strip_vtt_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split())


def extract_segment_vtt(input_vtt: str, start_sec: float, end_sec: float, output_vtt: str) -> None:
    """Write a VTT with only cues in [start_sec, end_sec], timestamps shifted to t=0."""
    lines = ["WEBVTT\n\n"]
    for caption in webvtt.read(input_vtt):
        cue_start = vtt_time_to_sec(caption.start)
        cue_end   = vtt_time_to_sec(caption.end)
        if cue_start >= start_sec and cue_start < end_sec:
            new_start = cue_start - start_sec
            new_end   = min(cue_end - start_sec, end_sec - start_sec)
            text = strip_vtt_tags(caption.text)
            if text:
                lines.append(f"{sec_to_vtt_time(new_start)} --> {sec_to_vtt_time(new_end)}\n")
                lines.append(f"{text}\n\n")

    with open(output_vtt, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Segment VTT written: {output_vtt}")


def render_vertical_clip(
    input_video: str,
    segment_vtt: str,
    start_sec: float,
    end_sec: float,
    output_path: str,
) -> None:
    """Cut video, reformat to 9:16 with blurred background, burn captions."""
    duration = end_sec - start_sec

    # Use forward slashes for ffmpeg on Windows (avoid escape issues in subtitles filter)
    segment_vtt_ffmpeg = segment_vtt.replace("\\", "/").replace(":", "\\:")

    # Video filter chain:
    # 1. Scale to fit 1080 wide, crop height to 1920 (9:16)
    # 2. For background: scale + blur the original frame
    # 3. Overlay sharp center crop on blurred background
    # 4. Burn subtitles
    vf = (
        # Blurred background: scale to fill 1080x1920, then boxblur
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=20:5[bg];"
        # Sharp foreground: scale to fit within 1080x1920 keeping aspect
        "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
        # Overlay fg centered on bg
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[v];"
        # Burn captions
        f"[v]subtitles='{segment_vtt_ffmpeg}':force_style="
        "'FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=2,Bold=1,"
        "Alignment=2,MarginV=60'[out]"
    )

    cmd = [
        "ffmpeg", "-y",
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

    print(f"Running ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg stderr:", result.stderr[-2000:])
        result.check_returncode()
    print(f"Output: {output_path}")


if __name__ == "__main__":
    tmp_dir = os.path.join(os.path.dirname(__file__), "..", "tmp")
    segment_vtt = os.path.join(tmp_dir, "clip_test_segment.vtt")

    print(f"Extracting segment {START_SEC}s -> {END_SEC}s")
    extract_segment_vtt(VTT_PATH, START_SEC, END_SEC, segment_vtt)
    render_vertical_clip(VIDEO_PATH, segment_vtt, START_SEC, END_SEC, OUT_PATH)
    print(f"\nDone. Open tmp/clip_test.mp4 to verify:")
    print("  - Vertical (taller than wide)")
    print("  - Readable captions at bottom")
    print("  - Audio in sync")
    print(f"  - ~{int(END_SEC - START_SEC)} seconds long")
