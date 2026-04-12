"use client";

import { useEffect, useState } from "react";
import { api, ContentSuggestion } from "@/lib/api";

function ConfBadge({ c }: { c: string }) {
  if (c === "high") return <span className="badge-high">high</span>;
  if (c === "medium") return <span className="badge-medium">medium</span>;
  return <span className="badge-low">low</span>;
}

function UrgencyBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.65 ? "bg-success" : score >= 0.35 ? "bg-warning" : "bg-slate-600";
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-surface-border rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-muted">{score.toFixed(2)}</span>
    </div>
  );
}

export default function SuggestionsPage() {
  const [suggestions, setSuggestions] = useState<ContentSuggestion[]>([]);
  const [showUsed, setShowUsed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async (unused: boolean) => {
    setLoading(true);
    try {
      const data = await api.suggestions.list(!unused, 50);
      setSuggestions(data);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(showUsed); }, [showUsed]);

  const markUsed = async (id: number) => {
    try {
      await api.suggestions.markUsed(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
    } catch {
      // ignore
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Content Suggestions</h1>
          <p className="text-sm text-muted mt-1">{suggestions.length} suggestions</p>
        </div>
        <button
          onClick={() => setShowUsed((v) => !v)}
          className="btn-ghost text-xs"
        >
          {showUsed ? "Show unused only" : "Show all"}
        </button>
      </div>

      {error && <div className="card text-danger text-sm">{error}</div>}

      {!loading && suggestions.length === 0 && (
        <div className="card text-muted text-sm">
          No suggestions found. Run the suggestion generator.
        </div>
      )}

      <div className="space-y-4">
        {suggestions.map((s) => (
          <SuggestionCard key={s.id} suggestion={s} onMarkUsed={markUsed} />
        ))}
      </div>
    </div>
  );
}

function SuggestionCard({
  suggestion: s,
  onMarkUsed,
}: {
  suggestion: ContentSuggestion;
  onMarkUsed: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`card transition-opacity ${s.used ? "opacity-50" : ""}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-200 leading-snug">{s.title}</p>
          {s.rationale && (
            <p className="text-xs text-muted mt-1.5 leading-relaxed">{s.rationale}</p>
          )}
        </div>
        <div className="shrink-0 space-y-1.5 text-right">
          <ConfBadge c={s.confidence_level} />
          <UrgencyBar score={s.urgency_score} />
        </div>
      </div>

      {/* Insight */}
      {s.insight && (
        <div className="mt-3 pt-3 border-t border-surface-border">
          <p className="text-xs text-accent font-medium mb-1">Insight</p>
          <p className="text-xs text-slate-300 leading-relaxed">{s.insight}</p>
        </div>
      )}

      {/* Suggested article titles */}
      {s.suggested_articles && s.suggested_articles.length > 1 && (
        <div className="mt-3 pt-3 border-t border-surface-border">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-muted hover:text-slate-300 transition-colors"
          >
            {expanded ? "▾" : "▸"} {s.suggested_articles.length - 1} more title{s.suggested_articles.length - 1 !== 1 ? "s" : ""}
          </button>
          {expanded && (
            <ul className="mt-2 space-y-1">
              {s.suggested_articles.slice(1).map((t, i) => (
                <li key={i} className="text-xs text-slate-400 pl-3 border-l border-surface-border">
                  {t}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="mt-3 pt-3 border-t border-surface-border flex items-center justify-between">
        <span className="text-xs text-muted">
          {new Date(s.created_at).toLocaleDateString()}
        </span>
        {!s.used && (
          <button
            onClick={() => onMarkUsed(s.id)}
            className="btn-primary text-xs py-1 px-2.5"
          >
            Mark as used
          </button>
        )}
      </div>
    </div>
  );
}
