import { fetchEventSource } from '@microsoft/fetch-event-source';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export function startProcessing(youtubeUrl, handlers) {
  const ctrl = new AbortController();
  const url = `${API_BASE}/api/process?youtube_url=${encodeURIComponent(youtubeUrl)}`;

  fetchEventSource(url, {
    signal: ctrl.signal,
    onmessage(ev) {
      if (!ev.data) return;
      try {
        const data = JSON.parse(ev.data);
        handlers.onEvent(data);
      } catch (e) {
        console.error('Failed to parse SSE event:', ev.data);
      }
    },
    onerror(err) {
      handlers.onError(err);
      throw err;
    },
    openWhenHidden: true,
  });

  return () => ctrl.abort();
}

export function fileUrl(path) {
  return `${API_BASE}${path}`;
}
