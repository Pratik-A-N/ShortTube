import { useEffect, useState } from 'react';

function inlineParse(text) {
  const segments = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return segments.map((seg, i) => {
    if (seg.startsWith('**') && seg.endsWith('**'))
      return <strong key={i} className="font-semibold text-neutral-100">{seg.slice(2, -2)}</strong>;
    if (seg.startsWith('*') && seg.endsWith('*'))
      return <em key={i} className="italic text-neutral-200">{seg.slice(1, -1)}</em>;
    return seg;
  });
}

function MarkdownBody({ text }) {
  if (!text) return null;

  const lines = text.split('\n');
  const elements = [];
  let key = 0;
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (/^# /.test(line)) {
      // h1 is shown in the header — skip in body
      i++;
      continue;
    }
    if (/^## /.test(line)) {
      elements.push(
        <h2 key={key++} className="text-base font-semibold text-emerald-400 mt-7 mb-2 pb-1 border-b border-neutral-800 first:mt-0">
          {inlineParse(line.slice(3))}
        </h2>
      );
      i++;
      continue;
    }
    if (/^### /.test(line)) {
      elements.push(
        <h3 key={key++} className="text-sm font-semibold text-neutral-200 mt-5 mb-1.5">
          {inlineParse(line.slice(4))}
        </h3>
      );
      i++;
      continue;
    }
    if (/^[-*] /.test(line)) {
      const items = [];
      while (i < lines.length && /^[-*] /.test(lines[i])) {
        items.push(lines[i].slice(2));
        i++;
      }
      elements.push(
        <ul key={key++} className="my-3 space-y-1.5">
          {items.map((item, j) => (
            <li key={j} className="flex gap-2 text-sm text-neutral-300 leading-relaxed">
              <span className="text-emerald-500 mt-px shrink-0">›</span>
              <span>{inlineParse(item)}</span>
            </li>
          ))}
        </ul>
      );
      continue;
    }
    if (line.trim() === '') {
      i++;
      continue;
    }
    elements.push(
      <p key={key++} className="text-sm text-neutral-300 leading-relaxed my-2">
        {inlineParse(line)}
      </p>
    );
    i++;
  }

  return <>{elements}</>;
}

export default function BlogCard({ url }) {
  const [content, setContent] = useState('');

  useEffect(() => {
    fetch(url).then((r) => r.text()).then(setContent).catch(() => {});
  }, [url]);

  const title = content.match(/^#\s+(.+)/m)?.[1] ?? 'Blog Post';
  const wordCount = content.trim().split(/\s+/).filter(Boolean).length;
  const readTime = Math.max(1, Math.round(wordCount / 200));

  return (
    <section>
      <div className="rounded-xl border border-neutral-700 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-br from-neutral-800 to-neutral-900 px-6 pt-5 pb-5 border-b border-neutral-700">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-3">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-emerald-500">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="none">
                    <rect x="1.5" y="1.5" width="11" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
                    <line x1="3.5" y1="4.5" x2="10.5" y2="4.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
                    <line x1="3.5" y1="6.5" x2="10.5" y2="6.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
                    <line x1="3.5" y1="8.5" x2="7.5" y2="8.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
                  </svg>
                  Blog Post
                </span>
                <span className="h-3 w-px bg-neutral-700" />
                <span className="text-xs text-neutral-500">
                  {readTime} min read · {wordCount.toLocaleString()} words
                </span>
              </div>
              <h2 className="text-xl font-bold text-neutral-100 leading-snug">{title}</h2>
            </div>
            <a
              href={url}
              download
              className="shrink-0 text-xs px-3 py-1.5 rounded-md border border-neutral-700 text-neutral-400 hover:border-neutral-500 hover:text-neutral-200 transition-all"
            >
              ↓ .md
            </a>
          </div>
        </div>

        {/* Body */}
        <div className="bg-neutral-900 px-6 py-6 max-h-[540px] overflow-y-auto">
          <MarkdownBody text={content} />
        </div>
      </div>
    </section>
  );
}
