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
        <pre className="whitespace-pre-wrap text-sm text-neutral-300 font-sans leading-relaxed">{caption.text}</pre>
      </div>
      <button
        onClick={handleCopy}
        className="text-xs text-emerald-400 hover:text-emerald-300 self-start shrink-0 transition-colors"
      >
        {copied ? 'Copied!' : 'Copy'}
      </button>
    </div>
  );
}
