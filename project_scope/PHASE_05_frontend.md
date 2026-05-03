# Phase 5 — React Frontend

> **Goal:** Single-page React app that consumes the SSE stream and renders progress + downloadable artifacts.
>
> **Time budget:** 2 hours.
>
> **Why this phase exists:** The Loom demo *is* the submission. A founder watching a 60-second video judges the visual product, not your graph topology. The frontend has to look polished even though it's only one screen.

---

## Files to create

```
viral-chopper/
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── src/
    │   ├── main.jsx
    │   ├── App.jsx
    │   ├── api.js                       # SSE client
    │   ├── components/
    │   │   ├── URLInput.jsx
    │   │   ├── ProgressTimeline.jsx
    │   │   ├── ClipCard.jsx
    │   │   ├── BlogCard.jsx
    │   │   └── CaptionCard.jsx
    │   └── styles.css                   # Tailwind imports
    └── .gitignore
```

Reuse the Vite + Tailwind shell from your Code Review Agent if possible. If not, scaffold with `npm create vite@latest frontend -- --template react`.

---

## File 1: `frontend/package.json`

```json
{
  "name": "viral-chopper-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@microsoft/fetch-event-source": "^2.0.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.0.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

We use `@microsoft/fetch-event-source` instead of native `EventSource` because EventSource doesn't support custom headers and breaks on POST. Even though Phase 3 uses GET, fetch-event-source handles disconnects/reconnects more gracefully.

---

## File 2: `frontend/src/api.js`

```javascript
import { fetchEventSource } from '@microsoft/fetch-event-source';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export function startProcessing(youtubeUrl, handlers) {
  const ctrl = new AbortController();
  const url = `${API_BASE}/api/process?youtube_url=${encodeURIComponent(youtubeUrl)}`;

  fetchEventSource(url, {
    signal: ctrl.signal,
    onmessage(ev) {
      try {
        const data = JSON.parse(ev.data);
        handlers.onEvent(data);
      } catch (e) {
        console.error('Failed to parse SSE event:', ev.data);
      }
    },
    onerror(err) {
      handlers.onError(err);
      throw err; // stop reconnect attempts
    },
    openWhenHidden: true,
  });

  return () => ctrl.abort();
}

export function fileUrl(path) {
  // path is like "/files/<job_id>/<filename>"
  return `${API_BASE}${path}`;
}
```

---

## File 3: `frontend/src/App.jsx`

Top-level state machine. Three states: `idle`, `processing`, `complete | error`.

```jsx
import { useState } from 'react';
import URLInput from './components/URLInput';
import ProgressTimeline from './components/ProgressTimeline';
import ClipCard from './components/ClipCard';
import BlogCard from './components/BlogCard';
import CaptionCard from './components/CaptionCard';
import { startProcessing, fileUrl } from './api';

