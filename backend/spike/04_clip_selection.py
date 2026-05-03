"""
Spike 04: End-to-end test of Scanner + Refiner agents.
Assumes tmp/captions.en.vtt exists from spike 01.
"""

import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from nodes.transcript import parse_vtt_to_windows
from nodes.scanner import score_windows
from nodes.refiner import refine_clips
from llm.client import LLMClient

VTT_PATH = os.path.join(os.path.dirname(__file__), "..", "tmp", "captions.en.vtt")

windows = parse_vtt_to_windows(VTT_PATH)
duration_min = max(w.end_sec for w in windows) / 60
print(f"Parsed {len(windows)} windows from {duration_min:.1f}-min video")

llm = LLMClient()

print("\nScoring windows...")
scored = score_windows(windows, duration_min, llm)

print("\nTop 5 windows by score:")
for sw in sorted(scored, key=lambda x: -x.total)[:5]:
    print(f"  Window {sw.window_id}: total={sw.total} -- {sw.one_line_reason}")

print("\nRefining top clips...")
clips = refine_clips(scored, windows, llm)

print("\nSelected clips:")
for c in clips:
    print(f"  Clip {c.rank}: {c.start_sec:.1f}s -> {c.end_sec:.1f}s ({c.end_sec - c.start_sec:.0f}s)")
    print(f"    Hook:     {c.hook_title}")
    print(f"    Score:    {c.viral_score}")
    print(f"    Why:      {c.rationale}")
