import os
import zipfile
from pathlib import Path

from schemas import PipelineState


def build_zip(state: PipelineState) -> str:
    job_dir = Path(f"tmp/jobs/{state.job_id}")
    zip_path = str(job_dir / "bundle.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for clip in state.rendered_clips:
            p = Path(clip.file_path)
            if p.exists():
                zf.write(p, f"clip_{clip.rank}_{clip.hook_title[:30].replace(' ', '_')}.mp4")

        blog_path = job_dir / "blog.md"
        if blog_path.exists():
            zf.write(blog_path, "blog_post.md")

        captions_path = job_dir / "captions.txt"
        if state.social_captions:
            captions_path.write_text("\n\n---\n\n".join(state.social_captions), encoding="utf-8")
            zf.write(captions_path, "social_captions.txt")

    return zip_path
