const pulse = 'bg-neutral-800 animate-pulse rounded';

export function ClipCaptionRowSkeleton() {
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 overflow-hidden flex flex-col sm:flex-row sm:h-[460px]">
      <div className="sm:w-1/2 shrink-0 flex flex-col">
        <div className="aspect-[9/16] sm:aspect-auto sm:flex-1 sm:min-h-0 bg-neutral-800 animate-pulse" />
        <div className="px-4 py-3 border-t border-neutral-800 space-y-2 shrink-0">
          <div className={`${pulse} h-3 w-1/4`} />
          <div className={`${pulse} h-4 w-3/4`} />
          <div className={`${pulse} h-3 w-1/5`} />
        </div>
      </div>
      <div className="hidden sm:block w-px bg-neutral-800 shrink-0" />
      <div className="sm:hidden h-px bg-neutral-800" />
      <div className="sm:w-1/2 p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className={`${pulse} h-3 w-28`} />
          <div className={`${pulse} h-7 w-16 rounded-md`} />
        </div>
        {[100, 92, 85, 75, 60, 88].map((w, i) => (
          <div key={i} className={`${pulse} h-3`} style={{ width: `${w}%` }} />
        ))}
      </div>
    </div>
  );
}

export function BlogSkeleton() {
  return (
    <section>
      <div className="rounded-xl border border-neutral-700 overflow-hidden">
        <div className="bg-gradient-to-br from-neutral-800 to-neutral-900 px-6 py-5 border-b border-neutral-700 space-y-3">
          <div className={`${pulse} h-3 w-32`} />
          <div className={`${pulse} h-6 w-2/3`} />
        </div>
        <div className="bg-neutral-900 px-6 py-6 space-y-3">
          {[95, 80, 88, 65, 92, 55, 78, 70, 84, 50].map((w, i) => (
            <div key={i} className={`${pulse} h-3`} style={{ width: `${w}%` }} />
          ))}
        </div>
      </div>
    </section>
  );
}
