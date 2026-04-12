import { api, Pattern } from "@/lib/api";

const TYPE_LABELS: Record<string, { label: string; color: string }> = {
  emerging: { label: "Emerging", color: "text-success bg-success/10" },
  hype_peak: { label: "Hype Peak", color: "text-warning bg-warning/10" },
  hype_recovery: { label: "Recovery", color: "text-accent bg-accent/10" },
  cross_source_correlation: { label: "Correlated", color: "text-purple-400 bg-purple-400/10" },
  topic_cluster: { label: "Cluster", color: "text-cyan-400 bg-cyan-400/10" },
  content_gap: { label: "Content Gap", color: "text-orange-400 bg-orange-400/10" },
};

function PatternTypeBadge({ type }: { type: string }) {
  const meta = TYPE_LABELS[type] ?? { label: type, color: "text-slate-400 bg-slate-700" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${meta.color}`}>
      {meta.label}
    </span>
  );
}

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1 bg-surface-border rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-accent"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-muted">{pct}%</span>
    </div>
  );
}

async function getData() {
  try {
    return await api.patterns.list(undefined, 50);
  } catch {
    return [];
  }
}

export default async function PatternsPage() {
  const patterns = await getData();

  // Group by type
  const grouped: Record<string, Pattern[]> = {};
  for (const p of patterns) {
    if (!grouped[p.pattern_type]) grouped[p.pattern_type] = [];
    grouped[p.pattern_type].push(p);
  }

  const typeOrder = [
    "emerging", "hype_peak", "hype_recovery",
    "cross_source_correlation", "topic_cluster", "content_gap"
  ];
  const sortedTypes = [
    ...typeOrder.filter((t) => grouped[t]),
    ...Object.keys(grouped).filter((t) => !typeOrder.includes(t)),
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Patterns</h1>
        <p className="text-sm text-muted mt-1">{patterns.length} patterns detected</p>
      </div>

      {patterns.length === 0 && (
        <div className="card text-muted text-sm">
          No patterns detected yet. Run the analyzer.
        </div>
      )}

      {sortedTypes.map((type) => (
        <section key={type}>
          <div className="flex items-center gap-3 mb-3">
            <PatternTypeBadge type={type} />
            <span className="text-xs text-muted">{grouped[type].length} pattern{grouped[type].length !== 1 ? "s" : ""}</span>
          </div>
          <div className="space-y-3">
            {grouped[type].map((p) => (
              <PatternCard key={p.id} pattern={p} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function PatternCard({ pattern: p }: { pattern: Pattern }) {
  const evidence = p.evidence ?? {};
  const detectedAt = new Date(p.detected_at).toLocaleDateString();

  return (
    <div className="card">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-slate-200">{p.title}</p>
          {p.description && (
            <p className="text-xs text-muted mt-1 leading-relaxed">{p.description}</p>
          )}
        </div>
        <div className="shrink-0 text-right space-y-1">
          <ConfidenceBar score={p.confidence_score} />
          <p className="text-xs text-muted">{detectedAt}</p>
        </div>
      </div>

      {/* Evidence summary */}
      {Object.keys(evidence).length > 0 && (
        <div className="mt-3 pt-3 border-t border-surface-border flex flex-wrap gap-3">
          {Object.entries(evidence)
            .filter(([, v]) => typeof v === "number" || typeof v === "string")
            .slice(0, 5)
            .map(([k, v]) => (
              <div key={k} className="text-xs">
                <span className="text-muted">{k.replace(/_/g, " ")}: </span>
                <span className="text-slate-300 font-mono">
                  {typeof v === "number" ? (Number.isInteger(v) ? v : v.toFixed(2)) : String(v)}
                </span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
