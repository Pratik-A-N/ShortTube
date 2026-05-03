export default function ClipCard({ clip, fileUrl }) {
  const url = fileUrl(clip.url);
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 overflow-hidden">
      <div className="aspect-[9/16] bg-black">
        <video src={url} controls className="h-full w-full" />
      </div>
      <div className="p-3">
        <div className="text-xs text-neutral-500 mb-1">Clip {clip.rank}</div>
        <div className="text-sm font-medium text-neutral-100 mb-2 leading-snug">{clip.hook_title}</div>
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
