import { useState, useEffect } from 'react';
import URLInput from './components/URLInput';
import ProgressTimeline from './components/ProgressTimeline';
import ClipCaptionRow from './components/ClipCaptionRow';
import BlogCard from './components/BlogCard';
import { ClipCaptionRowSkeleton, BlogSkeleton } from './components/Skeletons';
import { startProcessing, fileUrl } from './api';

const PROVIDERS = [
  { value: 'groq',      label: 'Groq' },
  { value: 'openai',    label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'mistral',   label: 'Mistral' },
  { value: 'together',  label: 'Together AI' },
];

function SettingsModal({ open, onClose, provider, onProvider, apiKey, onApiKey }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-neutral-950/80 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="relative w-full max-w-md rounded-2xl border border-neutral-700 bg-neutral-900 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800">
          <h2 className="font-semibold text-neutral-100">LLM Settings</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 transition-colors"
          >
            <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
              <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-5">
          {/* Provider */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-neutral-300">Provider</label>
            <div className="space-y-2">
              {PROVIDERS.map((p) => (
                <label
                  key={p.value}
                  className={`flex items-center justify-between rounded-lg border px-4 py-3 cursor-pointer transition-colors ${
                    provider === p.value
                      ? 'border-emerald-500 bg-emerald-500/10'
                      : 'border-neutral-700 bg-neutral-950 hover:border-neutral-600'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="radio"
                      name="provider"
                      value={p.value}
                      checked={provider === p.value}
                      onChange={() => onProvider(p.value)}
                      className="accent-emerald-500"
                    />
                    <span className="text-sm font-medium text-neutral-200">{p.label}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* API Key */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-neutral-300">
              API Key
              <span className="ml-2 text-xs font-normal text-neutral-500">(leave blank to use server key)</span>
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => onApiKey(e.target.value)}
              placeholder={`Paste your ${PROVIDERS.find(p => p.value === provider)?.label} key…`}
              className="w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2.5 text-sm placeholder:text-neutral-500 focus:border-emerald-500 focus:outline-none"
            />
          </div>

          {/* Security note */}
          <p className="text-xs text-neutral-500 leading-relaxed">
            Your key is sent over HTTPS, used only for this request, and never stored on the server.
          </p>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-neutral-800 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-lg bg-emerald-500 px-5 py-2 text-sm font-medium text-neutral-950 hover:bg-emerald-400 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true';

export default function App() {
  const [status, setStatus] = useState('idle');
  const [events, setEvents] = useState([]);
  const [clips, setClips] = useState([]);
  const [blogUrl, setBlogUrl] = useState(null);
  const [captions, setCaptions] = useState([]);
  const [zipUrl, setZipUrl] = useState(null);
  const [error, setError] = useState(null);

  const [showSettings, setShowSettings] = useState(false);
  const [userProvider, setUserProvider] = useState('groq');
  const [userApiKey, setUserApiKey] = useState('');

  const handleSubmit = (url) => {
    setStatus('processing');
    setEvents([]);
    setClips([]);
    setBlogUrl(null);
    setCaptions([]);
    setZipUrl(null);
    setError(null);

    startProcessing(url, {
      apiKey: userApiKey.trim() || null,
      provider: userProvider,
      onEvent: (ev) => {
        setEvents((prev) => [...prev, ev]);

        if (ev.type === 'artifact') {
          const d = ev.data;
          if (d?.type === 'clip') {
            setClips((prev) => [...prev.filter((c) => c.rank !== d.rank), d].sort((a, b) => a.rank - b.rank));
          } else if (d?.type === 'blog') {
            setBlogUrl(d.url);
          } else if (d?.type === 'caption') {
            setCaptions((prev) => [...prev.filter((c) => c.rank !== d.rank), d].sort((a, b) => a.rank - b.rank));
          } else if (d?.type === 'zip') {
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
        setError(err?.message || 'Connection lost');
      },
    });
  };

  const isActive = status === 'processing' || status === 'complete';
  const keyIsSet = userApiKey.trim().length > 0;

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="border-b border-neutral-800">
        <div className="mx-auto max-w-5xl px-6 py-6 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">ShortTube</h1>
            <p className="text-sm text-neutral-400 mt-1">
              Paste a YouTube URL. Get 3 vertical clips, a blog post, and social captions.
            </p>
          </div>

          {/* Settings gear button */}
          <button
            onClick={() => setShowSettings(true)}
            title="LLM Settings"
            className="relative mt-1 rounded-lg p-2 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 transition-colors"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 15a3 3 0 100-6 3 3 0 000 6z"
                stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
              />
              <path
                d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"
                stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
              />
            </svg>
            {/* Active indicator dot */}
            {keyIsSet && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-emerald-400" />
            )}
          </button>
        </div>
      </header>

      {DEMO_MODE && (
        <div className="border-b border-amber-500/20 bg-amber-500/5 px-6 py-2.5 text-center text-xs text-amber-400">
          Demo mode — the pipeline always runs on a fixed video regardless of the URL entered.
        </div>
      )}

      <main className="mx-auto max-w-5xl px-6 py-8 space-y-8">
        <URLInput onSubmit={handleSubmit} disabled={status === 'processing'} />

        {isActive && <ProgressTimeline events={events} />}

        {status === 'error' && (
          <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-red-300">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Paired clip + caption rows */}
        {isActive && (
          <section className="space-y-4">
            {[1, 2, 3].map((rank) => {
              const clip = clips.find((c) => c.rank === rank);
              const caption = captions.find((c) => c.rank === rank);
              return clip
                ? <ClipCaptionRow key={rank} clip={clip} caption={caption} fileUrl={fileUrl} />
                : <ClipCaptionRowSkeleton key={rank} />;
            })}
          </section>
        )}

        {/* Blog post */}
        {isActive && (blogUrl ? <BlogCard url={fileUrl(blogUrl)} /> : <BlogSkeleton />)}

        {/* Download all */}
        {zipUrl && status === 'complete' && (
          <div className="flex justify-center pb-4">
            <a
              href={fileUrl(zipUrl)}
              download
              className="inline-flex items-center gap-2.5 rounded-xl bg-emerald-500 px-8 py-3.5 font-semibold text-neutral-950 hover:bg-emerald-400 transition-colors shadow-lg shadow-emerald-500/20"
            >
              <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
                <path
                  d="M8 2v9M5 8l3 3 3-3M3 13h10"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              Download All (ZIP)
            </a>
          </div>
        )}
      </main>

      <SettingsModal
        open={showSettings}
        onClose={() => setShowSettings(false)}
        provider={userProvider}
        onProvider={setUserProvider}
        apiKey={userApiKey}
        onApiKey={setUserApiKey}
      />
    </div>
  );
}
