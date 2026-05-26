"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Dog as DogIcon, Loader2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import type { AuthResponse } from "@/lib/types";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      const res = await api.post<AuthResponse>(
        "/auth/login",
        { phone, password },
        { skipAuth: true },
      );
      saveAuth(res.token, res.staff);
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? "Invalid phone or password" : err.detail);
      } else {
        setError("Network error. Is the backend running on :8000?");
      }
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-surface p-8 shadow-xl">
        <div className="mb-6 flex items-center justify-center gap-2 text-accent">
          <DogIcon className="h-7 w-7" />
          <span className="text-2xl font-semibold tracking-tight">DogBuddy</span>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-muted">Phone</label>
            <input
              type="tel"
              autoComplete="username"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-text outline-none focus:border-accent"
              placeholder="9999900001"
              required
              disabled={busy}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-muted">Password</label>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-text outline-none focus:border-accent"
              required
              disabled={busy}
            />
          </div>

          {error && (
            <div className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 font-medium text-bg transition hover:opacity-90 disabled:opacity-50"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {busy ? "Logging in..." : "Log in"}
          </button>
        </form>

        {process.env.NODE_ENV !== "production" && (
          <p className="mt-6 text-center text-xs text-muted">
            Use the seeded account: <span className="text-text">9999900001</span> /{" "}
            <span className="text-text">dogbuddy123</span>
          </p>
        )}
      </div>
    </main>
  );
}
