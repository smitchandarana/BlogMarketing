interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
}

export default function StatCard({ label, value, sub, accent }: StatCardProps) {
  return (
    <div
      className="card-glass p-6"
      style={accent ? { borderColor: "rgba(255,106,61,0.3)" } : {}}
    >
      <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "#475569" }}>
        {label}
      </p>
      <p
        className="text-3xl font-bold leading-none"
        style={{ color: accent ? "#ff6a3d" : "var(--text-primary)" }}
      >
        {value}
      </p>
      {sub && (
        <p className="text-xs mt-2" style={{ color: "var(--text-secondary)" }}>{sub}</p>
      )}
    </div>
  );
}
