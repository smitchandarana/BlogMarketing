"use client";

import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";

interface EngagementBarProps {
  data: { label: string; value: number }[];
  title: string;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="card-glass px-3 py-2 text-xs">
      <p style={{ color: "var(--text-secondary)" }}>{label}</p>
      <p className="font-semibold mt-0.5" style={{ color: "#ff6a3d" }}>
        {Number(payload[0].value).toFixed(4)}
      </p>
    </div>
  );
};

export function EngagementBar({ data, title }: EngagementBarProps) {
  return (
    <div className="card-glass p-6">
      <p className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "#475569" }}>
        {title}
      </p>
      {data.length === 0 ? (
        <p className="text-sm py-8 text-center" style={{ color: "var(--text-secondary)" }}>
          No data yet
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
            <XAxis
              dataKey="label"
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,106,61,0.05)" }} />
            <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={40}>
              {data.map((_, i) => (
                <Cell key={i} fill={i === 0 ? "#ff6a3d" : "#1e293b"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