export default function App() {
  const [status, setStatus] = useState('idle'); // idle | processing | complete | error
  const [events, setEvents] = useState([]);
  const [clips, setClips] = useState([]);
  const [blogUrl, setBlogUrl] = useState(null);
  const [captions, setCaptions] = useState([]);
  const [zipUrl, setZipUrl] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = (url) => {
    setStatus('processing');
    setEvents([]);
    setClips([]);
    setBlogUrl(null);
    setCaptions([]);
    setZipUrl(null);
    setError(null);

    startProcessing(url, {
      onEvent: (ev) => {
        setEvents((prev) => [...prev, ev]);

        if (ev.type === 'artifact') {
          const d = ev.data;
          if (d.type === 'clip') {
            setClips((prev) => [...prev, d].sort((a, b) => a.rank - b.rank));
          } else if (d.type === 'blog') {
            setBlogUrl(d.url);
          } else if (d.type === 'caption') {
            setCaptions((prev) => [...prev, d].sort((a, b) => a.rank - b.rank));
          } else if (d.type === 'zip') {
            setZipUrl(d.url);
          }
        } else if (ev.type === 'done') {
          setStatus('complete');
        } else if (ev.type === 'error') {
          setStatus('error');
          setError(ev.message);
        }
      },
      onError: (err) => {
        setStatus('error');
        setError(err.message || 'Connection lost');
      },
    });
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="border-b border-neutral-800">
        <div className="mx-auto max-w-5xl px-6 py-6">
          <h1 className="text-2xl font-semibold tracking-tight">Viral Video Chopper</h1>
          <p className="text-sm text-neutral-400 mt-1">
            Paste a YouTube URL. Get 3 vertical clips, a blog post, and social captions.
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8 space-y-8">
        <URLInput onSubmit={handleSubmit} disabled={status === 'processing'} />

        {(status === 'processing' || status === 'complete') && (
          <ProgressTimeline events={events} />
        )}

        {status === 'error' && (
          <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-red-300">
            <strong>Error:</strong> {error}
          </div>
        )}

        {clips.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold mb-3">Clips</h2>
            <div className="grid gap-4 md:grid-cols-3">
              {clips.map((c) => <ClipCard key={c.rank} clip={c} fileUrl={fileUrl} />)}
            </div>
          </section>
        )}

        {blogUrl && <BlogCard url={fileUrl(blogUrl)} />}

        {captions.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold mb-3">Social Captions</h2>
            <div className="space-y-2">
              {captions.map((c) => <CaptionCard key={c.rank} caption={c} />)}
            </div>
          </section>
        )}

        {zipUrl && status === 'complete' && (
          <a
            href={fileUrl(zipUrl)}
            download
            className="inline-block rounded-lg bg-emerald-500 px-4 py-2 font-medium text-neutral-950 hover:bg-emerald-400"
          >
            Download all (zip)
          </a>
        )}
      </main>
    </div>
  );
}
```

---

## File 4: `frontend/src/components/URLInput.jsx`

```jsx
import { useState } from 'react';

