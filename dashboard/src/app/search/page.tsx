"use client";

import { useState } from "react";
import Link from "next/link";
import { api, Topic, RawItem } from "@/lib/api";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [topics, setTopics] = useState<Topic[]>([]);
  const [items, setItems] = useState<RawItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async () => {
    if (query.trim().length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const [t, i] = await Promise.all([
        api.search.topics(query),
        api.search.items(query),
      ]);
      setTopics(t);
      setItems(i);
      setSearched(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Search</h1>
        <p className="text-sm text-muted mt-1">Search topics and collected items</p>
      </div>

      {/* Search bar */}
      <div className="flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="Search topics, articles, papers…"
          className="flex-1 bg-surface-card border border-surface-border rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
        />
        <button
          onClick={search}
          disabled={loading || query.trim().length < 2}
          className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "…" : "Search"}
        </button>
      </div>

      {error && <div className="card text-danger text-sm">{error}</div>}

      {searched && !loading && (
        <div className="space-y-6">
          {/* Topics */}
          {topics.length > 0 && (
            <section>
              <h2 className="text-xs font-medium text-muted uppercase tracking-wider mb-3">
                Topics ({topics.length})
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {topics.map((t) => (
                  <Link
                    key={t.id}
                    href={`/trends/${t.slug}`}
                    className="card p-3 hover:bg-surface-hover transition-colors"
                  >
                    <p className="text-sm text-slate-200 font-medium">{t.name}</p>
                    {t.category && <p className="text-xs text-muted mt-0.5">{t.category}</p>}
                    {t.aliases && t.aliases.length > 0 && (
                      <p className="text-xs text-muted mt-1 truncate">
                        aka: {t.aliases.slice(0, 3).join(", ")}
                      </p>
                    )}
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* Items */}
          {items.length > 0 && (
            <section>
              <h2 className="text-xs font-medium text-muted uppercase tracking-wider mb-3">
                Collected Items ({items.length})
              </h2>
              <div className="space-y-2">
                {items.map((item) => (
                  <div key={item.id} className="card py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        {item.url ? (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-slate-200 hover:text-white hover:underline truncate block"
                          >
                            {item.title || item.url}
                          </a>
                        ) : (
                          <p className="text-sm text-slate-200 truncate">{item.title || "Untitled"}</p>
                        )}
                        <div className="flex items-center gap-2 mt-1">
                          <span className="px-1.5 py-0.5 rounded text-xs bg-surface-hover text-muted">
                            {item.source}
                          </span>
                          {item.author && (
                            <span className="text-xs text-muted truncate">{item.author}</span>
                          )}
                          {item.published_at && (
                            <span className="text-xs text-muted">
                              {new Date(item.published_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>
                      {item.importance_score != null && (
                        <span className="text-xs font-mono text-muted shrink-0">
                          {item.importance_score.toFixed(2)}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {topics.length === 0 && items.length === 0 && (
            <div className="card text-muted text-sm text-center py-8">
              No results for "{query}"
            </div>
          )}
        </div>
      )}
    </div>
  );
}
