"use client";

import { useEffect, useState, useCallback } from "react";
import { api, RawItem } from "@/lib/api";

const SOURCE_LABELS: Record<string, string> = {
  arxiv: "arXiv",
  github: "GitHub",
  google_trends: "Google Trends",
  hn: "Hacker News",
  huggingface: "HuggingFace",
  newsapi: "NewsAPI",
  reddit: "Reddit",
  rss: "RSS",
  stackoverflow: "Stack Overflow",
};

const SOURCE_COLORS: Record<string, string> = {
  arxiv: "text-blue-400 bg-blue-400/10",
  github: "text-slate-300 bg-slate-300/10",
  google_trends: "text-yellow-400 bg-yellow-400/10",
  hn: "text-orange-400 bg-orange-400/10",
  huggingface: "text-yellow-300 bg-yellow-300/10",
  newsapi: "text-purple-400 bg-purple-400/10",
  reddit: "text-orange-500 bg-orange-500/10",
  rss: "text-green-400 bg-green-400/10",
  stackoverflow: "text-orange-300 bg-orange-300/10",
};

const PAGE_SIZE = 50;

function ScoreBar({ score }: { score: number | null }) {
  if (score == null) return <span className="text-xs text-muted">—</span>;
  const pct = Math.round(score * 100);
  const color = score >= 0.65 ? "bg-success" : score >= 0.35 ? "bg-warning" : "bg-slate-600";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-surface-border rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-slate-400">{score.toFixed(2)}</span>
    </div>
  );
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return "< 1h ago";
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export default function SourcesPage() {
  const [sources, setSources] = useState<string[]>([]);
  const [active, setActive] = useState<string>("");
  const [items, setItems] = useState<RawItem[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);

  // Load source list
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/api/v1/sources`)
      .then((r) => r.json())
      .then((data: string[]) => {
        setSources(data);
        if (data.length > 0) setActive(data[0]);
      })
      .catch(() => {});
  }, []);

  // Load items when source or offset changes
  const loadItems = useCallback(async (source: string, off: number, append: boolean) => {
    if (!source) return;
    setLoading(true);
    try {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/api/v1/sources/${source}/items?limit=${PAGE_SIZE}&offset=${off}`;
      const data: RawItem[] = await fetch(url).then((r) => r.json());
      setItems((prev) => append ? [...prev, ...data] : data);
      setHasMore(data.length === PAGE_SIZE);
    } catch {
      if (!append) setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!active) return;
    setOffset(0);
    setItems([]);
    loadItems(active, 0, false);
  }, [active, loadItems]);

  const loadMore = () => {
    const next = offset + PAGE_SIZE;
    setOffset(next);
    loadItems(active, next, true);
  };

  const label = SOURCE_LABELS[active] ?? active;
  const colorCls = SOURCE_COLORS[active] ?? "text-slate-300 bg-slate-300/10";

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Sources</h1>
        <p className="text-sm text-muted mt-1">Browse collected items by source</p>
      </div>

      {/* Source tabs */}
      <div className="flex flex-wrap gap-2">
        {sources.map((s) => {
          const c = SOURCE_COLORS[s] ?? "text-slate-300 bg-slate-300/10";
          return (
            <button
              key={s}
              onClick={() => setActive(s)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                active === s
                  ? c + " ring-1 ring-inset ring-white/20"
                  : "text-muted bg-surface-hover hover:text-slate-300"
              }`}
            >
              {SOURCE_LABELS[s] ?? s}
            </button>
          );
        })}
      </div>

      {/* Item count header */}
      {active && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${colorCls}`}>{label}</span>
            <span className="text-sm text-muted">{items.length} items loaded</span>
          </div>
          {loading && <span className="text-xs text-muted animate-pulse">Loading…</span>}
        </div>
      )}

      {/* Items table */}
      {items.length > 0 && (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-border text-xs text-muted uppercase tracking-wider">
                <th className="text-left px-4 py-3 font-medium">Title</th>
                <th className="text-left px-4 py-3 font-medium hidden sm:table-cell">Author</th>
                <th className="text-left px-4 py-3 font-medium">Score</th>
                <th className="text-left px-4 py-3 font-medium hidden md:table-cell">Collected</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  className="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
                >
                  <td className="px-4 py-3 max-w-0">
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-slate-200 hover:text-white hover:underline line-clamp-2 block"
                      >
                        {item.title || item.url}
                      </a>
                    ) : (
                      <span className="text-slate-400 line-clamp-2">{item.title || "—"}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <span className="text-xs text-muted truncate block max-w-32">
                      {item.author || "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <ScoreBar score={item.importance_score} />
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell whitespace-nowrap">
                    <span className="text-xs text-muted">{timeAgo(item.collected_at)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {hasMore && (
            <div className="px-4 py-3 border-t border-surface-border">
              <button
                onClick={loadMore}
                disabled={loading}
                className="btn-ghost text-xs disabled:opacity-50"
              >
                {loading ? "Loading…" : "Load more"}
              </button>
            </div>
          )}
        </div>
      )}

      {!loading && active && items.length === 0 && (
        <div className="card text-sm text-muted">
          No items collected from {label} yet.
        </div>
      )}
    </div>
  );
}
