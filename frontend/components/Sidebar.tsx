"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Radio, Lightbulb, FileText,
  Send, BarChart3, Settings, Zap,
} from "lucide-react";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/signals",   label: "Signals",   icon: Radio },
  { href: "/insights",  label: "Insights",  icon: Lightbulb },
  { href: "/content",   label: "Content",   icon: FileText },
  { href: "/distribution", label: "Distribution", icon: Send },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings",  label: "Settings",  icon: Settings },
];

export default function Sidebar() {
  const path = usePathname();

  return (
    <aside
      className="fixed left-0 top-0 h-screen w-64 flex flex-col z-40 border-r"
      style={{
        background: "var(--surface)",
        borderColor: "var(--border)",
      }}
    >
      {/* Logo */}
      <div className="px-6 py-6 border-b" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center glow-primary-sm"
            style={{ background: "linear-gradient(135deg, #ff6a3d, #ff4a2a)" }}
          >
            <Zap size={16} color="white" strokeWidth={2.5} />
          </div>
          <div>
            <p className="font-bold text-sm leading-none" style={{ color: "var(--text-primary)" }}>
              Phoenix
            </p>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
              Intelligence Engine
            </p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 overflow-y-auto">
        <p className="px-3 mb-3 text-xs font-semibold uppercase tracking-widest" style={{ color: "#475569" }}>
          Pipeline
        </p>
        <ul className="space-y-1">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = path === href || path.startsWith(href + "/");
            return (
              <li key={href}>
                <Link
                  href={href}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200"
                  style={{
                    background: active ? "rgba(255,106,61,0.12)" : "transparent",
                    color: active ? "#ff6a3d" : "var(--text-secondary)",
                    boxShadow: active ? "0 0 12px rgba(255,106,61,0.08)" : "none",
                  }}
                  onMouseEnter={e => {
                    if (!active) (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.04)";
                  }}
                  onMouseLeave={e => {
                    if (!active) (e.currentTarget as HTMLElement).style.background = "transparent";
                  }}
                >
                  <Icon
                    size={17}
                    strokeWidth={active ? 2.5 : 2}
                    color={active ? "#ff6a3d" : "currentColor"}
                  />
                  {label}
                  {active && (
                    <span
                      className="ml-auto w-1.5 h-1.5 rounded-full"
                      style={{ background: "#ff6a3d" }}
                    />
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t text-xs" style={{ borderColor: "var(--border)", color: "#475569" }}>
        <p>Phoenix Solutions</p>
        <p className="mt-0.5">v0.6.0 · AI Marketing</p>
      </div>
    </aside>
  );
}
