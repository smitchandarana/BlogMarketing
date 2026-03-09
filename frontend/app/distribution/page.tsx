import { api } from "@/lib/api";
import Badge from "@/components/Badge";
import StatCard from "@/components/StatCard";

export default async function DistributionPage() {
  let data = null;
  try { data = await api.queue(200); } catch {}

  const queued    = data?.items.filter(i => i.status === "queued").length    ?? 0;
  const scheduled = data?.items.filter(i => i.status === "scheduled").length ?? 0;
  const published = data?.items.filter(i => i.status === "published").length ?? 0;
  const failed    = data?.items.filter(i => i.status === "failed").length    ?? 0;

  return (
    <div className="max-w-screen-xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold" style={{ letterSpacing: "-0.02em" }}>
          <span className="gradient-text">Distribution</span>
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Publishing queue across LinkedIn and website channels
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Jobs" value={data?.total ?? "—"} />
        <StatCard label="Queued" value={queued + scheduled} sub="Pending publish" />
        <StatCard label="Published" value={published} accent />
        <StatCard label="Failed" value={failed} />
      </div>

      <div className="card-glass overflow-hidden">
        <div className="px-6 py-4 border-b flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
          <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#475569" }}>
            Queue
          </p>
          <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
            {data?.total ?? 0} items
          </span>
        </div>

        {data?.items.length ? (
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["#", "Content ID", "Channel", "Scheduled", "Published", "Status", "URL"].map(h => (
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
              {data.items.map((item, i) => (
                <tr
                  key={item.id}
                  style={{ borderBottom: i < data.items.length - 1 ? "1px solid rgba(30,41,59,0.5)" : "none" }}
                >
                  <td className="px-6 py-4 text-xs" style={{ color: "#475569" }}>{item.id}</td>
                  <td className="px-6 py-4 font-medium" style={{ color: "var(--text-primary)" }}>
                    #{item.content_id}
                  </td>
                  <td className="px-6 py-4"><Badge label={item.channel} /></td>
                  <td className="px-6 py-4 text-xs" style={{ color: "var(--text-secondary)" }}>
                    {item.scheduled_time ? new Date(item.scheduled_time).toLocaleString() : "—"}
                  </td>
                  <td className="px-6 py-4 text-xs" style={{ color: "var(--text-secondary)" }}>
                    {item.published_at ? new Date(item.published_at).toLocaleString() : "—"}
                  </td>
                  <td className="px-6 py-4"><Badge label={item.status} /></td>
                  <td className="px-6 py-4">
                    {item.external_url ? (
                      <a
                        href={item.external_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs underline-offset-2 hover:underline"
                        style={{ color: "#ff6a3d" }}
                      >
                        View ↗
                      </a>
                    ) : (
                      <span className="text-xs" style={{ color: "#475569" }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="py-16 text-center">
            <p className="text-4xl mb-3">📬</p>
            <p className="font-medium" style={{ color: "var(--text-primary)" }}>Queue is empty</p>
            <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
              Queue content via POST /api/distribution/distribute
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
