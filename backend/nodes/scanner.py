import asyncio
import json
import logging
import math
from typing import Callable, Coroutine, List

from llm.client import LLMClient
from llm.prompts import SCANNER_SYSTEM, SCANNER_USER
from schemas import TranscriptWindow, ScoredWindow

logger = logging.getLogger(__name__)

SCANNER_BATCH_SIZE = 15  # ~2800 input tokens per call, well under Groq's 12k limit


async def score_windows(
    windows: List[TranscriptWindow],
    duration_min: float,
    llm: LLMClient,
    on_batch_done: Callable[[int, int], Coroutine] | None = None,
) -> List[ScoredWindow]:
    num_batches = math.ceil(len(windows) / SCANNER_BATCH_SIZE)
    logger.info(f"Scanner: {len(windows)} windows → {num_batches} batch(es) of ≤{SCANNER_BATCH_SIZE}")

    loop = asyncio.get_event_loop()
    scored: List[ScoredWindow] = []

    for i in range(num_batches):
        batch = windows[i * SCANNER_BATCH_SIZE : (i + 1) * SCANNER_BATCH_SIZE]
        # Run blocking LLM call in thread pool so the event loop stays free to flush SSE
        result = await loop.run_in_executor(None, _score_batch, batch, duration_min, llm, i + 1)
        scored.extend(result)
        if on_batch_done:
            await on_batch_done(i + 1, num_batches)

    logger.info(f"Scanner scored {len(scored)} windows total")
    return scored


def _score_batch(
    windows: List[TranscriptWindow],
    duration_min: float,
    llm: LLMClient,
    batch_num: int = 1,
) -> List[ScoredWindow]:
    lines = []
    for w in windows:
        start_m, start_s = divmod(int(w.start_sec), 60)
        end_m, end_s = divmod(int(w.end_sec), 60)
        lines.append(f"[Window {w.window_id}] {start_m:02d}:{start_s:02d} -> {end_m:02d}:{end_s:02d}")
        lines.append(w.text[:600])
        lines.append("")
    windows_text = "\n".join(lines)

    user_prompt = SCANNER_USER.format(duration_min=duration_min, windows_text=windows_text)
    raw = llm.complete(SCANNER_SYSTEM, user_prompt, response_format="json", temperature=0.2, max_tokens=2048)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Scanner batch {batch_num} JSON parse failed. Raw:\n{raw[:500]}")
        raise

    return [ScoredWindow(**item) for item in data.get("windows", [])]
