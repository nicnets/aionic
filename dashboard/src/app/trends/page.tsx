import { api, TrendingTopic } from "@/lib/api";
import Link from "next/link";

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

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.65 ? "bg-success" : score >= 0.35 ? "bg-warning" : "bg-slate-600";
  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-1.5 bg-surface-border rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-slate-400 w-8">{score.toFixed(2)}</span>
    </div>
  );
}

async function getData() {
  const [all, emerging] = await Promise.allSettled([
    api.trends.current(50),
    api.trends.emerging(10),
  ]);
  return {
    all: all.status === "fulfilled" ? all.value : [],
    emerging: emerging.status === "fulfilled" ? emerging.value : [],
  };
}

export default async function TrendsPage() {
  const { all, emerging } = await getData();

  const writeNow = all.filter((t) => t.classification === "write_now");
  const monitor = all.filter((t) => t.classification === "monitor");

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Trends</h1>
        <p className="text-sm text-muted mt-1">{all.length} topics scored</p>
      </div>

      {/* Emerging callout */}
      {emerging.length > 0 && (
        <div className="card border-success/30 bg-success/5">
          <p className="text-xs text-success uppercase tracking-wider mb-3">↑ Emerging Now</p>
          <div className="flex flex-wrap gap-2">
            {emerging.map((t) => (
              <Link
                key={t.topic_id}
                href={`/trends/${t.slug}`}
                className="px-2.5 py-1 rounded-lg bg-success/10 text-sm text-success hover:bg-success/20 transition-colors"
              >
                {t.name}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Write now */}
      {writeNow.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-3">
            Write Now ({writeNow.length})
          </h2>
          <TopicsTable topics={writeNow} />
        </section>
      )}

      {/* Monitor */}
      {monitor.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-3">
            Monitor ({monitor.length})
          </h2>
          <TopicsTable topics={monitor} />
        </section>
      )}

      {all.length === 0 && (
        <div className="card text-muted text-sm">
          No topics scored yet. Trigger the priority engine from Admin → Collect.
        </div>
      )}
    </div>
  );
}

function TopicsTable({ topics }: { topics: TrendingTopic[] }) {
  return (
    <div className="card p-0 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-surface-border text-xs text-muted uppercase tracking-wider">
            <th className="text-left px-4 py-3 font-medium">Topic</th>
            <th className="text-left px-4 py-3 font-medium hidden md:table-cell">Category</th>
            <th className="text-left px-4 py-3 font-medium">Score</th>
            <th className="text-left px-4 py-3 font-medium hidden sm:table-cell">Sources</th>
            <th className="text-left px-4 py-3 font-medium hidden md:table-cell">Consistency</th>
            <th className="text-left px-4 py-3 font-medium">Confidence</th>
          </tr>
        </thead>
        <tbody>
          {topics.map((t) => (
            <tr
              key={t.topic_id}
              className="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
            >
              <td className="px-4 py-3">
                <Link
                  href={`/trends/${t.slug}`}
                  className="font-medium text-slate-200 hover:text-white hover:underline"
                >
                  {t.name}
                </Link>
              </td>
              <td className="px-4 py-3 hidden md:table-cell">
                <span className="text-xs text-muted">{t.category || "—"}</span>
              </td>
              <td className="px-4 py-3">
                <ScoreBar score={t.score} />
              </td>
              <td className="px-4 py-3 hidden sm:table-cell">
                <span className="text-slate-400">{t.source_count}</span>
              </td>
              <td className="px-4 py-3 hidden md:table-cell">
                <span className="text-slate-400">{t.consistency_days}d</span>
              </td>
              <td className="px-4 py-3">
                <ConfBadge c={t.confidence_level} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
