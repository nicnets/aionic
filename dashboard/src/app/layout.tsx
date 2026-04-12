import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Aionic — AI Content Intelligence",
  description: "AI trend detection and editorial intelligence dashboard",
};

const navLinks = [
  { href: "/", label: "Overview", icon: "⬡" },
  { href: "/trends", label: "Trends", icon: "↑" },
  { href: "/patterns", label: "Patterns", icon: "◈" },
  { href: "/suggestions", label: "Suggestions", icon: "✦" },
  { href: "/sources", label: "Sources", icon: "◎" },
  { href: "/search", label: "Search", icon: "⌕" },
  { href: "/admin", label: "Admin", icon: "⚙" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <div className="flex min-h-screen">
          {/* Sidebar */}
          <aside className="w-56 shrink-0 border-r border-surface-border flex flex-col">
            <div className="px-5 py-5 border-b border-surface-border">
              <span className="text-sm font-semibold text-slate-100 tracking-wide">
                ⬡ Aionic
              </span>
              <p className="text-xs text-muted mt-0.5">AI Intelligence</p>
            </div>
            <nav className="flex-1 px-3 py-4 space-y-0.5">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-slate-100 hover:bg-surface-hover transition-colors"
                >
                  <span className="text-xs text-muted w-4">{link.icon}</span>
                  {link.label}
                </Link>
              ))}
            </nav>
            <div className="px-5 py-4 border-t border-surface-border">
              <p className="text-xs text-muted">API on :8000</p>
            </div>
          </aside>

          {/* Main content */}
          <main className="flex-1 min-w-0 overflow-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
