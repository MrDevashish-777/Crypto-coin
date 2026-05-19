"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/api/fetcher";

type HealthPayload = {
  checked_at: string;
  services: Record<string, { ok: boolean; status: number }>;
};

export default function OpsPage() {
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [market, setMarket] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setError(null);
      try {
        const [h, m] = await Promise.all([
          fetchJson<HealthPayload>("/api/admin/health"),
          fetchJson<unknown>("/api/admin/market-status"),
        ]);
        if (!mounted) return;
        setHealth(h);
        setMarket(m);
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Unable to load ops data");
      }
    }
    load();
    const id = setInterval(load, 15000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Ops Observability</h1>
        <p className="text-sm text-slate-400">Health, retry visibility and timeline-friendly diagnostics.</p>
      </header>
      {error ? <p className="text-red-400 text-sm">{error}</p> : null}

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="font-medium mb-3">Service health</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {Object.entries(health?.services || {}).map(([name, status]) => (
            <div key={name} className="border border-slate-800 rounded p-3 flex justify-between">
              <span>{name}</span>
              <span className={status.ok ? "text-emerald-400" : "text-red-400"}>
                {status.ok ? "healthy" : "degraded"} ({status.status})
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="font-medium mb-3">Market status payload</h2>
        <pre className="text-xs overflow-auto">{JSON.stringify(market, null, 2)}</pre>
      </section>
    </div>
  );
}

