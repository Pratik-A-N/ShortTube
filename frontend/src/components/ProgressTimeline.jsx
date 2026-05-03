import React from 'react';

const LABELS = {
  ingest: 'Download',
  transcript: 'Transcript',
  scanner: 'Scanner',
  refiner: 'Refiner',
  render_clip: 'Render Clips',
  write_blog: 'Blog Post',
  write_caption: 'Captions',
  aggregator: 'Package',
};

const SEQUENTIAL = ['ingest', 'transcript', 'scanner', 'refiner'];
const PARALLEL = [
  { key: 'render_clip', total: 3 },
  { key: 'write_blog', total: 1 },
  { key: 'write_caption', total: 3 },
];

// Nodes that emit granular progress (0-100) during their run
const PROGRESS_NODES = new Set(['ingest', 'scanner']);

function deriveNodeState(events) {
  const state = {};
  for (const ev of events) {
    if (ev.type === 'node_start' && ev.node) {
      const s = state[ev.node] ?? { started: 0, done: 0, message: null, progress: null };
      state[ev.node] = {
        ...s,
        started: s.started + 1,
        message: ev.message ?? s.message,
        progress: ev.progress ?? s.progress,
      };
    } else if (ev.type === 'node_complete' && ev.node) {
      const s = state[ev.node] ?? { started: 0, done: 0, message: null, progress: null };
      state[ev.node] = { ...s, done: s.done + 1 };
    }
  }
  return state;
}

function nodeStatus(state, key, total = 1) {
  const s = state[key] ?? { started: 0, done: 0 };
  if (s.done >= total) return 'done';
  if (s.started > 0) return 'running';
  return 'pending';
}

function StatusIcon({ status }) {
  if (status === 'done') {
    return (
      <svg className="h-3.5 w-3.5 shrink-0 text-emerald-500" viewBox="0 0 14 14" fill="none">
        <circle cx="7" cy="7" r="6.25" stroke="currentColor" strokeWidth="1.25" />
        <path
          d="M4.5 7l1.9 1.9 3.1-3.4"
          stroke="currentColor"
          strokeWidth="1.25"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (status === 'running') {
    return <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse inline-block shrink-0" />;
  }
  return <span className="h-2 w-2 rounded-full bg-neutral-600 inline-block shrink-0" />;
}

function NodePill({ nodeKey, nodeState, total = 1 }) {
  const status = nodeStatus(nodeState, nodeKey, total);
  const s = nodeState[nodeKey] ?? {};
  const doneCount = s.done ?? 0;
  const progress = s.progress;
  const showProgress = PROGRESS_NODES.has(nodeKey) && status === 'running' && progress != null;

  const border = {
    pending: 'border-neutral-700',
    running: 'border-amber-400/50 shadow-[0_0_8px_0_rgba(251,191,36,0.1)]',
    done: 'border-emerald-500/40',
  }[status];

  const bg = {
    pending: 'bg-neutral-800/40',
    running: 'bg-amber-400/5',
    done: 'bg-emerald-500/5',
  }[status];

  return (
    <div className={`rounded-lg border ${border} ${bg} px-3 py-2 flex flex-col gap-1.5 min-w-0`}>
      <div className="flex items-center gap-2">
        <StatusIcon status={status} />
        <span className="text-xs font-medium text-neutral-300 whitespace-nowrap">
          {LABELS[nodeKey]}
          {total > 1 && (
            <span className="ml-1 text-neutral-500">{doneCount}/{total}</span>
          )}
        </span>
      </div>
      {showProgress && (
        <div className="h-0.5 w-full bg-neutral-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-amber-400 rounded-full transition-[width] duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}

export default function ProgressTimeline({ events }) {
  const nodeState = deriveNodeState(events);

  const parallelRunning = PARALLEL.some(({ key, total }) => nodeStatus(nodeState, key, total) === 'running');
  const parallelDone = PARALLEL.every(({ key, total }) => nodeStatus(nodeState, key, total) === 'done');
  const parallelBorder = parallelRunning
    ? 'border-amber-400/30'
    : parallelDone
    ? 'border-emerald-500/30'
    : 'border-neutral-700/40';

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-5">
      <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-4">Pipeline</p>

      {/* Sequential chain */}
      <div className="flex items-center gap-2 flex-wrap">
        {SEQUENTIAL.map((key, i) => (
          <React.Fragment key={key}>
            <NodePill nodeKey={key} nodeState={nodeState} />
            {i < SEQUENTIAL.length - 1 && (
              <span className="text-neutral-600 text-xs select-none">→</span>
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Connector line */}
      <div className="ml-5 my-1">
        <div className="w-px h-4 bg-neutral-700" />
      </div>

      {/* Parallel fan-out */}
      <div className={`rounded-lg border border-dashed ${parallelBorder} p-3`}>
        <div className="grid grid-cols-3 gap-2">
          {PARALLEL.map(({ key, total }) => (
            <NodePill key={key} nodeKey={key} nodeState={nodeState} total={total} />
          ))}
        </div>
      </div>

      {/* Connector line */}
      <div className="ml-5 my-1">
        <div className="w-px h-4 bg-neutral-700" />
      </div>

      {/* Final node */}
      <NodePill nodeKey="aggregator" nodeState={nodeState} />
    </div>
  );
}
