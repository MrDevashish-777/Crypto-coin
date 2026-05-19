"use client";

import { useState } from "react";
import { fetchJson } from "@/lib/api/fetcher";
import type { GenerateRequest } from "@/lib/api/types";

const symbols = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOGE", "LINK"];
const timeframes = ["5m", "15m", "1h", "4h", "1d"];

export default function GenerationPage() {
  const [form, setForm] = useState<GenerateRequest>({ symbol: "BTC", timeframe: "15m", strategy: "planitt" });
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  async function runGeneration() {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const data = await fetchJson<unknown>("/api/admin/generate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(form),
      });
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Generation Controls</h1>
        <p className="text-sm text-slate-400">Run manual generation with guardrails and inspect immediate response.</p>
      </header>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4 space-y-4 max-w-xl">
        <div className="space-y-1">
          <label className="text-xs text-slate-400">Symbol</label>
          <select
            value={form.symbol}
            onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value }))}
            className="w-full rounded bg-slate-950 border border-slate-700 px-3 py-2"
          >
            {symbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-slate-400">Timeframe</label>
          <select
            value={form.timeframe}
            onChange={(e) => setForm((f) => ({ ...f, timeframe: e.target.value }))}
            className="w-full rounded bg-slate-950 border border-slate-700 px-3 py-2"
          >
            {timeframes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-slate-400">Strategy Hint</label>
          <input
            value={form.strategy}
            onChange={(e) => setForm((f) => ({ ...f, strategy: e.target.value }))}
            className="w-full rounded bg-slate-950 border border-slate-700 px-3 py-2"
          />
        </div>
        <button
          disabled={running}
          onClick={runGeneration}
          className="rounded bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 px-4 py-2"
        >
          {running ? "Running..." : "Run Generation"}
        </button>
        <div className="text-xs text-slate-400">
          Server-side proxy injects FastAPI internal key. Browser never receives internal credentials.
        </div>
      </section>

      {error ? <p className="text-red-400 text-sm">{error}</p> : null}
      {result ? (
        <pre className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-xs overflow-auto">
          {JSON.stringify(result, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}

