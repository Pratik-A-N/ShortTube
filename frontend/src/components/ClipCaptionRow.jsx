import { useState } from 'react';

const SIGNAL_LABELS = {
  heatmap_peak:      { text: 'Trending moment',     cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  chapter:           { text: 'Key chapter',         cls: 'bg-sky-500/10 text-sky-400 border-sky-500/20' },
  creator_highlight: { text: 'Creator-highlighted', cls: 'bg-violet-500/10 text-violet-400 border-violet-500/20' },
};

function SignalBadge({ tag }) {
  const cfg = SIGNAL_LABELS[tag];
  if (!cfg) return null;
  return (
    <span className={`inline-block text-[10px] font-medium px-2 py-0.5 rounded-full border ${cfg.cls}`}>
      {cfg.text}
    </span>
  );
}

function parseCaption(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  const isHashtagLine = l => /^(#\w+[\s,]*)+$/.test(l);
  const hashtags = lines.filter(isHashtagLine).flatMap(l => l.match(/#\w+/g) ?? []);
  const content = lines.filter(l => !isHashtagLine(l));
  const [rawHook = '', ...bodyLines] = content;
  const hook = rawHook.replace(/^\[Clip\s*\d+\]\s*/i, '');
  const body = bodyLines.join(' ');
  return { hook, body, hashtags };
}

export default function ClipCaptionRow({ clip, caption, fileUrl }) {
  const [copied, setCopied] = useState(false);
  const videoUrl = fileUrl(clip.url);

  const handleCopy = () => {
    navigator.clipboard.writeText(caption?.text ?? '');
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const hasTags = clip.signal_tags?.length > 0;
  const hasRationale = !!clip.rationale;
  const parsed = caption ? parseCaption(caption.text) : null;
  const charCount = caption?.text?.length ?? 0;

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 overflow-hidden flex flex-col sm:flex-row sm:h-[460px]">
      {/* Video column */}
      <div className="sm:w-1/2 shrink-0 flex flex-col">
        <div className="aspect-[9/16] sm:aspect-auto sm:flex-1 sm:min-h-0 bg-black">
          <video src={videoUrl} controls className="h-full w-full object-contain" />
        </div>
        <div className="px-4 py-3 border-t border-neutral-800 shrink-0">
          <p className="text-sm font-medium text-neutral-100 leading-snug mb-2">{clip.hook_title}</p>
          <a href={videoUrl} download className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">
            ↓ Download mp4
          </a>
        </div>
      </div>

      <div className="hidden sm:block w-px bg-neutral-800 shrink-0" />
      <div className="sm:hidden h-px bg-neutral-800" />

      {/* Right column */}
      <div className="sm:w-1/2 flex flex-col min-w-0 sm:overflow-y-auto">

        {/* AI Analysis */}
        {(hasTags || hasRationale) && (
          <div className="p-5 border-b border-neutral-800/60">
            <div className="flex items-center gap-2 mb-3">
              <div className="h-1.5 w-1.5 rounded-full bg-violet-500" />
              <span className="text-xs font-semibold uppercase tracking-wider text-neutral-500">AI Analysis</span>
            </div>
            {hasTags && (
              <div className="flex flex-wrap gap-1.5 mb-2.5">
                {clip.signal_tags.map(tag => <SignalBadge key={tag} tag={tag} />)}
              </div>
            )}
            {hasRationale && (
              <p className="text-sm text-neutral-400 leading-relaxed">{clip.rationale}</p>
            )}
          </div>
        )}

        {/* Social Caption */}
        <div className="flex-1 flex flex-col p-5 min-h-0">
          <div className="flex items-center justify-between mb-4 gap-3">
            <div className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              <span className="text-xs font-semibold uppercase tracking-wider text-neutral-500">Caption</span>
            </div>
            <div className="flex items-center gap-2.5 shrink-0">
              {caption && (
                <span className={`text-[11px] tabular-nums ${charCount > 200 ? 'text-amber-400' : 'text-neutral-600'}`}>
                  {charCount}/220
                </span>
              )}
              <button
                onClick={handleCopy}
                disabled={!caption}
                className="text-xs px-3 py-1.5 rounded-md bg-neutral-800 hover:bg-neutral-700 text-neutral-300 hover:text-neutral-100 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {copied ? '✓ Copied' : 'Copy'}
              </button>
            </div>
          </div>

          {parsed ? (
            <div className="space-y-3">
              {parsed.hook && (
                <p className="text-sm font-semibold text-neutral-100 leading-snug">{parsed.hook}</p>
              )}
              {parsed.body && (
                <p className="text-sm text-neutral-400 leading-relaxed">{parsed.body}</p>
              )}
              {parsed.hashtags.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {parsed.hashtags.map(tag => (
                    <span
                      key={tag}
                      className="text-[11px] text-emerald-400/80 bg-emerald-500/8 border border-emerald-500/15 px-2 py-0.5 rounded-full"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <div className="h-4 w-4/5 bg-neutral-800 animate-pulse rounded" />
              <div className="space-y-2">
                {[100, 92, 78].map((w, i) => (
                  <div key={i} className="h-3 bg-neutral-800 animate-pulse rounded" style={{ width: `${w}%` }} />
                ))}
              </div>
              <div className="flex gap-1.5 pt-1">
                {[60, 72, 55, 80].map((w, i) => (
                  <div key={i} className="h-5 bg-neutral-800 animate-pulse rounded-full" style={{ width: `${w}px` }} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
