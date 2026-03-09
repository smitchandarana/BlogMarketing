import { api } from "@/lib/api";
import Badge from "@/components/Badge";
import StatCard from "@/components/StatCard";

export default async function SignalsPage() {
  let data = null;
  try { data = await api.signals(100); } catch {}

  const byStatus = (data?.content ?? []).reduce((acc: Record<string, number>, s) => {
    acc[s.status] = (acc[s.status] ?? 0) + 1;
    return acc;
  }, {});

  const avgScore = data?.content.length
    ? (data.content.reduce((a, s) => a + s.relevance_score, 0) / data.content.length * 10).toFixed(2)
    : "—";

  return (
    <div className="max-w-screen-xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold" style={{ letterSpacing: "-0.02em" }}>
          <span className="gradient-text">Signals</span>
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Market intelligence collected from RSS feeds and Reddit
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total" value={data?.total ?? "—"} />
        <StatCard label="Avg Score" value={avgScore} sub="out of 10" accent />
        <StatCard label="Draft" value={byStatus.draft ?? 0} />
        <StatCard label="Processed" value={(byStatus.processed ?? 0) + (byStatus.used ?? 0)} />
      </div>

      <div className="card-glass overflow-hidden">
        <div className="px-6 py-4 border-b flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
          <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#475569" }}>
            All Signals
          </p>
          <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
            {data?.total ?? 0} total
          </span>
        </div>
        {data?.content.length ? (
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Source", "Title", "Category", "Score", "Status", "Date"].map(h => (
                  <th
                    key={h}
                    className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider"
                    style={{ color: "#475569" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.content.map((s, i) => (
                <tr
                  key={s.id}
                  style={{
                    borderBottom: i < data.content.length - 1 ? "1px solid rgba(30,41,59,0.5)" : "none",
                  }}
                >
                  <td className="px-6 py-4" style={{ color: "var(--text-secondary)" }}>
                    <span className="capitalize">{s.source}</span>
                  </td>
                  <td className="px-6 py-4 max-w-xs">
                    <p className="font-medium truncate" style={{ color: "var(--text-primary)" }}>{s.title}</p>
                    {s.summary && (
                      <p className="text-xs mt-0.5 truncate" style={{ color: "var(--text-secondary)" }}>{s.summary}</p>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-xs capitalize" style={{ color: "var(--text-secondary)" }}>
                      {s.category ?? "—"}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="font-semibold" style={{ color: "#ff6a3d" }}>
                      {(s.relevance_score * 10).toFixed(1)}
                    </span>
                  </td>
                  <td className="px-6 py-4"><Badge label={s.status} /></td>
                  <td className="px-6 py-4 text-xs" style={{ color: "#475569" }}>
                    {new Date(s.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="py-16 text-center">
            <p className="text-4xl mb-3">📡</p>
            <p className="font-medium" style={{ color: "var(--text-primary)" }}>No signals collected yet</p>
            <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
              Trigger a collection run via POST /api/signals/collect
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
