import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Phoenix Marketing Intelligence Engine",
  description: "AI-powered marketing automation dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased flex min-h-screen" style={{ background: "var(--bg)" }}>
        <Sidebar />
        <main className="flex-1 ml-64 min-h-screen p-8" style={{ background: "var(--bg)" }}>
          {children}
        </main>
      </body>
    </html>
  );
}