export default function URLInput({ onSubmit, disabled }) {
  const [url, setUrl] = useState('');

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-5">
      <label className="block text-sm font-medium text-neutral-300 mb-2">
        YouTube URL
      </label>
      <div className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://youtube.com/watch?v=..."
          disabled={disabled}
          className="flex-1 rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm placeholder:text-neutral-500 focus:border-emerald-500 focus:outline-none disabled:opacity-50"
        />
        <button
          onClick={() => url && onSubmit(url)}
          disabled={disabled || !url}
          className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {disabled ? 'Processing…' : 'Generate'}
        </button>
      </div>
      <p className="text-xs text-neutral-500 mt-2">
        English videos with auto-captions, 5–25 minutes long.
      </p>
    </div>
  );
}
```

---

## File 5: `frontend/src/components/ProgressTimeline.jsx`

Show node events as they arrive. Group by node. Show running status ("Rendering clip 2…") with a pulsing dot until that node's `node_complete` event arrives.

```jsx
export default function ProgressTimeline({ events }) {
  // Build a map: node -> { status: 'running' | 'done', message: '...' }
  const nodes = new Map();
  for (const ev of events) {
    if (ev.type === 'node_start' && ev.node) {
      nodes.set(ev.node, { status: 'running', message: ev.message });
    } else if (ev.type === 'node_complete' && ev.node) {
      const existing = nodes.get(ev.node) || {};
      nodes.set(ev.node, { ...existing, status: 'done' });
    }
  }

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-5">
      <h2 className="text-sm font-medium text-neutral-300 mb-3">Pipeline</h2>
      <ul className="space-y-2 text-sm">
        {[...nodes.entries()].map(([node, info]) => (
          <li key={node} className="flex items-center gap-3">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                info.status === 'done'
                  ? 'bg-emerald-500'
                  : 'bg-amber-400 animate-pulse'
              }`}
            />
            <span className="font-mono text-xs text-neutral-400 w-32 shrink-0">{node}</span>
            <span className="text-neutral-300">{info.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

---

## File 6: `frontend/src/components/ClipCard.jsx`

```jsx
export default function ClipCard({ clip, fileUrl }) {
  const url = fileUrl(clip.url);
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 overflow-hidden">
      <div className="aspect-[9/16] bg-black">
        <video src={url} controls className="h-full w-full" />
      </div>
      <div className="p-3">
        <div className="text-xs text-neutral-500 mb-1">Clip {clip.rank}</div>
        <div className="text-sm font-medium text-neutral-100 mb-2">{clip.hook_title}</div>
        <a
          href={url}
          download
          className="text-xs text-emerald-400 hover:text-emerald-300"
        >
          Download mp4
        </a>
      </div>
    </div>
  );
}
```

---

## File 7: `frontend/src/components/BlogCard.jsx`

```jsx
import { useEffect, useState } from 'react';

export default function BlogCard({ url }) {
  const [content, setContent] = useState('');

  useEffect(() => {
    fetch(url).then(r => r.text()).then(setContent);
  }, [url]);

  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-lg font-semibold">Blog Post</h2>
        <a href={url} download className="text-xs text-emerald-400 hover:text-emerald-300">
          Download .md
        </a>
      </div>
      <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-5 max-h-96 overflow-y-auto">
        <pre className="whitespace-pre-wrap text-sm text-neutral-300 font-sans">{content}</pre>
      </div>
    </section>
  );
}
```

(For a 3-day demo, rendering markdown as plain pre-wrap is fine. Don't add a markdown renderer dependency unless you have spare time at end of Day 2.)

---

## File 8: `frontend/src/components/CaptionCard.jsx`

```jsx
import { useState } from 'react';

export default function CaptionCard({ caption }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(caption.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4 flex gap-3">
      <div className="flex-1">
        <pre className="whitespace-pre-wrap text-sm text-neutral-300 font-sans">{caption.text}</pre>
      </div>
      <button
        onClick={handleCopy}
        className="text-xs text-emerald-400 hover:text-emerald-300 self-start shrink-0"
      >
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  );
}
```

---

## File 9: Tailwind setup

`tailwind.config.js`:
```javascript
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: { extend: {} },
  plugins: [],
};
```

`postcss.config.js`:
```javascript
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

`src/styles.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

`src/main.jsx`:
```jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
```

---

## File 10: `frontend/.env`

```
VITE_API_BASE=http://localhost:8000
```

For production, this gets set to the deployed backend URL in Phase 6.

---

## Phase 5 done criteria

- [ ] `npm run dev` starts the frontend on port 5173
- [ ] Pasting the canonical demo URL triggers the backend, events stream live, status pulses
- [ ] Clips appear as they finish rendering (parallel — clip 2 may finish before clip 1)
- [ ] Blog post appears, can be downloaded as .md
- [ ] Captions appear with working "Copy" button
- [ ] "Download all (zip)" appears at the end and works
- [ ] On `error` event from backend, UI shows the error clearly and stops the spinner
- [ ] Layout looks intentional on desktop (1920×1080) — judgment call: would a founder spend 60s on this UI without wincing?

---

## What we're explicitly NOT doing in Phase 5

- No mobile responsive design — Loom demo is desktop. If you have time at end of Day 3, add basic responsive. Otherwise skip.
- No dark/light theme toggle — dark only.
- No animation libraries (framer-motion etc.) — pulse is enough.
- No video preview thumbnail before processing — too much work for marginal value.
- No "save my session" / no history — every load starts fresh.
- No accessibility audit beyond basic semantic HTML.

---

## Visual polish tips for the Loom

- Use one accent color (emerald-500). Don't introduce more.
- Keep typography to one font family (system font). No Google Fonts download.
- The aspect-[9/16] video container is the visual centerpiece — make sure it actually shows vertical video, not letterboxed horizontal.
- Test the full flow on the canonical demo video at least twice before recording. The Loom should feel inevitable, not lucky.
