from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from schemas import PipelineState, ClipperTask, BlogTask, CaptionTask
from nodes.ingest import ingest_node
from nodes.transcript_node import transcript_node
from nodes.scanner_node import scanner_node
from nodes.refiner_node import refiner_node
from nodes.clipper import render_one_clip
from nodes.blog_writer import write_blog
from nodes.caption_writer import write_caption
from nodes.aggregator import aggregator_node
from nodes.transcript import extract_text_for_range


def fan_out(state: PipelineState) -> list:
    """Fan out after refiner: parallel clip render + blog + captions."""
    sends = []

    for clip in state.selected_clips:
        sends.append(Send("render_clip", ClipperTask(
            job_id=state.job_id,
            clip=clip,
            video_path=state.video_path,
            vtt_path=state.vtt_path,
        )))

    full_transcript = "\n\n".join(w.text for w in state.windows)
    sends.append(Send("write_blog", BlogTask(
        job_id=state.job_id,
        video_title=state.video_title or "Untitled",
        duration_min=(state.duration_sec or 0) / 60,
        transcript_text=full_transcript,
    )))

    for clip in state.selected_clips:
        clip_text = extract_text_for_range(state.windows, clip.start_sec, clip.end_sec)
        sends.append(Send("write_caption", CaptionTask(
            clip=clip,
            clip_transcript=clip_text,
            job_id=state.job_id,
        )))

    return sends


def build_graph():
    g = StateGraph(PipelineState)

    g.add_node("ingest", ingest_node)
    g.add_node("transcript", transcript_node)
    g.add_node("scanner", scanner_node)
    g.add_node("refiner", refiner_node)
    g.add_node("render_clip", render_one_clip)
    g.add_node("write_blog", write_blog)
    g.add_node("write_caption", write_caption)
    g.add_node("aggregator", aggregator_node)

    g.add_edge(START, "ingest")
    g.add_edge("ingest", "transcript")
    g.add_edge("transcript", "scanner")
    g.add_edge("scanner", "refiner")
    g.add_conditional_edges("refiner", fan_out, ["render_clip", "write_blog", "write_caption"])
    g.add_edge("render_clip", "aggregator")
    g.add_edge("write_blog", "aggregator")
    g.add_edge("write_caption", "aggregator")
    g.add_edge("aggregator", END)

    return g.compile()
