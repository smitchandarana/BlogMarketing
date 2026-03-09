const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  draft:      { bg: "rgba(100,116,139,0.15)", text: "#94a3b8" },
  queued:     { bg: "rgba(100,116,139,0.15)", text: "#94a3b8" },
  new:        { bg: "rgba(59,130,246,0.15)",  text: "#60a5fa" },
  scheduled:  { bg: "rgba(234,179,8,0.15)",   text: "#facc15" },
  processing: { bg: "rgba(234,179,8,0.15)",   text: "#facc15" },
  published:  { bg: "rgba(34,197,94,0.15)",   text: "#4ade80" },
  used:       { bg: "rgba(34,197,94,0.15)",   text: "#4ade80" },
  approved:   { bg: "rgba(34,197,94,0.15)",   text: "#4ade80" },
  failed:     { bg: "rgba(239,68,68,0.15)",   text: "#f87171" },
  linkedin:   { bg: "rgba(10,102,194,0.15)",  text: "#60a5fa" },
  website:    { bg: "rgba(255,106,61,0.15)",  text: "#ff6a3d" },
};

export default function Badge({ label }: { label: string }) {
  const style = STATUS_COLORS[label.toLowerCase()] ?? { bg: "rgba(100,116,139,0.15)", text: "#94a3b8" };
  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize"
      style={{ background: style.bg, color: style.text }}
    >
      {label}
    </span>
  );
}
