import { api } from "@/lib/api";
import Badge from "@/components/Badge";
import StatCard from "@/components/StatCard";

export default async function InsightsPage() {
  let data = null;
  try { data = await api.insights(100); } catch {}

  const avgConf = data?.insights.length
    ? (data.insights.reduce((a, i) => a + i.confidence, 0) / data.insights.length * 100).toFixed(1)
    : "—";

  return (
    <div className="max-w-screen-xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold" style={{ letterSpacing: "-0.02em" }}>
          <span className="gradient-text">Insights</span>
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          AI-synthesized decision intelligence from market signals
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total" value={data?.total ?? "—"} />
        <StatCard label="Avg Confidence" value={avgConf !== "—" ? avgConf + "%" : "—"} accent />
        <StatCard label="Draft" value={data?.insights.filter(i => i.status === "draft").length ?? 0} />
        <StatCard label="Used" value={data?.insights.filter(i => i.status === "used").length ?? 0} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {data?.insights.length ? data.insights.map(insight => (
          <div key={insight.id} className="card-glass p-6">
            <div className="flex items-start justify-between gap-4 mb-3">
              <h3 className="font-semibold text-base leading-snug" style={{ color: "var(--text-primary)" }}>
                {insight.title}
              </h3>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span
                  className="text-sm font-bold"
                  style={{ color: insight.confidence >= 0.7 ? "#4ade80" : insight.confidence >= 0.5 ? "#facc15" : "#f87171" }}
                >
                  {(insight.confidence * 100).toFixed(0)}%
                </span>
                <Badge label={insight.status} />
              </div>
            </div>
            <p className="text-sm leading-relaxed mb-4" style={{ color: "var(--text-secondary)" }}>
              {insight.summary}
            </p>
            <div className="flex items-center gap-3 text-xs" style={{ color: "#475569" }}>
              {insight.category && (
                <span
                  className="px-2 py-0.5 rounded-md capitalize"
                  style={{ background: "rgba(255,106,61,0.1)", color: "#ff6a3d" }}
                >
                  {insight.category}
                </span>
              )}
              <span>{new Date(insight.created_at).toLocaleDateString()}</span>
            </div>
          </div>
        )) : (
          <div className="col-span-2 card-glass py-16 text-center">
            <p className="text-4xl mb-3">💡</p>
            <p className="font-medium" style={{ color: "var(--text-primary)" }}>No insights generated yet</p>
            <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
              Collect signals first, then trigger POST /api/insights/generate
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
