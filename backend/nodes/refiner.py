import json
import logging
from typing import List, Optional

from llm.client import LLMClient
from llm.prompts import REFINER_SYSTEM, REFINER_USER
from schemas import TranscriptWindow, ScoredWindow, SelectedClip
from config import CLIP_MIN_SEC, CLIP_MAX_SEC
from utils.engagement import (
    window_heatmap_score, window_has_peak,
    window_chapter_score, window_description_ts_score,
)

logger = logging.getLogger(__name__)


def refine_clips(
    scored_windows: List[ScoredWindow],
    windows: List[TranscriptWindow],
    llm: LLMClient,
    video_duration: float = float("inf"),
    top_k: int = 8,
    num_clips: int = 3,
    heatmap: Optional[List[dict]] = None,
    chapters: Optional[List[dict]] = None,
    description_timestamps: Optional[List[dict]] = None,
) -> List[SelectedClip]:
    heatmap = heatmap or []
    chapters = chapters or []
    description_timestamps = description_timestamps or []

    window_map = {w.window_id: w for w in windows}

    def hybrid_score(sw: ScoredWindow) -> float:
        w = window_map.get(sw.window_id)
        if not w:
            return float(sw.total)
        return (
            sw.total
            + window_heatmap_score(w, heatmap) * 5   # z-score: 0 to ~2.5 typical
            + window_has_peak(w, heatmap) * 5         # spike bonus: rewound-to moment
            + window_chapter_score(w, chapters) * 3
            + window_description_ts_score(w, description_timestamps) * 2
        )

    top = sorted(scored_windows, key=lambda x: -hybrid_score(x))[:top_k]

    for sw in top[:5]:
        w = window_map.get(sw.window_id)
        if w:
            logger.info(
                f"Window {sw.window_id} hybrid={hybrid_score(sw):.1f} "
                f"(llm={sw.total} "
                f"heat={window_heatmap_score(w, heatmap)*5:.1f} "
                f"peak={window_has_peak(w, heatmap)*5:.0f} "
                f"chapter={window_chapter_score(w, chapters)*3:.0f} "
                f"dts={window_description_ts_score(w, description_timestamps)*2:.0f})"
            )

    candidate_windows = [window_map[sw.window_id] for sw in top if sw.window_id in window_map]

    lines = []
    for sw in top:
        w = window_map.get(sw.window_id)
        if not w:
            continue
        start_m, start_s = divmod(int(w.start_sec), 60)
        end_m, end_s = divmod(int(w.end_sec), 60)
        lines.append(
            f"Window {sw.window_id} | {start_m:02d}:{start_s:02d} -> {end_m:02d}:{end_s:02d} "
            f"| start_sec={w.start_sec} | end_sec={w.end_sec} | total={sw.total}"
        )
        lines.append(w.text[:800])
        lines.append("")
    top_windows_text = "\n".join(lines)

    user_prompt = REFINER_USER.format(top_windows_text=top_windows_text)
    raw = llm.complete(REFINER_SYSTEM, user_prompt, response_format="json", temperature=0.4, max_tokens=2048)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Refiner JSON parse failed. Raw:\n{raw[:500]}")
        raise

    clips = []
    for item in data.get("clips", []):
        try:
            clips.append(SelectedClip(**item))
        except Exception as e:
            logger.warning(f"Skipping malformed clip from LLM: {e} | item={item}")

    clips = _validate_clips(clips, candidate_windows, video_duration)

    # If the LLM + validation left us short, fill from unused top windows directly
    if len(clips) < num_clips:
        logger.warning(f"Only {len(clips)} valid clips after validation — filling from scanner windows")
        clips = _fill_from_windows(clips, candidate_windows, video_duration, num_clips)

    # Attach signal tags so the UI can show which data sources agreed on each clip
    final = []
    for clip in clips[:num_clips]:
        w = _closest_window(clip.start_sec, clip.end_sec, candidate_windows)
        tags = []
        if w:
            if window_has_peak(w, heatmap):
                tags.append("heatmap_peak")
            if window_chapter_score(w, chapters):
                tags.append("chapter")
            if window_description_ts_score(w, description_timestamps):
                tags.append("creator_highlight")
        final.append(clip.model_copy(update={"signal_tags": tags}))

    logger.info(f"Refiner selected {len(final)} clips")
    return final


