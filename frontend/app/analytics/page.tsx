import { api } from "@/lib/api";
import StatCard from "@/components/StatCard";
import { EngagementBar } from "@/components/AnalyticsChart";

export default async function AnalyticsPage() {
  let dash = null;
  let top = null;
  try { dash = await api.analyticsDashboard(); } catch {}
  try { top = await api.topContent(10); } catch {}

  const liHours = (dash?.best_linkedin_hours ?? []).map(h => ({
    label: `${h.hour}:00`,
    value: h.avg_engagement,
  }));
  const webHours = (dash?.best_website_hours ?? []).map(h => ({
    label: `${h.hour}:00`,
    value: h.avg_engagement,
  }));
  const topics = (dash?.top_topics ?? []).slice(0, 8).map(t => ({
    label: t.topic.substring(0, 20),
    value: t.avg_engagement,
  }));

  return (
    <div className="max-w-screen-xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold" style={{ letterSpacing: "-0.02em" }}>
          <span className="gradient-text">Analytics</span>
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Performance metrics, engagement trends, and feedback signals
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Avg Engagement"
          value={dash ? (dash.avg_engagement_rate * 100).toFixed(3) + "%" : "—"}
          sub="Across all channels"
          accent
        />
        <StatCard
          label="Top Topics"
          value={dash?.top_topics.length ?? "—"}
          sub="Ranked by engagement"
        />
        <StatCard
          label="Best LinkedIn Hour"
          value={liHours[0] ? liHours[0].label : "—"}
          sub="Optimal posting time"
        />
        <StatCard
          label="Formats Tracked"
          value={dash?.top_formats.length ?? "—"}
          sub="Content types analysed"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <EngagementBar data={topics} title="Top Topics by Engagement" />
        <EngagementBar data={liHours} title="Best LinkedIn Posting Hours" />
        <EngagementBar data={webHours} title="Best Website Posting Hours" />
      </div>

      {/* Formats */}
      {dash?.top_formats.length ? (
        <div className="card-glass p-6 mb-6">
          <p className="text-xs font-semibold uppercase tracking-widest mb-5" style={{ color: "#475569" }}>
            Content Format Performance
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {dash.top_formats.map(f => (
              <div
                key={f.content_type}
                className="px-5 py-4 rounded-xl flex items-center justify-between"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)" }}
              >
                <div>
                  <p className="font-medium text-sm capitalize" style={{ color: "var(--text-primary)" }}>
                    {f.content_type.replace("_", " ")}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                    {f.content_count} piece{f.content_count !== 1 ? "s" : ""}
                  </p>
                </div>
                <span className="text-xl font-bold" style={{ color: "#ff6a3d" }}>
                  {(f.avg_engagement * 100).toFixed(2)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Top Content */}
      <div className="card-glass overflow-hidden">
        <div className="px-6 py-4 border-b" style={{ borderColor: "var(--border)" }}>
          <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#475569" }}>
            Top Performing Content
          </p>
        </div>
        {top?.items.length ? (
          <div className="divide-y" style={{ borderColor: "var(--border)" }}>
            {top.items.map((item, i) => (
              <div key={item.id} className="px-6 py-4 flex items-center gap-4">
                <span
                  className="text-2xl font-black w-8 text-center flex-shrink-0"
                  style={{ color: i === 0 ? "#ff6a3d" : "#334155" }}
                >
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate" style={{ color: "var(--text-primary)" }}>{item.topic}</p>
                  <p className="text-xs mt-0.5 capitalize" style={{ color: "var(--text-secondary)" }}>
                    {item.content_type.replace("_", " ")} · {new Date(item.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="font-bold text-lg" style={{ color: "#ff6a3d" }}>
                    {(item.performance_score * 100).toFixed(1)}
                  </p>
                  <p className="text-xs" style={{ color: "#475569" }}>score</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-16 text-center">
            <p className="text-4xl mb-3">📊</p>
            <p className="font-medium" style={{ color: "var(--text-primary)" }}>No metrics collected yet</p>
            <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
              Trigger POST /api/analytics/collect to gather data
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
