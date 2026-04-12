"use client";

import { useEffect, useRef, useState } from "react";
import { api, SourceWeight, AIProvider, UnresolvedTopic, Topic, SystemConfig, JobStatus, SystemLogEntry, RssFeed, RssFeedTestResult } from "@/lib/api";

type Tab = "collect" | "logs" | "config" | "weights" | "provider" | "topics" | "unresolved" | "performance" | "rss";

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("collect");

  const tabs: { key: Tab; label: string }[] = [
    { key: "collect", label: "Collect" },
    { key: "logs", label: "Logs" },
    { key: "config", label: "Config" },
    { key: "weights", label: "Source Weights" },
    { key: "provider", label: "AI Provider" },
    { key: "topics", label: "Topics" },
    { key: "unresolved", label: "Unresolved" },
    { key: "performance", label: "Performance" },
    { key: "rss", label: "RSS Feeds" },
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Admin</h1>
        <p className="text-sm text-muted mt-1">System configuration and controls</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-surface-border pb-0">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t.key
                ? "border-accent text-slate-100"
                : "border-transparent text-muted hover:text-slate-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "logs" && <LogsTab />}
      {tab === "config" && <ConfigTab />}
      {tab === "weights" && <WeightsTab />}
      {tab === "provider" && <ProviderTab />}
      {tab === "topics" && <TopicsTab />}
      {tab === "unresolved" && <UnresolvedTab />}
      {tab === "collect" && <CollectTab />}
      {tab === "performance" && <PerformanceTab />}
      {tab === "rss" && <RssFeedsTab />}
    </div>
  );
}

// ---- System Logs ----------------------------------------------------------

const LEVEL_COLORS: Record<string, string> = {
  DEBUG:    "text-slate-500",
  INFO:     "text-slate-300",
  WARNING:  "text-yellow-400",
  ERROR:    "text-red-400",
  CRITICAL: "text-red-500",
};

