"""
Spike 02: Parse VTT captions into 90-second sliding windows.
Input:  tmp/captions.en.vtt
Output: prints windows to stdout
"""

import os
import re
import webvtt

VTT_PATH = os.path.join(os.path.dirname(__file__), "..", "tmp", "captions.en.vtt")
WINDOW_SIZE_SEC = 90
STRIDE_SEC = 30


def vtt_time_to_sec(t: str) -> float:
    """'00:01:23.456' → 83.456"""
    parts = t.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    m, s = parts
    return int(m) * 60 + float(s)


def strip_vtt_tags(text: str) -> str:
    """Remove <c>, <00:00:00.000>, and other VTT inline tags."""
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split())


def parse_vtt_to_windows(vtt_path: str, window_size: int = 90, stride: int = 30):
    cues = []
    for caption in webvtt.read(vtt_path):
        start = vtt_time_to_sec(caption.start)
        text = strip_vtt_tags(caption.text)
        if text:
            cues.append((start, text))

    if not cues:
        print("No cues found in VTT.")
        return []

    max_time = cues[-1][0] + window_size
    windows = []
    window_id = 1
    t = 0.0

    while t < max_time:
        end = t + window_size
        window_cues = [text for start, text in cues if t <= start < end]
        if window_cues:
            windows.append({
                "window_id": window_id,
                "start_sec": t,
                "end_sec": end,
                "text": " ".join(window_cues),
            })
            window_id += 1
        t += stride

    return windows


if __name__ == "__main__":
    windows = parse_vtt_to_windows(VTT_PATH)
    for w in windows:
        start_m, start_s = divmod(int(w["start_sec"]), 60)
        end_m, end_s = divmod(int(w["end_sec"]), 60)
        print(f"\n[Window {w['window_id']}] {start_m:02d}:{start_s:02d} -> {end_m:02d}:{end_s:02d}")
        print(w["text"][:300] + ("..." if len(w["text"]) > 300 else ""))

    print(f"\nTotal windows: {len(windows)}")
