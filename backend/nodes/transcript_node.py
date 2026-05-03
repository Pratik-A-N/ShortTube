from schemas import PipelineState
from nodes.transcript import parse_vtt_to_windows
from utils.progress import emit, ProgressEvent
from utils.logger import get_logger
from config import WINDOW_SIZE_SEC, WINDOW_STRIDE_SEC

log = get_logger("nodes.transcript")


async def transcript_node(state: PipelineState) -> dict:
    log.info(f"[{state.job_id[:8]}] TRANSCRIPT start | vtt={state.vtt_path}")
    await emit(ProgressEvent(type="node_start", node="transcript", message="Parsing captions..."))

    windows = parse_vtt_to_windows(state.vtt_path, WINDOW_SIZE_SEC, WINDOW_STRIDE_SEC)

    if not windows:
        log.error(f"[{state.job_id[:8]}] TRANSCRIPT produced 0 windows — VTT may be empty")
        raise ValueError("No transcript windows produced from captions")

    log.info(f"[{state.job_id[:8]}] TRANSCRIPT done | windows={len(windows)} | window_size={WINDOW_SIZE_SEC}s | stride={WINDOW_STRIDE_SEC}s")

    await emit(ProgressEvent(
        type="node_complete",
        node="transcript",
        message=f"Created {len(windows)} transcript windows",
    ))

    return {"windows": windows}
