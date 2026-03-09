import { api } from "@/lib/api";
import Badge from "@/components/Badge";
import StatCard from "@/components/StatCard";

export default async function ContentPage() {
  let data = null;
  try { data = await api.content(100); } catch {}

  const blogs = data?.content.filter(c => c.content_type === "blog_post").length ?? 0;
  const liPosts = data?.content.filter(c => c.content_type === "linkedin_post").length ?? 0;
  const published = data?.content.filter(c => c.status === "published").length ?? 0;

  return (
    <div className="max-w-screen-xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold" style={{ letterSpacing: "-0.02em" }}>
          <span className="gradient-text">Content</span>
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          AI-generated blog posts and LinkedIn content
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total" value={data?.total ?? "—"} />
        <StatCard label="Blog Posts" value={blogs} />
        <StatCard label="LinkedIn" value={liPosts} />
        <StatCard label="Published" value={published} accent />
      </div>

      <div className="card-glass overflow-hidden">
        <div className="px-6 py-4 border-b" style={{ borderColor: "var(--border)" }}>
          <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#475569" }}>
            All Content
          </p>
        </div>
        {data?.content.length ? (
          <div className="divide-y" style={{ borderColor: "var(--border)" }}>
            {data.content.map(c => (
              <div key={c.id} className="px-6 py-5 flex items-start gap-4">
                {/* Type pill */}
                <div
                  className="mt-0.5 px-2 py-0.5 rounded-md text-xs font-semibold flex-shrink-0 capitalize"
                  style={{
                    background: c.content_type === "blog_post"
                      ? "rgba(255,106,61,0.1)" : "rgba(10,102,194,0.12)",
                    color: c.content_type === "blog_post" ? "#ff6a3d" : "#60a5fa",
                  }}
                >
                  {c.content_type.replace("_", " ")}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <p className="font-semibold truncate" style={{ color: "var(--text-primary)" }}>
                      {c.title || c.topic}
                    </p>
                    <Badge label={c.status} />
                  </div>
                  <p className="text-xs mb-2 line-clamp-2" style={{ color: "var(--text-secondary)" }}>
                    {c.body ? c.body.substring(0, 160) + (c.body.length > 160 ? "…" : "") : c.topic}
                  </p>
                  <div className="flex items-center gap-3 text-xs" style={{ color: "#475569" }}>
                    <span>{new Date(c.created_at).toLocaleDateString()}</span>
                    {c.hashtags && (
                      <span className="truncate max-w-xs" style={{ color: "#ff6a3d" }}>
                        {c.hashtags.substring(0, 60)}
                      </span>
                    )}
                  </div>
                </div>

                {c.performance_score !== undefined && c.performance_score > 0 && (
                  <div className="text-right flex-shrink-0">
                    <p className="text-xs" style={{ color: "#475569" }}>Score</p>
                    <p className="font-bold" style={{ color: "#ff6a3d" }}>
                      {(c.performance_score * 100).toFixed(1)}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="py-16 text-center">
            <p className="text-4xl mb-3">✍️</p>
            <p className="font-medium" style={{ color: "var(--text-primary)" }}>No content generated yet</p>
            <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
              Trigger via POST /api/content/generate
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