function LogsTab() {
  const [logs, setLogs] = useState<SystemLogEntry[]>([]);
  const [level, setLevel] = useState<string>("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const ref = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = async () => {
    try {
      const data = await api.admin.logs(level || undefined);
      setLogs(data);
      setTimeout(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, 50);
    } catch {}
  };

  useEffect(() => { fetch(); }, [level]);

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(fetch, 2000);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [autoRefresh, level]);

  const handleClear = async () => {
    await api.admin.clearLogs();
    setLogs([]);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={level}
          onChange={(e) => setLevel(e.target.value)}
          className="bg-surface border border-surface-border rounded px-3 py-1.5 text-sm text-slate-100 focus:outline-none focus:border-accent"
        >
          <option value="">All levels</option>
          <option value="DEBUG">DEBUG</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
          <option value="CRITICAL">CRITICAL</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-muted cursor-pointer">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
            className="accent-accent"
          />
          Auto-refresh (2s)
        </label>
        <button onClick={fetch} className="btn-ghost text-sm px-3 py-1.5">Refresh</button>
        <button onClick={handleClear} className="btn-danger text-sm px-3 py-1.5 ml-auto">Clear</button>
        <span className="text-xs text-muted">{logs.length} entries</span>
      </div>

      <div
        ref={ref}
        className="bg-[#0d1117] border border-surface-border rounded-lg p-3 h-[60vh] overflow-y-auto font-mono text-xs space-y-0.5"
      >
        {logs.length === 0 && (
          <p className="text-muted">No log entries. Start the pipeline to see activity here.</p>
        )}
        {logs.map((entry, i) => (
          <div key={i} className="flex gap-2 leading-5">
            <span className="text-slate-600 shrink-0 select-none">{entry.t}</span>
            <span className={`shrink-0 w-16 ${LEVEL_COLORS[entry.level] ?? "text-slate-400"}`}>
              {entry.level}
            </span>
            <span className="text-slate-500 shrink-0 truncate max-w-[160px]" title={entry.logger}>
              {entry.logger.replace("backend.", "")}
            </span>
            <span className={LEVEL_COLORS[entry.level] ?? "text-slate-300"}>{entry.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Config ---------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  llm: "LLM API Keys",
  collectors: "Collector API Keys",
  scheduling: "Collection Schedule",
  processing: "Processing",
};

const CATEGORY_ORDER = ["llm", "collectors", "scheduling", "processing"];

function ConfigTab() {
  const [items, setItems] = useState<SystemConfig[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [shown, setShown] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [msg, setMsg] = useState<Record<string, string>>({});

  useEffect(() => {
    api.admin.config().then(setItems).catch(() => {});
  }, []);

  const grouped = CATEGORY_ORDER.reduce<Record<string, SystemConfig[]>>((acc, cat) => {
    acc[cat] = items.filter((i) => i.category === cat);
    return acc;
  }, {});

  const save = async (key: string) => {
    const value = edits[key];
    if (value === undefined) return;
    setSaving(key);
    try {
      const updated = await api.admin.updateConfig(key, value);
      setItems((prev) => prev.map((i) => (i.key === key ? updated : i)));
      setEdits((prev) => { const n = { ...prev }; delete n[key]; return n; });
      setMsg((prev) => ({ ...prev, [key]: "Saved" }));
      setTimeout(() => setMsg((prev) => { const n = { ...prev }; delete n[key]; return n; }), 2000);
    } catch {
      setMsg((prev) => ({ ...prev, [key]: "Failed" }));
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="space-y-6">
      <p className="text-xs text-muted">
        Configure API keys and settings here instead of .env. Changes to API keys take effect immediately.
        Scheduling interval changes require an application restart.
      </p>

      {CATEGORY_ORDER.map((cat) => {
        const group = grouped[cat];
        if (!group || group.length === 0) return null;
        return (
          <div key={cat} className="space-y-2">
            <p className="text-xs font-semibold text-muted uppercase tracking-wider">
              {CATEGORY_LABELS[cat] ?? cat}
            </p>
            <div className="card p-0 overflow-hidden divide-y divide-surface-border">
              {group.map((item) => {
                const isEditing = edits[item.key] !== undefined;
                const inputType = item.is_secret && !shown[item.key] ? "password" : "text";
                const displayValue = isEditing ? edits[item.key] : item.value;

                return (
                  <div key={item.key} className="px-4 py-3 flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-mono text-slate-300">{item.key}</p>
                      {item.description && (
                        <p className="text-xs text-muted mt-0.5 truncate">{item.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <div className="relative">
                        <input
                          type={inputType}
                          value={displayValue}
                          onChange={(e) =>
                            setEdits((prev) => ({ ...prev, [item.key]: e.target.value }))
                          }
                          className="bg-surface border border-surface-border rounded px-2 py-1 text-xs font-mono text-slate-100 focus:outline-none focus:border-accent w-48"
                        />
                      </div>
                      {item.is_secret && (
                        <button
                          onClick={() => setShown((prev) => ({ ...prev, [item.key]: !prev[item.key] }))}
                          className="text-xs text-muted hover:text-slate-300 w-8 text-center"
                          title={shown[item.key] ? "Hide" : "Show"}
                        >
                          {shown[item.key] ? "🙈" : "👁"}
                        </button>
                      )}
                      {isEditing && (
                        <button
                          onClick={() => save(item.key)}
                          disabled={saving === item.key}
                          className="btn-primary text-xs py-1 px-2.5 disabled:opacity-50"
                        >
                          {saving === item.key ? "…" : "Save"}
                        </button>
                      )}
                      {msg[item.key] && (
                        <span className={`text-xs ${msg[item.key] === "Saved" ? "text-success" : "text-danger"}`}>
                          {msg[item.key]}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---- Source Weights -------------------------------------------------------

function WeightsTab() {
  const [weights, setWeights] = useState<SourceWeight[]>([]);
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    api.admin.weights().then(setWeights).catch(() => {});
  }, []);

  const save = async (source: string) => {
    const val = parseFloat(editing[source]);
    if (isNaN(val) || val < 0 || val > 2) return;
    setSaving(source);
    try {
      const updated = await api.admin.updateWeight(source, val);
      setWeights((prev) => prev.map((w) => (w.source === source ? updated : w)));
      setEditing((prev) => { const n = { ...prev }; delete n[source]; return n; });
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">Weights range 0.1–2.0. Applied to all scoring calculations.</p>
      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-border">
              <th className="text-left px-4 py-3 text-xs text-muted uppercase tracking-wider font-medium">Source</th>
              <th className="text-left px-4 py-3 text-xs text-muted uppercase tracking-wider font-medium">Weight</th>
              <th className="text-left px-4 py-3 text-xs text-muted uppercase tracking-wider font-medium">Updated</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {weights.map((w) => (
              <tr key={w.source} className="border-b border-surface-border last:border-0">
                <td className="px-4 py-3 font-mono text-slate-300">{w.source}</td>
                <td className="px-4 py-3">
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    max="2"
                    value={editing[w.source] ?? w.weight}
                    onChange={(e) => setEditing((prev) => ({ ...prev, [w.source]: e.target.value }))}
                    className="w-20 bg-surface border border-surface-border rounded px-2 py-1 text-sm font-mono text-slate-100 focus:outline-none focus:border-accent"
                  />
                </td>
                <td className="px-4 py-3 text-xs text-muted">
                  {new Date(w.updated_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3 text-right">
                  {editing[w.source] !== undefined && (
                    <button
                      onClick={() => save(w.source)}
                      disabled={saving === w.source}
                      className="btn-primary text-xs py-1 px-2.5 disabled:opacity-50"
                    >
                      {saving === w.source ? "…" : "Save"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---- AI Provider ----------------------------------------------------------

function ProviderTab() {
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [newProvider, setNewProvider] = useState("");
  const [newModel, setNewModel] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api.admin.providers().then(setProviders).catch(() => {});
  }, []);

  const activate = async () => {
    if (!newProvider || !newModel) return;
    setSaving(true);
    try {
      const updated = await api.admin.setActiveProvider(newProvider, newModel);
      setProviders((prev) =>
        prev.map((p) => ({ ...p, is_active: false })).map((p) =>
          p.id === updated.id ? updated : p
        )
      );
      if (!providers.find((p) => p.id === updated.id)) {
        setProviders((prev) => [...prev, updated]);
      }
      setMsg("Provider updated");
    } catch {
      setMsg("Failed to update provider");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-border">
              <th className="text-left px-4 py-3 text-xs text-muted uppercase tracking-wider font-medium">Provider</th>
              <th className="text-left px-4 py-3 text-xs text-muted uppercase tracking-wider font-medium">Model</th>
              <th className="text-left px-4 py-3 text-xs text-muted uppercase tracking-wider font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {providers.map((p) => (
              <tr key={p.id} className="border-b border-surface-border last:border-0">
                <td className="px-4 py-3 text-slate-300">{p.provider}</td>
                <td className="px-4 py-3 font-mono text-xs text-slate-400">{p.model_id}</td>
                <td className="px-4 py-3">
                  {p.is_active ? (
                    <span className="badge-write-now">active</span>
                  ) : (
                    <span className="badge-ignore">inactive</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card space-y-3">
        <p className="text-sm font-medium text-slate-200">Switch Active Provider</p>
        <div className="flex gap-2">
          <select
            value={newProvider}
            onChange={(e) => setNewProvider(e.target.value)}
            className="bg-surface border border-surface-border rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-accent"
          >
            <option value="">Provider…</option>
            <option value="claude">claude</option>
            <option value="openai">openai</option>
            <option value="openrouter">openrouter</option>
          </select>
          <input
            type="text"
            placeholder="model-id"
            value={newModel}
            onChange={(e) => setNewModel(e.target.value)}
            className="flex-1 bg-surface border border-surface-border rounded px-3 py-2 text-sm font-mono text-slate-100 focus:outline-none focus:border-accent"
          />
          <button onClick={activate} disabled={saving} className="btn-primary disabled:opacity-50">
            {saving ? "…" : "Activate"}
          </button>
        </div>
        {msg && <p className="text-xs text-muted">{msg}</p>}
      </div>
    </div>
  );
}

// ---- Topics ---------------------------------------------------------------

function TopicsTab() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api.admin.topics().then(setTopics).catch(() => {});
  }, []);

  const approve = async (id: number) => {
    await api.admin.approveTopic(id);
    setTopics((prev) => prev.map((t) => (t.id === id ? { ...t, is_approved: true } : t)));
  };

  const del = async (id: number) => {
    await api.admin.deleteTopic(id);
    setTopics((prev) => prev.filter((t) => t.id !== id));
  };

  const filtered = filter
    ? topics.filter((t) => t.name.toLowerCase().includes(filter.toLowerCase()))
    : topics;

  return (
    <div className="space-y-3">
      <input
        type="text"
        placeholder="Filter topics…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="w-full bg-surface-card border border-surface-border rounded-lg px-4 py-2 text-sm text-slate-100 placeholder:text-muted focus:outline-none focus:border-accent"
      />
      <div className="card p-0 overflow-hidden max-h-[500px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface-card">
            <tr className="border-b border-surface-border">
              <th className="text-left px-4 py-3 text-xs text-muted uppercase tracking-wider font-medium">Name</th>
              <th className="text-left px-4 py-3 text-xs text-muted uppercase tracking-wider font-medium">Category</th>
              <th className="text-left px-4 py-3 text-xs text-muted uppercase tracking-wider font-medium">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr key={t.id} className="border-b border-surface-border last:border-0 hover:bg-surface-hover">
                <td className="px-4 py-2.5">
                  <p className="text-sm text-slate-200">{t.name}</p>
                  {t.aliases && t.aliases.length > 0 && (
                    <p className="text-xs text-muted truncate max-w-xs">{t.aliases.join(", ")}</p>
                  )}
                </td>
                <td className="px-4 py-2.5 text-xs text-muted">{t.category || "—"}</td>
                <td className="px-4 py-2.5">
                  {t.is_approved ? (
                    <span className="badge-write-now">approved</span>
                  ) : (
                    <span className="badge-ignore">pending</span>
                  )}
                </td>
                <td className="px-4 py-2.5 text-right space-x-2">
                  {!t.is_approved && (
                    <button onClick={() => approve(t.id)} className="btn-ghost text-xs text-success">
                      Approve
                    </button>
                  )}
                  <button onClick={() => del(t.id)} className="btn-danger text-xs">
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---- Unresolved Topics ---------------------------------------------------

function UnresolvedTab() {
  const [items, setItems] = useState<UnresolvedTopic[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedCanonical, setSelectedCanonical] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.admin.unresolvedTopics(), api.admin.topics()])
      .then(([u, t]) => { setItems(u); setTopics(t); })
      .catch(() => {});
  }, []);

  const resolve = async (id: number) => {
    const canonicalId = parseInt(selectedCanonical[id] || "");
    if (!canonicalId) return;
    await api.admin.resolveUnresolved(id, canonicalId);
    setItems((prev) => prev.filter((i) => i.id !== id));
    setMsg("Resolved");
  };

  const promote = async (id: number) => {
    await api.admin.promoteUnresolved(id);
    setItems((prev) => prev.filter((i) => i.id !== id));
    setMsg("Promoted to new topic");
  };

  return (
    <div className="space-y-3">
      {msg && <p className="text-xs text-success">{msg}</p>}
      {items.length === 0 && (
        <div className="card text-muted text-sm">No unresolved topics in the review queue.</div>
      )}
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.id} className="card">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-mono text-slate-200">"{item.raw_text}"</p>
                <p className="text-xs text-muted mt-1">
                  {item.occurrence_count} occurrences · first seen {new Date(item.first_seen_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <select
                  value={selectedCanonical[item.id] || ""}
                  onChange={(e) =>
                    setSelectedCanonical((prev) => ({ ...prev, [item.id]: e.target.value }))
                  }
                  className="bg-surface border border-surface-border rounded px-2 py-1 text-xs text-slate-100 focus:outline-none focus:border-accent max-w-[160px]"
                >
                  <option value="">Map to topic…</option>
                  {topics.map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
                <button
                  onClick={() => resolve(item.id)}
                  disabled={!selectedCanonical[item.id]}
                  className="btn-primary text-xs py-1 disabled:opacity-40"
                >
                  Resolve
                </button>
                <button onClick={() => promote(item.id)} className="btn-ghost text-xs">
                  New
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Collect trigger ------------------------------------------------------

const SOURCES = [
  "rss", "hackernews", "arxiv", "github",
  "reddit", "huggingface", "newsapi",
  "google_trends", "stackoverflow",
];

const PIPELINE_STEPS: { key: "pipeline" | "analysis" | "suggestions"; label: string; description: string }[] = [
  {
    key: "pipeline",
    label: "1. Process Items",
    description: "Normalise, score importance, deduplicate, enrich with LLM, tag topics, and save processed items.",
  },
  {
    key: "analysis",
    label: "2. Run Analysis",
    description: "Score topics with the priority engine, backfill trend snapshots, and detect patterns.",
  },
  {
    key: "suggestions",
    label: "3. Generate Suggestions",
    description: "Use the LLM to generate editorial content ideas from the top-scored topics.",
  },
];

function StatusBadge({ status }: { status: JobStatus["status"] }) {
  const map: Record<JobStatus["status"], { label: string; cls: string }> = {
    idle:    { label: "idle",    cls: "text-muted border-surface-border" },
    running: { label: "running", cls: "text-accent border-accent animate-pulse" },
    done:    { label: "done",    cls: "text-success border-success" },
    error:   { label: "error",   cls: "text-danger border-danger" },
  };
  const { label, cls } = map[status];
  return (
    <span className={`text-xs font-mono border rounded px-1.5 py-0.5 ${cls}`}>{label}</span>
  );
}

function LogPanel({ logs, status }: { logs: JobStatus["logs"]; status: JobStatus["status"] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [logs]);

  if (status === "idle") return null;

  return (
    <div
      ref={ref}
      className="mt-3 bg-[#0d1117] border border-surface-border rounded-lg p-3 h-40 overflow-y-auto font-mono text-xs space-y-0.5"
    >
      {logs.length === 0 && (
        <p className="text-muted">Waiting for first log entry...</p>
      )}
      {logs.map((entry, i) => (
        <div key={i} className="flex gap-2">
          <span className="text-muted shrink-0">{entry.t}</span>
          <span className={entry.msg.startsWith("Error") ? "text-danger" : "text-slate-300"}>
            {entry.msg}
          </span>
        </div>
      ))}
      {status === "running" && (
        <div className="flex gap-2">
          <span className="text-muted shrink-0">      </span>
          <span className="text-accent animate-pulse">▌</span>
        </div>
      )}
    </div>
  );
}

function CollectTab() {
  const [jobs, setJobs] = useState<Record<string, JobStatus>>({
    pipeline:    { job: "pipeline",    status: "idle", logs: [], started_at: null, finished_at: null },
    analysis:    { job: "analysis",    status: "idle", logs: [], started_at: null, finished_at: null },
    suggestions: { job: "suggestions", status: "idle", logs: [], started_at: null, finished_at: null },
  });
  const [collectStatus, setCollectStatus] = useState<Record<string, "idle" | "running" | "done" | "error">>({});
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch initial status on mount
  useEffect(() => {
    api.admin.runStatus().then((statuses) => {
      const map: Record<string, JobStatus> = {};
      statuses.forEach((s) => { map[s.job] = s; });
      setJobs((prev) => ({ ...prev, ...map }));
    }).catch(() => {});
  }, []);

  // Start polling when any job is running
  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const statuses = await api.admin.runStatus();
        const map: Record<string, JobStatus> = {};
        statuses.forEach((s) => { map[s.job] = s; });
        setJobs((prev) => ({ ...prev, ...map }));
        const anyRunning = statuses.some((s) => s.status === "running");
        if (!anyRunning && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }, 1000);
  };

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const triggerPipelineStep = async (key: "pipeline" | "analysis" | "suggestions") => {
    const fns = {
      pipeline: api.admin.runPipeline,
      analysis: api.admin.runAnalysis,
      suggestions: api.admin.runSuggestions,
    };
    try {
      await fns[key]();
      setJobs((prev) => ({
        ...prev,
        [key]: { ...prev[key], status: "running", logs: [] },
      }));
      startPolling();
    } catch {
      setJobs((prev) => ({
        ...prev,
        [key]: { ...prev[key], status: "error" },
      }));
    }
  };

  const triggerCollect = async (source: string) => {
    setCollectStatus((prev) => ({ ...prev, [source]: "running" }));
    try {
      await (source === "all" ? api.collect.all() : api.collect.source(source));
      setCollectStatus((prev) => ({ ...prev, [source]: "done" }));
    } catch {
      setCollectStatus((prev) => ({ ...prev, [source]: "error" }));
    }
  };

  const collectIcon = (s: string) => {
    const st = collectStatus[s];
    if (st === "running") return "…";
    if (st === "done") return "✓";
    if (st === "error") return "✗";
    return "▸";
  };

  return (
    <div className="space-y-6">

      {/* Pipeline steps */}
      <div className="space-y-3">
        <div>
          <p className="text-sm font-semibold text-slate-200">Processing Pipeline</p>
          <p className="text-xs text-muted mt-0.5">Run steps 1 → 2 → 3 in order after collecting data. Each step feeds the next.</p>
        </div>

        {PIPELINE_STEPS.map((step) => {
          const job = jobs[step.key];
          const isRunning = job.status === "running";
          return (
            <div key={step.key} className="card">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <p className="text-sm font-medium text-slate-200">{step.label}</p>
                    <StatusBadge status={job.status} />
                    {job.finished_at && job.status !== "idle" && (
                      <span className="text-xs text-muted">
                        finished {new Date(job.finished_at).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted">{step.description}</p>
                </div>
                <button
                  onClick={() => triggerPipelineStep(step.key)}
                  disabled={isRunning}
                  className="btn-primary shrink-0 disabled:opacity-50"
                >
                  {isRunning ? "Running…" : job.status === "done" ? "Re-run" : "Run"}
                </button>
              </div>
              <LogPanel logs={job.logs} status={job.status} />
            </div>
          );
        })}
      </div>

      {/* Collect sources */}
      <div className="space-y-3">
        <div>
          <p className="text-sm font-semibold text-slate-200">Collect from Sources</p>
          <p className="text-xs text-muted mt-0.5">Fetch new items from individual sources or all at once.</p>
        </div>
        <div className="card">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            <button
              onClick={() => triggerCollect("all")}
              disabled={collectStatus["all"] === "running"}
              className="btn-primary justify-center py-2 col-span-full sm:col-span-1 disabled:opacity-50"
            >
              ↻ Collect All {collectIcon("all")}
            </button>
            {SOURCES.map((s) => (
              <button
                key={s}
                onClick={() => triggerCollect(s)}
                disabled={collectStatus[s] === "running"}
                className={`btn-ghost justify-between py-2 px-3 border border-surface-border rounded-lg disabled:opacity-50 ${
                  collectStatus[s] === "done" ? "text-success" :
                  collectStatus[s] === "error" ? "text-danger" :
                  collectStatus[s] === "running" ? "text-accent" : "text-muted"
                }`}
              >
                <span className="capitalize">{s.replace("_", " ")}</span>
                <span className="text-xs">{collectIcon(s)}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

    </div>
  );
}

// ---- Performance tracking ------------------------------------------------

function PerformanceTab() {
  const [form, setForm] = useState({ article_title: "", views: "", engagement_score: "", suggestion_id: "" });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const submit = async () => {
    if (!form.article_title.trim()) return;
    setSaving(true);
    try {
      await api.admin.recordPerformance({
        article_title: form.article_title,
        views: form.views ? parseInt(form.views) : undefined,
        engagement_score: form.engagement_score ? parseFloat(form.engagement_score) : undefined,
        suggestion_id: form.suggestion_id ? parseInt(form.suggestion_id) : undefined,
      });
      setForm({ article_title: "", views: "", engagement_score: "", suggestion_id: "" });
      setMsg("Performance recorded — feedback loop updated.");
    } catch {
      setMsg("Failed to record performance.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card max-w-lg space-y-4">
      <p className="text-sm font-medium text-slate-200">Record Article Performance</p>
      <p className="text-xs text-muted">
        Submit performance data to improve source weights via the feedback loop.
      </p>

      <div className="space-y-3">
        <div>
          <label className="text-xs text-muted block mb-1">Article Title *</label>
          <input
            type="text"
            value={form.article_title}
            onChange={(e) => setForm((p) => ({ ...p, article_title: e.target.value }))}
            className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-accent"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-muted block mb-1">Page Views</label>
            <input
              type="number"
              value={form.views}
              onChange={(e) => setForm((p) => ({ ...p, views: e.target.value }))}
              className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-accent"
            />
          </div>
          <div>
            <label className="text-xs text-muted block mb-1">Engagement Score (0–1)</label>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={form.engagement_score}
              onChange={(e) => setForm((p) => ({ ...p, engagement_score: e.target.value }))}
              className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-accent"
            />
          </div>
        </div>
        <div>
          <label className="text-xs text-muted block mb-1">Linked Suggestion ID (optional)</label>
          <input
            type="number"
            value={form.suggestion_id}
            onChange={(e) => setForm((p) => ({ ...p, suggestion_id: e.target.value }))}
            className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-accent"
          />
        </div>
      </div>

      <button
        onClick={submit}
        disabled={saving || !form.article_title.trim()}
        className="btn-primary w-full justify-center disabled:opacity-50"
      >
        {saving ? "Saving…" : "Record Performance"}
      </button>

      {msg && <p className="text-xs text-muted">{msg}</p>}
    </div>
  );
}

// ---- RSS Feed Management --------------------------------------------------

const CATEGORIES = ["research", "lab", "media", "community", "general"];

function RssFeedsTab() {
  const [feeds, setFeeds] = useState<RssFeed[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [testResult, setTestResult] = useState<RssFeedTestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);

  const [form, setForm] = useState({ url: "", name: "", category: "general", is_active: true });

  const load = async () => {
    setLoading(true);
    try {
      setFeeds(await api.admin.rssFeeds());
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleTest = async () => {
    if (!form.url.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await api.admin.testRssFeed(form.url.trim(), form.name || "test", form.category);
      setTestResult(result);
      // Auto-fill name from feed title if empty
      if (result.ok && result.title && !form.name) {
        setForm((p) => ({ ...p, name: result.title! }));
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setTestResult({ url: form.url, ok: false, title: null, entry_count: 0, sample_titles: [], error: msg });
    }
    setTesting(false);
  };

  const handleSave = async () => {
    if (!form.url.trim() || !form.name.trim()) return;
    setSaving(true);
    try {
      if (editId !== null) {
        await api.admin.updateRssFeed(editId, { name: form.name, category: form.category, is_active: form.is_active });
      } else {
        await api.admin.createRssFeed({ url: form.url.trim(), name: form.name.trim(), category: form.category, is_active: form.is_active });
      }
      setForm({ url: "", name: "", category: "general", is_active: true });
      setTestResult(null);
      setShowAdd(false);
      setEditId(null);
      await load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      alert(msg);
    }
    setSaving(false);
  };

  const handleToggle = async (feed: RssFeed) => {
    try {
      await api.admin.updateRssFeed(feed.id, { is_active: !feed.is_active });
      await load();
    } catch {}
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this feed?")) return;
    try {
      await api.admin.deleteRssFeed(id);
      await load();
    } catch {}
  };

  const startEdit = (feed: RssFeed) => {
    setForm({ url: feed.url, name: feed.name, category: feed.category, is_active: feed.is_active });
    setEditId(feed.id);
    setShowAdd(true);
    setTestResult(null);
  };

  const cancelForm = () => {
    setForm({ url: "", name: "", category: "general", is_active: true });
    setTestResult(null);
    setShowAdd(false);
    setEditId(null);
  };

  const grouped = CATEGORIES.map((cat) => ({
    cat,
    feeds: feeds.filter((f) => f.category === cat),
  })).filter((g) => g.feeds.length > 0);
  const ungrouped = feeds.filter((f) => !CATEGORIES.includes(f.category));
  if (ungrouped.length) grouped.push({ cat: "other", feeds: ungrouped });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted">
            {feeds.length} feed{feeds.length !== 1 ? "s" : ""} —{" "}
            {feeds.filter((f) => f.is_active).length} active
          </p>
        </div>
        {!showAdd && (
          <button onClick={() => setShowAdd(true)} className="btn-primary">
            + Add Feed
          </button>
        )}
      </div>

      {/* Add / Edit form */}
      {showAdd && (
        <div className="bg-surface border border-surface-border rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-semibold text-slate-100">
            {editId !== null ? "Edit Feed" : "Add RSS Feed"}
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="md:col-span-2">
              <label className="text-xs text-muted block mb-1">Feed URL *</label>
              <div className="flex gap-2">
                <input
                  type="url"
                  value={form.url}
                  onChange={(e) => { setForm((p) => ({ ...p, url: e.target.value })); setTestResult(null); }}
                  disabled={editId !== null}
                  placeholder="https://example.com/feed.xml"
                  className="flex-1 bg-surface-2 border border-surface-border rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-accent disabled:opacity-50"
                />
                <button
                  onClick={handleTest}
                  disabled={testing || !form.url.trim() || editId !== null}
                  className="px-3 py-2 text-sm bg-surface-2 border border-surface-border rounded hover:border-accent disabled:opacity-40 transition-colors"
                >
                  {testing ? "Testing…" : "Test"}
                </button>
              </div>
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">Name *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                placeholder="OpenAI Blog"
                className="w-full bg-surface-2 border border-surface-border rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-accent"
              />
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">Category</label>
              <select
                value={form.category}
                onChange={(e) => setForm((p) => ({ ...p, category: e.target.value }))}
                className="w-full bg-surface-2 border border-surface-border rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-accent"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm text-muted cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))}
              className="accent-accent"
            />
            Active (collect automatically)
          </label>

          {/* Test result */}
          {testResult && (
            <div className={`rounded p-3 text-xs space-y-1 ${testResult.ok ? "bg-green-950 border border-green-800" : "bg-red-950 border border-red-800"}`}>
              {testResult.ok ? (
                <>
                  <p className="text-green-400 font-medium">✓ Feed OK — {testResult.entry_count} entries</p>
                  {testResult.title && <p className="text-slate-300">Feed title: <span className="text-slate-100">{testResult.title}</span></p>}
                  {testResult.sample_titles.length > 0 && (
                    <ul className="text-slate-400 pl-2 space-y-0.5">
                      {testResult.sample_titles.map((t, i) => <li key={i}>· {t}</li>)}
                    </ul>
                  )}
                </>
              ) : (
                <p className="text-red-400">✗ {testResult.error || "Feed failed to parse"}</p>
              )}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button
              onClick={handleSave}
              disabled={saving || !form.url.trim() || !form.name.trim()}
              className="btn-primary disabled:opacity-50"
            >
              {saving ? "Saving…" : editId !== null ? "Update Feed" : "Add Feed"}
            </button>
            <button onClick={cancelForm} className="px-3 py-1.5 text-sm text-muted hover:text-slate-300 transition-colors">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Feed list grouped by category */}
      {loading ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : feeds.length === 0 ? (
        <p className="text-sm text-muted">No feeds yet. Add one above.</p>
      ) : (
        <div className="space-y-4">
          {grouped.map(({ cat, feeds: catFeeds }) => (
            <div key={cat}>
              <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-2 capitalize">{cat}</h3>
              <div className="space-y-1">
                {catFeeds.map((feed) => (
                  <div
                    key={feed.id}
                    className={`flex items-start gap-3 rounded-lg px-3 py-2.5 border transition-colors ${
                      feed.is_active
                        ? "bg-surface border-surface-border"
                        : "bg-surface/50 border-surface-border/50 opacity-60"
                    }`}
                  >
                    {/* Toggle */}
                    <button
                      onClick={() => handleToggle(feed)}
                      title={feed.is_active ? "Disable" : "Enable"}
                      className={`mt-0.5 w-3 h-3 rounded-full flex-shrink-0 border-2 transition-colors ${
                        feed.is_active ? "bg-green-500 border-green-500" : "bg-transparent border-slate-500"
                      }`}
                    />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-slate-100 font-medium truncate">{feed.name}</span>
                        {feed.error_count > 0 && (
                          <span className="text-xs text-red-400 flex-shrink-0">{feed.error_count} err</span>
                        )}
                      </div>
                      <p className="text-xs text-muted truncate">{feed.url}</p>
                      <div className="flex gap-3 mt-1 text-xs text-slate-500">
                        {feed.last_collected_at && (
                          <span>collected {new Date(feed.last_collected_at).toLocaleString()}</span>
                        )}
                        {feed.item_count > 0 && <span>{feed.item_count} items total</span>}
                        {feed.last_error && (
                          <span className="text-red-400 truncate max-w-xs" title={feed.last_error}>
                            ⚠ {feed.last_error}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex gap-1 flex-shrink-0">
                      <button
                        onClick={() => startEdit(feed)}
                        className="px-2 py-1 text-xs text-muted hover:text-slate-300 transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(feed.id)}
                        className="px-2 py-1 text-xs text-red-500 hover:text-red-400 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-muted">
        Active feeds are collected automatically every hour. Use the Collect tab to trigger immediately.
        Click the green/grey dot to enable or disable a feed without deleting it.
      </p>
    </div>
  );
}
