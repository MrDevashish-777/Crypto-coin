"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchJson } from "@/lib/api/fetcher";
import type { SignalRecord } from "@/lib/api/types";

const PAGE_SIZE = 15;

export default function SignalsPage() {
  const [rows, setRows] = useState<SignalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [asset, setAsset] = useState("");
  const [timeframe, setTimeframe] = useState("");
  const [status, setStatus] = useState("");
  const [minConfidence, setMinConfidence] = useState(0);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<SignalRecord | null>(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchJson<SignalRecord[]>("/api/admin/signals?limit=200");
        if (!mounted) return;
        setRows(data);
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load signals");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    const id = setInterval(load, 12000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (asset && !r.asset.toLowerCase().includes(asset.toLowerCase())) return false;
      if (timeframe && r.timeframe !== timeframe) return false;
      if (status && r.status !== status) return false;
      if ((r.confidence || 0) < minConfidence) return false;
      return true;
    });
  }, [rows, asset, timeframe, status, minConfidence]);

  const totalPages = Math.max(Math.ceil(filtered.length / PAGE_SIZE), 1);
  const pageRows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Signals Console</h1>
        <p className="text-sm text-slate-400">Filter, inspect and monitor lifecycle state.</p>
      </header>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-3 grid grid-cols-1 md:grid-cols-5 gap-2">
        <input
          placeholder="Asset (BTCUSDT)"
          value={asset}
          onChange={(e) => {
            setAsset(e.target.value);
            setPage(1);
          }}
          className="rounded bg-slate-950 border border-slate-700 px-2 py-2 text-sm"
        />
        <input
          placeholder="Timeframe (15m)"
          value={timeframe}
          onChange={(e) => {
            setTimeframe(e.target.value);
            setPage(1);
          }}
          className="rounded bg-slate-950 border border-slate-700 px-2 py-2 text-sm"
        />
        <input
          placeholder="Status (active)"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="rounded bg-slate-950 border border-slate-700 px-2 py-2 text-sm"
        />
        <input
          type="number"
          min={0}
          max={100}
          value={minConfidence}
          onChange={(e) => {
            setMinConfidence(Number(e.target.value) || 0);
            setPage(1);
          }}
          className="rounded bg-slate-950 border border-slate-700 px-2 py-2 text-sm"
        />
        <button
          onClick={() => {
            setAsset("");
            setTimeframe("");
            setStatus("");
            setMinConfidence(0);
            setPage(1);
          }}
          className="rounded border border-slate-700 px-2 py-2 text-sm hover:bg-slate-800"
        >
          Reset
        </button>
      </section>

      {error ? <p className="text-red-400 text-sm">{error}</p> : null}
      {loading ? <p className="text-sm text-slate-400">Loading signals...</p> : null}
      {!loading && filtered.length === 0 ? <p className="text-sm text-slate-400">No signals found.</p> : null}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-900 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-950 text-slate-400">
              <tr>
                <th className="text-left p-2">Asset</th>
                <th className="text-left p-2">Type</th>
                <th className="text-left p-2">TF</th>
                <th className="text-left p-2">Conf</th>
                <th className="text-left p-2">Status</th>
                <th className="text-left p-2">Created</th>
              </tr>
            </thead>
            <tbody>
              {pageRows.map((r) => (
                <tr
                  key={`${r._id || r.dedup_key || r.asset}-${r.created_at}`}
                  className="border-t border-slate-800 hover:bg-slate-800/40 cursor-pointer"
                  onClick={() => setSelected(r)}
                >
                  <td className="p-2">{r.asset}</td>
                  <td className={`p-2 ${r.signal_type === "BUY" ? "text-emerald-400" : "text-red-400"}`}>
                    {r.signal_type}
                  </td>
                  <td className="p-2">{r.timeframe}</td>
                  <td className="p-2">{r.confidence}</td>
                  <td className="p-2">{r.status}</td>
                  <td className="p-2">{new Date(r.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between p-2 border-t border-slate-800 text-xs">
            <span>
              Page {page}/{totalPages} | {filtered.length} rows
            </span>
            <div className="space-x-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                className="border border-slate-700 rounded px-2 py-1 disabled:opacity-50"
              >
                Prev
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                className="border border-slate-700 rounded px-2 py-1 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="font-medium mb-2">Signal Details</h2>
          {!selected ? <p className="text-sm text-slate-400">Select a signal row to inspect details.</p> : null}
          {selected ? (
            <div className="space-y-2 text-sm">
              <p>
                <span className="text-slate-400">Asset:</span> {selected.asset}
              </p>
              <p>
                <span className="text-slate-400">Entry Range:</span> {selected.entry_range.join(" - ")}
              </p>
              <p>
                <span className="text-slate-400">Stop Loss:</span> {selected.stop_loss}
              </p>
              <p>
                <span className="text-slate-400">TP:</span> {selected.take_profit.tp1}/{selected.take_profit.tp2}/
                {selected.take_profit.tp3}
              </p>
              <p>
                <span className="text-slate-400">R:R:</span> {selected.risk_reward_ratio}
              </p>
              <p>
                <span className="text-slate-400">Validity:</span> {selected.validity}
              </p>
              <p>
                <span className="text-slate-400">Reason:</span> {selected.reason}
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

