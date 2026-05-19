"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/api/fetcher";
import type { PerformanceSummary, SignalRecord } from "@/lib/api/types";

type HealthPayload = {
  checked_at: string;
  services: Record<string, { ok: boolean; status: number }>;
};

export default function OverviewPage() {
  const [perf, setPerf] = useState<PerformanceSummary | null>(null);
  const [signals, setSignals] = useState<SignalRecord[]>([]);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setError(null);
      try {
        const [perfData, signalsData, healthData] = await Promise.all([
          fetchJson<PerformanceSummary>("/api/admin/performance"),
          fetchJson<SignalRecord[]>("/api/admin/signals?limit=50"),
          fetchJson<HealthPayload>("/api/admin/health"),
        ]);
        if (!mounted) return;
        setPerf(perfData);
        setSignals(signalsData);
        setHealth(healthData);
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Load failed");
      }
    }
    load();
    const id = setInterval(load, 15000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  const avgConfidence = signals.length
    ? Math.round(signals.reduce((acc, s) => acc + (s.confidence || 0), 0) / signals.length)
    : 0;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Overview</h1>
        <p className="text-sm text-slate-400">Real-time operations snapshot and service status.</p>
      </header>
      {error ? <div className="text-sm text-red-400">{error}</div> : null}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card title="Total Signals" value={String(perf?.total ?? 0)} />
        <Card title="Active Signals" value={String(perf?.active ?? 0)} />
        <Card title="Avg Confidence" value={`${avgConfidence}%`} />
        <Card title="Expired Signals" value={String(Math.max((perf?.total ?? 0) - (perf?.active ?? 0), 0))} />
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="font-medium mb-3">Service Health</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.entries(health?.services || {}).map(([name, status]) => (
            <div key={name} className="rounded border border-slate-800 p-3 flex justify-between">
              <span className="text-sm">{name}</span>
              <span className={`text-sm ${status.ok ? "text-emerald-400" : "text-red-400"}`}>
                {status.ok ? `UP (${status.status})` : `DOWN (${status.status})`}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{title}</p>
      <p className="text-2xl font-semibold mt-2">{value}</p>
    </div>
  );
}

