const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const V1 = `${BASE}/api/v1`;

async function get<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
  const url = new URL(`${V1}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));
  }
  const res = await fetch(url.toString(), { next: { revalidate: 30 } });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${V1}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${V1}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`PUT ${path} → ${res.status}`);
  return res.json();
}

// ---- Types ---------------------------------------------------------------

export interface TrendingTopic {
  topic_id: number;
  name: string;
  slug: string;
  category: string | null;
  score: number;
  classification: "write_now" | "monitor" | "ignore";
  confidence_level: "high" | "medium" | "low";
  source_count: number;
  consistency_days: number;
  score_breakdown: Record<string, number> | null;
}

export interface TimeSeriesPoint {
  snapshot_date: string;
  mention_count: number;
  weighted_mention_count: number;
  momentum_score: number | null;
  sentiment_avg: number | null;
  sources: string[] | null;
}

export interface TopicTimeSeries {
  topic_id: number;
  name: string;
  slug: string;
  data: TimeSeriesPoint[];
}

export interface Pattern {
  id: number;
  pattern_type: string;
  title: string;
  description: string | null;
  evidence: Record<string, unknown> | null;
  confidence_score: number;
  detected_at: string;
  topic_ids: number[] | null;
}

export interface ContentSuggestion {
  id: number;
  title: string;
  rationale: string | null;
  insight: string | null;
  suggested_articles: string[] | null;
  topic_ids: number[] | null;
  urgency_score: number;
  confidence_level: string;
  created_at: string;
  used: boolean;
}

export interface SourceWeight {
  id: number;
  source: string;
  weight: number;
  updated_at: string;
}

export interface AIProvider {
  id: number;
  provider: string;
  model_id: string;
  is_active: boolean;
  updated_at: string;
}

export interface Topic {
  id: number;
  name: string;
  slug: string;
  category: string | null;
  aliases: string[] | null;
  is_approved: boolean;
}

export interface UnresolvedTopic {
  id: number;
  raw_text: string;
  occurrence_count: number;
  suggested_canonical_id: number | null;
  suggested_merge_id: number | null;
  first_seen_at: string;
  last_seen_at: string;
}

export interface SystemLogEntry {
  t: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  logger: string;
  msg: string;
}

export interface JobLogEntry {
  t: string;
  msg: string;
}

export interface JobStatus {
  job: string;
  status: "idle" | "running" | "done" | "error";
  logs: JobLogEntry[];
  started_at: string | null;
  finished_at: string | null;
}

export interface SystemConfig {
  key: string;
  value: string;
  is_secret: boolean;
  category: string;
  description: string | null;
  updated_at: string;
}

export interface RssFeed {
  id: number;
  url: string;
  name: string;
  category: string;
  is_active: boolean;
  last_collected_at: string | null;
  last_error: string | null;
  error_count: number;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface RssFeedTestResult {
  url: string;
  ok: boolean;
  title: string | null;
  entry_count: number;
  sample_titles: string[];
  error: string | null;
}

export interface SystemStats {
  total_items: number;
  items_today: number;
  items_last_7d: number;
  total_topics: number;
  active_topics: number;
  patterns_detected: number;
  suggestions_available: number;
  sources_active: string[];
  last_collection_at: string | null;
}

export interface TopicItem {
  id: number;
  source: string;
  title: string | null;
  url: string | null;
  author: string | null;
  published_at: string | null;
  importance_score: number | null;
}

export interface TopicSourceBreakdown {
  source: string;
  mention_count: number;
}

export interface RawItem {
  id: number;
  source: string;
  url: string | null;
  title: string | null;
  author: string | null;
  published_at: string | null;
  collected_at: string;
  importance_score: number | null;
  mention_count: number;
}

// ---- API calls -----------------------------------------------------------

export const api = {
  stats: () => get<SystemStats>("/stats"),

  trends: {
    current: (limit = 20, classification?: string) =>
      get<TrendingTopic[]>("/trends/current", { limit, ...(classification ? { classification } : {}) }),
    emerging: (limit = 10) => get<TrendingTopic[]>("/trends/emerging", { limit }),
    declining: (limit = 10) => get<TrendingTopic[]>("/trends/declining", { limit }),
    timeseries: (slug: string, days = 30) =>
      get<TopicTimeSeries>(`/trends/${slug}/timeseries`, { days }),
    items: (slug: string, days = 30) =>
      get<TopicItem[]>(`/trends/${slug}/items`, { days, limit: 50 }),
    sources: (slug: string, days = 30) =>
      get<TopicSourceBreakdown[]>(`/trends/${slug}/sources`, { days }),
  },

  patterns: {
    list: (pattern_type?: string, limit = 20) =>
      get<Pattern[]>("/patterns", { limit, ...(pattern_type ? { pattern_type } : {}) }),
  },

  suggestions: {
    list: (unused_only = true, limit = 20) =>
      get<ContentSuggestion[]>("/suggestions", { unused_only, limit }),
    markUsed: (id: number) => post<{ status: string }>(`/suggestions/${id}/use`),
  },

  search: {
    topics: (q: string) => get<Topic[]>("/search/topics", { q }),
    items: (q: string) => get<RawItem[]>("/search/items", { q }),
  },

  admin: {
    weights: () => get<SourceWeight[]>("/admin/weights"),
    updateWeight: (source: string, weight: number) =>
      put<SourceWeight>(`/admin/weights/${source}`, { weight }),

    providers: () => get<AIProvider[]>("/admin/provider"),
    setActiveProvider: (provider: string, model_id: string) =>
      put<AIProvider>("/admin/provider/active", { provider, model_id }),

    topics: () => get<Topic[]>("/admin/topics"),
    approveTopic: (id: number) => post<{ status: string }>(`/admin/topics/${id}/approve`),
    deleteTopic: (id: number) =>
      fetch(`${V1}/admin/topics/${id}`, { method: "DELETE", cache: "no-store" }).then((r) => r.json()),

    unresolvedTopics: () => get<UnresolvedTopic[]>("/admin/unresolved-topics"),
    resolveUnresolved: (id: number, canonical_id: number) =>
      post<{ status: string }>(`/admin/unresolved-topics/${id}/resolve?canonical_id=${canonical_id}`),
    promoteUnresolved: (id: number) =>
      post<Topic>(`/admin/unresolved-topics/${id}/create-new`),

    recordPerformance: (data: {
      suggestion_id?: number;
      article_title: string;
      views?: number;
      engagement_score?: number;
    }) => post<{ status: string }>("/admin/performance", data),

    config: () => get<SystemConfig[]>("/admin/config"),
    updateConfig: (key: string, value: string) =>
      put<SystemConfig>(`/admin/config/${key}`, { value }),

    runPipeline: () => post<{ status: string }>("/admin/run/pipeline"),
    runAnalysis: () => post<{ status: string }>("/admin/run/analysis"),
    runSuggestions: () => post<{ status: string }>("/admin/run/suggestions"),
    runStatus: () => get<JobStatus[]>("/admin/run/status"),
    logs: (level?: string, limit = 500) =>
      get<SystemLogEntry[]>("/admin/logs", { ...(level ? { level } : {}), limit }),
    clearLogs: () => post<{ status: string }>("/admin/logs/clear"),

    rssFeeds: () => get<RssFeed[]>("/admin/rss-feeds"),
    createRssFeed: (data: { url: string; name: string; category: string; is_active: boolean }) =>
      post<RssFeed>("/admin/rss-feeds", data),
    updateRssFeed: (id: number, data: { name?: string; category?: string; is_active?: boolean }) =>
      put<RssFeed>(`/admin/rss-feeds/${id}`, data),
    deleteRssFeed: (id: number) =>
      fetch(`${V1}/admin/rss-feeds/${id}`, { method: "DELETE", cache: "no-store" }).then((r) => r.json()),
    testRssFeed: (url: string, name: string, category: string) =>
      post<RssFeedTestResult>("/admin/rss-feeds/test", { url, name, category }),
  },

  collect: {
    all: () => post<{ status: string }>("/collect/all"),
    source: (source: string) => post<{ status: string }>(`/collect/${source}`),
  },
};
