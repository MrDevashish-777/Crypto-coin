"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

const nav = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/signals", label: "Signals" },
  { href: "/dashboard/generation", label: "Generation" },
  { href: "/dashboard/news", label: "News" },
  { href: "/dashboard/ops", label: "Ops" },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-[220px_1fr]">
      <aside className="border-r border-slate-800 bg-slate-900 p-4 space-y-4">
        <div>
          <h2 className="text-lg font-bold">Planitt Admin</h2>
          <p className="text-xs text-slate-400">Operations Console</p>
        </div>
        <nav className="space-y-1">
          {nav.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-md px-3 py-2 text-sm ${
                  active ? "bg-indigo-600 text-white" : "text-slate-300 hover:bg-slate-800"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <button
          onClick={logout}
          className="w-full rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
        >
          Logout
        </button>
      </aside>
      <section className="p-6">{children}</section>
    </div>
  );
}

