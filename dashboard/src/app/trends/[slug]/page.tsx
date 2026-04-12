"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api, TopicTimeSeries, TrendingTopic, TopicItem, TopicSourceBreakdown } from "@/lib/api";

const SOURCE_LABELS: Record<string, string> = {
  arxiv: "arXiv", github: "GitHub", google_trends: "Google Trends",
  hn: "Hacker News", huggingface: "HuggingFace", newsapi: "NewsAPI",
  reddit: "Reddit", rss: "RSS", stackoverflow: "Stack Overflow",
};

const SOURCE_COLORS: Record<string, string> = {
  arxiv: "bg-blue-400/15 text-blue-400",
  github: "bg-slate-400/15 text-slate-300",
  google_trends: "bg-yellow-400/15 text-yellow-400",
  hn: "bg-orange-400/15 text-orange-400",
  huggingface: "bg-yellow-300/15 text-yellow-300",
  newsapi: "bg-purple-400/15 text-purple-400",
  reddit: "bg-orange-500/15 text-orange-400",
  rss: "bg-green-400/15 text-green-400",
  stackoverflow: "bg-orange-300/15 text-orange-300",
};

function ClassBadge({ c }: { c: string }) {
  if (c === "write_now") return <span className="badge-write-now">write now</span>;
  if (c === "monitor") return <span className="badge-monitor">monitor</span>;
  return <span className="badge-ignore">ignore</span>;
}

function SourceBadge({ source }: { source: string }) {
  const cls = SOURCE_COLORS[source] ?? "bg-slate-600/20 text-slate-400";
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${cls}`}>
      {SOURCE_LABELS[source] ?? source}
    </span>
  );
}

function timeAgo(iso: string | null) {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return "< 1h ago";
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function TopicDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const [timeseries, setTimeseries] = useState<TopicTimeSeries | null>(null);
  const [topicScore, setTopicScore] = useState<TrendingTopic | null>(null);
  const [items, setItems] = useState<TopicItem[]>([]);
  const [sources, setSources] = useState<TopicSourceBreakdown[]>([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.trends.timeseries(slug, days),
      api.trends.current(100),
      api.trends.items(slug, days),
      api.trends.sources(slug, days),
    ])
      .then(([ts, all, its, srcs]) => {
        setTimeseries(ts);
        setTopicScore(all.find((t) => t.slug === slug) ?? null);
        setItems(its);
        setSources(srcs);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [slug, days]);

  if (loading) return <div className="p-6 text-muted text-sm">Loading…</div>;
  if (error || !timeseries) {
    return (
      <div className="p-6">
        <Link href="/trends" className="text-xs text-accent hover:underline">← Back to Trends</Link>
        <div className="card mt-4 text-danger text-sm">{error || "Topic not found"}</div>
      </div>
    );
  }

  const chartData = timeseries.data.map((d) => ({
    date: d.snapshot_date.slice(5),
    mentions: d.mention_count,
    weighted: Math.round(d.weighted_mention_count * 10) / 10,
  }));

  const maxMentions = Math.max(...sources.map((s) => s.mention_count), 1);
  const breakdown = topicScore?.score_breakdown;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <Link href="/trends" className="text-xs text-muted hover:text-slate-300">← Trends</Link>
        <div className="flex items-start justify-between mt-2">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">{timeseries.name}</h1>
            {topicScore && (
              <div className="flex items-center gap-3 mt-2">
                <ClassBadge c={topicScore.classification} />
                <span className="text-sm text-muted">
                  Score: <span className="text-slate-300 font-mono">{topicScore.score.toFixed(3)}</span>
                </span>
                <span className="text-sm text-muted">
                  {topicScore.source_count} sources · {topicScore.consistency_days} days
                </span>
              </div>
            )}
          </div>
          <div className="flex gap-1">
            {[14, 30, 60, 90].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  days === d ? "bg-accent text-white" : "text-slate-400 hover:text-slate-100 hover:bg-surface-hover"
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Source breakdown */}
      {sources.length > 0 && (
        <div className="card">
          <p className="text-xs text-muted uppercase tracking-wider mb-4">Which sources are driving this</p>
          <div className="space-y-2.5">
            {sources.map((s) => (
              <div key={s.source} className="flex items-center gap-3">
                <div className="w-28 shrink-0">
                  <SourceBadge source={s.source} />
                </div>
                <div className="flex-1 h-1.5 bg-surface-border rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent rounded-full"
                    style={{ width: `${(s.mention_count / maxMentions) * 100}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-slate-400 w-8 text-right">{s.mention_count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Chart */}
      <div className="card">
        <p className="text-xs text-muted uppercase tracking-wider mb-4">Mention trend</p>
        {chartData.length === 0 ? (
          <p className="text-sm text-muted text-center py-8">No snapshot data yet — run Analysis to populate</p>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3347" />
              <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#2a3347" }} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={false} width={32} />
              <Tooltip
                contentStyle={{ background: "#161b27", border: "1px solid #2a3347", borderRadius: 8 }}
                labelStyle={{ color: "#94a3b8", fontSize: 12 }}
                itemStyle={{ color: "#e2e8f0", fontSize: 12 }}
              />
              <Line type="monotone" dataKey="mentions" stroke="#3b82f6" strokeWidth={2} dot={false} name="Mentions" />
              <Line type="monotone" dataKey="weighted" stroke="#22c55e" strokeWidth={1.5} dot={false} strokeDasharray="4 2" name="Weighted" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Score breakdown */}
      {breakdown && (
        <div className="card">
          <p className="text-xs text-muted uppercase tracking-wider mb-4">Score breakdown</p>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
            {["velocity", "diversity", "weighted_mentions", "consistency", "momentum"].map((key) => {
              const val = (breakdown[key] as number) ?? 0;
              return (
                <div key={key} className="text-center">
                  <div className="relative w-12 h-12 mx-auto mb-2">
                    <svg viewBox="0 0 36 36" className="w-12 h-12 -rotate-90">
                      <circle cx="18" cy="18" r="15" fill="none" stroke="#2a3347" strokeWidth="3" />
                      <circle cx="18" cy="18" r="15" fill="none" stroke="#3b82f6" strokeWidth="3"
                        strokeDasharray={`${val * 94.2} 94.2`} strokeLinecap="round" />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-xs font-mono text-slate-300">
                      {(val * 100).toFixed(0)}
                    </span>
                  </div>
                  <p className="text-xs text-muted capitalize">{key.replace("_", " ")}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recent items */}
      {items.length > 0 && (
        <div className="card p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-surface-border">
            <p className="text-xs text-muted uppercase tracking-wider">
              What people are saying — {items.length} recent items
            </p>
          </div>
          <table className="w-full text-sm">
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                  <td className="px-4 py-3 w-28 shrink-0">
                    <SourceBadge source={item.source} />
                  </td>
                  <td className="px-4 py-3">
                    {item.url ? (
                      <a href={item.url} target="_blank" rel="noopener noreferrer"
                        className="text-slate-200 hover:text-white hover:underline line-clamp-2 block">
                        {item.title || item.url}
                      </a>
                    ) : (
                      <span className="text-slate-400 line-clamp-2">{item.title || "—"}</span>
                    )}
                    {item.author && (
                      <span className="text-xs text-muted mt-0.5 block">{item.author}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted whitespace-nowrap hidden sm:table-cell">
                    {timeAgo(item.published_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {items.length === 0 && !loading && (
        <div className="card text-sm text-muted">
          No items tagged with this topic yet — run Process Items then Analysis.
        </div>
      )}
    </div>
  );
}
