from __future__ import annotations
from typing import List, Annotated
from operator import add
from pydantic import BaseModel


class TranscriptWindow(BaseModel):
    window_id: int
    start_sec: float
    end_sec: float
    text: str


class ScoredWindow(BaseModel):
    window_id: int
    hook: int
    standalone: int
    energy: int
    specificity: int
    completeness: int
    total: int
    one_line_reason: str


class SelectedClip(BaseModel):
    rank: int
    start_sec: float
    end_sec: float
    hook_title: str
    viral_score: int
    rationale: str
    signal_tags: List[str] = []


class RenderedClip(BaseModel):
    rank: int
    file_path: str
    hook_title: str
    duration_sec: float
    rationale: str = ""
    signal_tags: List[str] = []


class ClipperTask(BaseModel):
    job_id: str
    clip: SelectedClip
    video_path: str
    vtt_path: str


class CaptionTask(BaseModel):
    clip: SelectedClip
    clip_transcript: str
    job_id: str


class BlogTask(BaseModel):
    job_id: str
    video_title: str
    duration_min: float
    transcript_text: str


class PipelineState(BaseModel):
    youtube_url: str
    job_id: str = ""
    video_path: str | None = None
    vtt_path: str | None = None
    duration_sec: float | None = None
    video_title: str | None = None
    windows: List[TranscriptWindow] = []
    scored_windows: List[ScoredWindow] = []
    selected_clips: List[SelectedClip] = []
    rendered_clips: Annotated[List[RenderedClip], add] = []
    blog_post: str | None = None
    social_captions: Annotated[List[str], add] = []
    error: str | None = None
    # YouTube engagement signals — all optional, degrade gracefully to 0 boost
    heatmap: List[dict] = []
    chapters: List[dict] = []
    description_timestamps: List[dict] = []
