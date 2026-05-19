"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setError(data.error || "Login failed");
        return;
      }
      router.push("/dashboard");
      router.refresh();
    } catch {
      setError("Unable to login");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen grid place-items-center p-6">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-4"
      >
        <h1 className="text-2xl font-semibold">Planitt Admin Login</h1>
        <p className="text-sm text-slate-400">Authenticate to access operations console.</p>
        <div className="space-y-1">
          <label className="text-xs text-slate-400">Username</label>
          <input
            className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 outline-none focus:border-indigo-500"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-slate-400">Password</label>
          <input
            type="password"
            className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 outline-none focus:border-indigo-500"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>
        {error ? <p className="text-sm text-red-400">{error}</p> : null}
        <button
          disabled={loading}
          className="w-full rounded-md bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 px-4 py-2 font-medium"
        >
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </main>
  );
}

