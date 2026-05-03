import hashlib
import json
import threading
from pathlib import Path
from typing import Optional

_MANIFEST = Path("cache/manifest.json")
_LOCK = threading.Lock()


def _load() -> dict:
    try:
        return json.loads(_MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    _MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _url_key(url: str) -> str:
    return hashlib.sha256(url.strip().encode()).hexdigest()[:20]


def get_cached(url: str) -> Optional[dict]:
    """Return cached entry if URL was processed before and all artifact files still exist."""
    with _LOCK:
        data = _load()

    entry = data.get(_url_key(url))
    if not entry:
        return None

    job_id = entry["job_id"]
    for artifact in entry["artifacts"]:
        artifact_url = artifact.get("url")
        if artifact_url:
            filename = artifact_url.rsplit("/", 1)[-1]
            if not Path(f"tmp/jobs/{job_id}/{filename}").exists():
                return None

    return entry


def save_result(url: str, job_id: str, artifacts: list) -> None:
    """Persist a completed job so the same URL is served from cache next time."""
    with _LOCK:
        data = _load()
        data[_url_key(url)] = {"job_id": job_id, "artifacts": artifacts, "url": url}
        _save(data)