def _closest_window(
    start: float, end: float, windows: List[TranscriptWindow]
) -> Optional[TranscriptWindow]:
    """Return the window with the most overlap with [start, end].
    If no window overlaps, return the nearest one by gap distance."""
    best, best_score = None, float("-inf")
    for w in windows:
        score = min(end, w.end_sec) - max(start, w.start_sec)  # positive = overlap, negative = gap
        if score > best_score:
            best_score = score
            best = w
    return best


def _validate_clips(
    clips: List[SelectedClip],
    candidate_windows: List[TranscriptWindow],
    video_duration: float,
) -> List[SelectedClip]:
    validated = []
    for clip in clips:
        start = max(0.0, clip.start_sec)
        end = min(video_duration, clip.end_sec)

        # Snap to the closest real transcript window so hallucinated timestamps
        # always map to content that actually exists in the video.
        window = _closest_window(start, end, candidate_windows)
        if window:
            has_overlap = min(end, window.end_sec) - max(start, window.start_sec) > 0
            if has_overlap:
                start = max(start, window.start_sec)
                end = min(end, window.end_sec)
            else:
                # Timestamps are completely outside any real window — use window bounds
                logger.warning(
                    f"Clip {clip.rank} timestamps ({start:.1f}-{end:.1f}s) outside all windows; "
                    f"snapping to window {window.window_id} ({window.start_sec:.1f}-{window.end_sec:.1f}s)"
                )
                start = window.start_sec
                end = window.end_sec

        # Enforce duration constraints
        duration = end - start
        if duration < CLIP_MIN_SEC:
            end = min(video_duration, start + CLIP_MIN_SEC)
            if end - start < CLIP_MIN_SEC and window:
                start, end = window.start_sec, window.end_sec
        elif duration > CLIP_MAX_SEC:
            end = start + CLIP_MAX_SEC

        validated.append(clip.model_copy(update={"start_sec": round(start, 2), "end_sec": round(end, 2)}))

    # Remove overlapping clips (keep lower rank = higher viral priority)
    non_overlapping = []
    for clip in sorted(validated, key=lambda c: c.rank):
        overlaps = any(
            not (clip.end_sec <= prev.start_sec or clip.start_sec >= prev.end_sec)
            for prev in non_overlapping
        )
        if overlaps:
            logger.warning(f"Dropping clip {clip.rank} — overlaps with existing selection")
        else:
            non_overlapping.append(clip)

    return non_overlapping


def _fill_from_windows(
    existing: List[SelectedClip],
    candidate_windows: List[TranscriptWindow],
    video_duration: float,
    num_clips: int,
) -> List[SelectedClip]:
    """Fill missing clip slots directly from top-scored windows (no LLM)."""
    clips = list(existing)
    next_rank = max((c.rank for c in clips), default=0) + 1

    for w in candidate_windows:
        if len(clips) >= num_clips:
            break
        overlaps = any(
            not (w.end_sec <= c.start_sec or w.start_sec >= c.end_sec)
            for c in clips
        )
        if overlaps:
            continue

        end = min(w.end_sec, w.start_sec + CLIP_MAX_SEC, video_duration)
        hook = " ".join(w.text.split()[:8]) + "…" if w.text else "Video excerpt"
        clips.append(SelectedClip(
            rank=next_rank,
            start_sec=round(w.start_sec, 2),
            end_sec=round(end, 2),
            hook_title=hook,
            viral_score=0,
            rationale="Fallback: taken directly from scanner window",
        ))
        next_rank += 1

    return clips
