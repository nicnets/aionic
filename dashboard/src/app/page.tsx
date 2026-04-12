import { api, SystemStats, TrendingTopic, ContentSuggestion } from "@/lib/api";
import Link from "next/link";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="card">
      <p className="text-xs text-muted uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-semibold text-slate-100">{value}</p>
      {sub && <p className="text-xs text-muted mt-1">{sub}</p>}
    </div>
  );
}

function ClassBadge({ c }: { c: string }) {
  if (c === "write_now") return <span className="badge-write-now">write now</span>;
  if (c === "monitor") return <span className="badge-monitor">monitor</span>;
  return <span className="badge-ignore">ignore</span>;
}

function ConfBadge({ c }: { c: string }) {
  if (c === "high") return <span className="badge-high">high</span>;
  if (c === "medium") return <span className="badge-medium">medium</span>;
  return <span className="badge-low">low</span>;
}

async function getOverviewData() {
  const [stats, trends, suggestions] = await Promise.allSettled([
    api.stats(),
    api.trends.current(8),
    api.suggestions.list(true, 5),
  ]);
  return {
    stats: stats.status === "fulfilled" ? stats.value : null,
    trends: trends.status === "fulfilled" ? trends.value : [],
    suggestions: suggestions.status === "fulfilled" ? suggestions.value : [],
  };
}

export default async function OverviewPage() {
  const { stats, trends, suggestions } = await getOverviewData();

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Overview</h1>
        <p className="text-sm text-muted mt-1">
          {stats?.last_collection_at
            ? `Last collection: ${new Date(stats.last_collection_at).toLocaleString()}`
            : "No data collected yet"}
        </p>
      </div>

      {/* Stats grid */}
      {stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Items Collected" value={stats.total_items.toLocaleString()} sub={`${stats.items_today} today`} />
          <StatCard label="Active Topics" value={stats.active_topics} sub={`${stats.total_topics} total`} />
          <StatCard label="Patterns Found" value={stats.patterns_detected} />
          <StatCard label="Open Suggestions" value={stats.suggestions_available} />
        </div>
      ) : (
        <div className="card text-muted text-sm">Backend offline — start with <code>docker compose up</code></div>
      )}

      {/* Sources active */}
      {stats && stats.sources_active.length > 0 && (
        <div className="card">
          <p className="text-xs text-muted uppercase tracking-wider mb-3">Active Sources</p>
          <div className="flex flex-wrap gap-2">
            {stats.sources_active.map((s) => (
              <span key={s} className="px-2 py-0.5 rounded bg-surface-hover text-xs text-slate-300">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Trending topics */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-medium text-slate-200">Top Trending Topics</p>
            <Link href="/trends" className="text-xs text-accent hover:underline">View all →</Link>
          </div>
          {trends.length === 0 ? (
            <p className="text-sm text-muted">No scored topics yet — run priority engine.</p>
          ) : (
            <div className="space-y-2">
              {trends.map((t) => (
                <Link
                  key={t.topic_id}
                  href={`/trends/${t.slug}`}
                  className="flex items-center justify-between p-2.5 rounded-lg hover:bg-surface-hover transition-colors group"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-slate-200 truncate group-hover:text-white">{t.name}</p>
                    <p className="text-xs text-muted">{t.source_count} sources · {t.consistency_days}d</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-3">
                    <span className="text-xs font-mono text-slate-400">{t.score.toFixed(2)}</span>
                    <ClassBadge c={t.classification} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Latest suggestions */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-medium text-slate-200">Content Suggestions</p>
            <Link href="/suggestions" className="text-xs text-accent hover:underline">View all →</Link>
          </div>
          {suggestions.length === 0 ? (
            <p className="text-sm text-muted">No suggestions yet — run the analyzer.</p>
          ) : (
            <div className="space-y-3">
              {suggestions.map((s) => (
                <div key={s.id} className="p-2.5 rounded-lg bg-surface-hover">
                  <p className="text-sm text-slate-200 leading-snug">{s.title}</p>
                  {s.rationale && (
                    <p className="text-xs text-muted mt-1 line-clamp-2">{s.rationale}</p>
                  )}
                  <div className="flex items-center gap-2 mt-2">
                    <ConfBadge c={s.confidence_level} />
                    <span className="text-xs text-muted">urgency {s.urgency_score.toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
