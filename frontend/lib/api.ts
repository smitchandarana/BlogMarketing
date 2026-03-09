const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API POST ${path} → ${res.status}`);
  return res.json();
}

// ---------- Types ----------
export interface Signal {
  id: number;
  source: string;
  title: string;
  summary: string | null;
  relevance_score: number;
  category: string | null;
  status: string;
  created_at: string;
}

export interface Insight {
  id: number;
  title: string;
  summary: string;
  category: string | null;
  confidence: number;
  status: string;
  created_at: string;
}

export interface Content {
  id: number;
  content_type: string;
  topic: string;
  title: string;
  body: string;
  hashtags: string;
  status: string;
  performance_score?: number;
  created_at: string;
}

export interface QueueItem {
  id: number;
  content_id: number;
  channel: string;
  status: string;
  scheduled_time: string | null;
  published_at: string | null;
  external_url: string | null;
  created_at: string;
}

export interface DashboardData {
  avg_engagement_rate: number;
  top_topics: { topic: string; avg_engagement: number; content_count: number }[];
  top_formats: { content_type: string; avg_engagement: number; content_count: number }[];
  best_linkedin_hours: { hour: number; avg_engagement: number; sample_count: number }[];
  best_website_hours: { hour: number; avg_engagement: number; sample_count: number }[];
}

export interface TopContentItem {
  id: number;
  topic: string;
  content_type: string;
  performance_score: number;
  status: string;
  created_at: string;
}

// ---------- API calls ----------
export const api = {
  health: () => get<{ status: string; version: string }>("/health"),
  signals: (limit = 20) => get<{ content: Signal[]; total: number }>(`/api/signals?limit=${limit}`),
  collectSignals: () => post<{ signals_new: number; signals_scored: number; timestamp: string }>("/api/signals/collect"),
  signalWorker: () => get<{ running: boolean }>("/api/signals/worker"),

  insights: (limit = 20) => get<{ insights: Insight[]; total: number }>(`/api/insights?limit=${limit}`),
  generateInsights: () => post<unknown>("/api/insights/generate"),
  insightWorker: () => get<{ running: boolean }>("/api/insights/worker"),

  content: (limit = 20) => get<{ content: Content[]; total: number }>(`/api/content?limit=${limit}`),
  generateContent: () => post<unknown>("/api/content/generate"),
  contentWorker: () => get<{ running: boolean }>("/api/content/worker"),

  queue: (limit = 50) => get<{ items: QueueItem[]; total: number }>(`/api/distribution/queue?limit=${limit}`),
  distribute: (content_id: number, content_type: string) =>
    post<unknown>("/api/distribution/distribute", { content_id, content_type }),
  runDistribution: () => post<unknown>("/api/distribution/run"),
  distributionWorker: () => get<{ running: boolean }>("/api/distribution/worker"),

  analyticsDashboard: () => get<DashboardData>("/api/analytics/dashboard"),
  topContent: (limit = 10) => get<{ items: TopContentItem[]; total: number }>(`/api/analytics/top-content?limit=${limit}`),
  collectAnalytics: () => post<unknown>("/api/analytics/collect"),
  analyticsWorker: () => get<{ running: boolean }>("/api/analytics/worker"),
};
