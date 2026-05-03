import re
import statistics
from typing import List, Tuple

from schemas import TranscriptWindow

_JUNK_LABEL = re.compile(
    r'\b(intro|outro|credits?|subscribe|end|opening|closing|sponsor|ads?|advertisement)\b',
    re.IGNORECASE,
)


def _normalize_heatmap(heatmap: List[dict]) -> List[dict]:
    """Return heatmap with added z_score key, clamped to 0 for below-average segments."""
    values = [s["value"] for s in heatmap]
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 1.0
    if std == 0:
        std = 1.0
    return [{**s, "z_score": max(0.0, (s["value"] - mean) / std)} for s in heatmap]


def _find_peak_times(heatmap: List[dict]) -> List[Tuple[float, float]]:
    """Return (start_time, end_time) of local maxima above mean + 1 std dev."""
    if len(heatmap) < 3:
        return []
    values = [s["value"] for s in heatmap]
    threshold = statistics.mean(values) + statistics.stdev(values)
    return [
        (heatmap[i]["start_time"], heatmap[i]["end_time"])
        for i in range(1, len(heatmap) - 1)
        if (
            heatmap[i]["value"] > threshold
            and heatmap[i]["value"] >= heatmap[i - 1]["value"]
            and heatmap[i]["value"] >= heatmap[i + 1]["value"]
        )
    ]


def window_heatmap_score(window: TranscriptWindow, heatmap: List[dict]) -> float:
    """Overlap-weighted average z-score for a window. Returns 0+ (no penalty for below-average)."""
    if not heatmap:
        return 0.0
    normed = _normalize_heatmap(heatmap)
    total_weight = total_value = 0.0
    for seg in normed:
        overlap = min(seg["end_time"], window.end_sec) - max(seg["start_time"], window.start_sec)
        if overlap > 0:
            total_weight += overlap
            total_value += seg["z_score"] * overlap
    return total_value / total_weight if total_weight > 0 else 0.0


def window_has_peak(window: TranscriptWindow, heatmap: List[dict]) -> float:
    """1.0 if a heatmap spike (local max above mean+1std) falls within this window."""
    if not heatmap:
        return 0.0
    for start, _ in _find_peak_times(heatmap):
        if window.start_sec <= start < window.end_sec:
            return 1.0
    return 0.0


def window_chapter_score(window: TranscriptWindow, chapters: List[dict]) -> float:
    """1.0 if the window's center falls inside any chapter, 0.0 otherwise."""
    if not chapters:
        return 0.0
    center = (window.start_sec + window.end_sec) / 2
    for ch in chapters:
        if ch["start_time"] <= center < ch["end_time"]:
            return 1.0
    return 0.0


def parse_description_timestamps(description: str) -> List[dict]:
    """Extract [{start_sec, label}] pairs from a YouTube description, skipping junk labels."""
    pattern = re.compile(r'(?:^|\n)\s*(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)', re.MULTILINE)
    result = []
    for m in pattern.finditer(description or ""):
        label = m.group(2).strip()
        if _JUNK_LABEL.search(label):
            continue
        parts = m.group(1).split(":")
        sec = (
            int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            if len(parts) == 3
            else int(parts[0]) * 60 + float(parts[1])
        )
        result.append({"start_sec": sec, "label": label})
    return result


def window_description_ts_score(window: TranscriptWindow, desc_timestamps: List[dict]) -> float:
    """1.0 if any description timestamp falls within the window, 0.0 otherwise."""
    if not desc_timestamps:
        return 0.0
    for ts in desc_timestamps:
        if window.start_sec <= ts["start_sec"] < window.end_sec:
            return 1.0
    return 0.0
