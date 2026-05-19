"use client";

export default function DashboardError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="rounded-lg border border-red-900 bg-red-950/30 p-4 space-y-3">
      <h2 className="font-semibold text-red-300">Dashboard error</h2>
      <p className="text-sm text-red-200">{error.message}</p>
      <button onClick={reset} className="rounded bg-red-700 hover:bg-red-600 px-3 py-1 text-sm">
        Retry
      </button>
    </div>
  );
}

