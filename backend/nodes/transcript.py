import re
from typing import List

import webvtt

from schemas import TranscriptWindow


def _vtt_time_to_sec(t: str) -> float:
    parts = t.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    m, s = parts
    return int(m) * 60 + float(s)


def _strip_vtt_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split())


def parse_vtt_to_windows(
    vtt_path: str,
    window_size_sec: int = 90,
    stride_sec: int = 30,
) -> List[TranscriptWindow]:
    cues = []
    for caption in webvtt.read(vtt_path):
        start = _vtt_time_to_sec(caption.start)
        text = _strip_vtt_tags(caption.text)
        if text:
            cues.append((start, text))

    if not cues:
        return []

    max_time = cues[-1][0] + window_size_sec
    windows = []
    window_id = 1
    t = 0.0

    while t < max_time:
        end = t + window_size_sec
        window_cues = [text for start, text in cues if t <= start < end]
        if window_cues:
            windows.append(TranscriptWindow(
                window_id=window_id,
                start_sec=t,
                end_sec=end,
                text=" ".join(window_cues),
            ))
            window_id += 1
        t += stride_sec

    return windows


def extract_text_for_range(windows: List[TranscriptWindow], start_sec: float, end_sec: float) -> str:
    """Return concatenated window text that overlaps [start_sec, end_sec]."""
    parts = []
    for w in windows:
        if w.start_sec < end_sec and w.end_sec > start_sec:
            parts.append(w.text)
    return " ".join(parts) if parts else ""
