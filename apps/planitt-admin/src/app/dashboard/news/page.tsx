"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/api/fetcher";
import type { NewsItem } from "@/lib/api/types";

type NewsResponse = {
  success?: boolean;
  data?: NewsItem[];
  message?: string;
};

export default function NewsPage() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchJson<NewsResponse>("/api/admin/news?limit=30");
        if (!mounted) return;
        setItems(res.data || []);
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load news");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    const id = setInterval(load, 30000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Market Intelligence</h1>
        <p className="text-sm text-slate-400">Latest news and sentiment signals from the processor feed.</p>
      </header>

      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      {loading ? <p className="text-sm text-slate-400">Loading news...</p> : null}
      {!loading && items.length === 0 ? <p className="text-sm text-slate-400">No news available.</p> : null}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {items.map((n, idx) => (
          <article key={`${n.title}-${idx}`} className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="flex justify-between gap-2">
              <p className="text-xs text-slate-400">{n.source || "unknown source"}</p>
              <span className="text-xs text-indigo-300">{n.sentiment || "NEUTRAL"}</span>
            </div>
            <h3 className="font-medium mt-2">{n.title}</h3>
            <div className="text-xs text-slate-400 mt-3 flex justify-between">
              <span>{n.published_at ? new Date(n.published_at).toLocaleString() : "-"}</span>
              {n.link ? (
                <a href={n.link} target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline">
                  Open
                </a>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

