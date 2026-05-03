import { useState } from 'react';
import URLInput from './components/URLInput';
import ProgressTimeline from './components/ProgressTimeline';
import ClipCaptionRow from './components/ClipCaptionRow';
import BlogCard from './components/BlogCard';
import { ClipCaptionRowSkeleton, BlogSkeleton } from './components/Skeletons';
import { startProcessing, fileUrl } from './api';

export default function App() {
  const [status, setStatus] = useState('idle');
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

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="border-b border-neutral-800">
        <div className="mx-auto max-w-5xl px-6 py-6">
          <h1 className="text-2xl font-semibold tracking-tight">ShortTube</h1>
          <p className="text-sm text-neutral-400 mt-1">
            Paste a YouTube URL. Get 3 vertical clips, a blog post, and social captions.
          </p>
        </div>
      </header>

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
    </div>
  );
}
