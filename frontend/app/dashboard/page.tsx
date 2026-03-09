import { api } from "@/lib/api";
import StatCard from "@/components/StatCard";
import Badge from "@/components/Badge";

async function getData() {
  try {
    const [signals, insights, content, queue, analytics] = await Promise.allSettled([
      api.signals(5),
      api.insights(5),
      api.content(5),
      api.queue(5),
      api.analyticsDashboard(),
    ]);
    return {
      signals: signals.status === "fulfilled" ? signals.value : null,
      insights: insights.status === "fulfilled" ? insights.value : null,
      content: content.status === "fulfilled" ? content.value : null,
      queue: queue.status === "fulfilled" ? queue.value : null,
      analytics: analytics.status === "fulfilled" ? analytics.value : null,
    };
  } catch {
    return { signals: null, insights: null, content: null, queue: null, analytics: null };
  }
}

export default async function DashboardPage() {
  const { signals, insights, content, queue, analytics } = await getData();

  return (
    <div className="max-w-screen-xl mx-auto">
      {/* Header */}
      <div className="mb-10">
        <div className="flex items-center gap-3 mb-2">
          <div
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ background: "#4ade80" }}
          />
          <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#4ade80" }}>
            System Online
          </span>
        </div>
        <h1 className="text-4xl font-bold leading-tight" style={{ letterSpacing: "-0.02em" }}>
          Marketing{" "}
          <span className="gradient-text text-glow">Intelligence</span>
        </h1>
        <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
          Full pipeline overview — Signals → Insights → Content → Distribution → Analytics
        </p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Signals" value={signals?.total ?? "—"} sub="Collected market signals" />
        <StatCard label="Insights" value={insights?.total ?? "—"} sub="Generated insights" />
        <StatCard label="Content" value={content?.total ?? "—"} sub="Drafts & published" />
        <StatCard
          label="Avg Engagement"
          value={analytics ? (analytics.avg_engagement_rate * 100).toFixed(2) + "%" : "—"}
          sub="Across all channels"
          accent
        />
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Signals */}
        <div className="card-glass p-6">
          <div className="flex items-center justify-between mb-5">
            <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#475569" }}>
              Recent Signals
            </p>
            <a href="/signals" className="text-xs transition-colors hover:text-white" style={{ color: "#ff6a3d" }}>
              View all →
            </a>
          </div>
          {signals?.content.length ? (
            <ul className="space-y-3">
              {signals.content.map(s => (
                <li key={s.id} className="flex items-start gap-3 pb-3 border-b last:border-0 last:pb-0" style={{ borderColor: "var(--border)" }}>
                  <div className="mt-1 w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: "#ff6a3d" }} />
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>{s.title}</p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                      {s.source} · Score {(s.relevance_score * 10).toFixed(1)}
                    </p>
                  </div>
                  <Badge label={s.status} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm py-6 text-center" style={{ color: "var(--text-secondary)" }}>No signals yet</p>
          )}
        </div>

        {/* Recent Insights */}
        <div className="card-glass p-6">
          <div className="flex items-center justify-between mb-5">
            <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#475569" }}>
              Recent Insights
            </p>
            <a href="/insights" className="text-xs transition-colors hover:text-white" style={{ color: "#ff6a3d" }}>
              View all →
            </a>
          </div>
          {insights?.insights.length ? (
            <ul className="space-y-3">
              {insights.insights.map(i => (
                <li key={i.id} className="pb-3 border-b last:border-0 last:pb-0" style={{ borderColor: "var(--border)" }}>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>{i.title}</p>
                    <span className="text-xs font-bold flex-shrink-0" style={{ color: "#ff6a3d" }}>
                      {(i.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-xs truncate" style={{ color: "var(--text-secondary)" }}>{i.summary}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm py-6 text-center" style={{ color: "var(--text-secondary)" }}>No insights yet</p>
          )}
        </div>

        {/* Content Pipeline */}
        <div className="card-glass p-6">
          <div className="flex items-center justify-between mb-5">
            <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#475569" }}>
              Content Pipeline
            </p>
            <a href="/content" className="text-xs transition-colors hover:text-white" style={{ color: "#ff6a3d" }}>
              View all →
            </a>
          </div>
          {content?.content.length ? (
            <ul className="space-y-3">
              {content.content.map(c => (
                <li key={c.id} className="flex items-center gap-3 pb-3 border-b last:border-0 last:pb-0" style={{ borderColor: "var(--border)" }}>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>{c.title || c.topic}</p>
                    <p className="text-xs mt-0.5 capitalize" style={{ color: "var(--text-secondary)" }}>
                      {c.content_type.replace("_", " ")}
                    </p>
                  </div>
                  <Badge label={c.status} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm py-6 text-center" style={{ color: "var(--text-secondary)" }}>No content yet</p>
          )}
        </div>

        {/* Publishing Queue */}
        <div className="card-glass p-6">
          <div className="flex items-center justify-between mb-5">
            <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#475569" }}>
              Publishing Queue
            </p>
            <a href="/distribution" className="text-xs transition-colors hover:text-white" style={{ color: "#ff6a3d" }}>
              View all →
            </a>
          </div>
          {queue?.items.length ? (
            <ul className="space-y-3">
              {queue.items.map(q => (
                <li key={q.id} className="flex items-center gap-3 pb-3 border-b last:border-0 last:pb-0" style={{ borderColor: "var(--border)" }}>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                      Content #{q.content_id}
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                      {q.scheduled_time ? new Date(q.scheduled_time).toLocaleString() : "Immediate"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge label={q.channel} />
                    <Badge label={q.status} />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm py-6 text-center" style={{ color: "var(--text-secondary)" }}>Queue empty</p>
          )}
        </div>
      </div>

      {/* Top Topics */}
      {analytics?.top_topics.length ? (
        <div className="card-glass p-6 mt-6">
          <p className="text-xs font-semibold uppercase tracking-widest mb-5" style={{ color: "#475569" }}>
            Top Performing Topics
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {analytics.top_topics.slice(0, 6).map((t, i) => (
              <div
                key={t.topic}
                className="flex items-center gap-3 px-4 py-3 rounded-xl"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)" }}
              >
                <span className="text-lg font-bold" style={{ color: "#ff6a3d", minWidth: 24 }}>
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>{t.topic}</p>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    {t.content_count} piece{t.content_count !== 1 ? "s" : ""}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
