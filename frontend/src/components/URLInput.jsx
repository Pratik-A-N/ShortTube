import { useState } from 'react';

const DEMO_URL = 'https://www.youtube.com/watch?v=arj7oStGLkU';
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true';

export default function URLInput({ onSubmit, disabled }) {
  const [url, setUrl] = useState(DEMO_MODE ? DEMO_URL : '');

  const handleKey = (e) => {
    if (e.key === 'Enter' && url && !disabled) onSubmit(url);
  };

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-5">
      <label className="block text-sm font-medium text-neutral-300 mb-2">
        YouTube URL
        {DEMO_MODE && (
          <span className="ml-2 text-xs font-normal text-amber-400">Demo — fixed video</span>
        )}
      </label>
      <div className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => !DEMO_MODE && setUrl(e.target.value)}
          onKeyDown={handleKey}
          placeholder="https://youtube.com/watch?v=..."
          disabled={disabled || DEMO_MODE}
          className="flex-1 rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm placeholder:text-neutral-500 focus:border-emerald-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <button
          onClick={() => url && onSubmit(url)}
          disabled={disabled}
          className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {disabled ? 'Processing…' : 'Generate'}
        </button>
      </div>
      <p className="text-xs text-neutral-500 mt-2">
        {DEMO_MODE
          ? 'Demo mode: pipeline runs on "Inside the Mind of a Master Procrastinator" by Tim Urban.'
          : 'English videos with auto-captions, 5–25 minutes long.'}
      </p>
    </div>
  );
}
