"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Dog as DogIcon,
  Loader2,
  PawPrint,
  Stethoscope,
  MessageSquareText,
  ShieldCheck,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import type { AuthResponse } from "@/lib/types";

const FEATURES = [
  {
    Icon: PawPrint,
    title: "Today's dogs at a glance",
    body: "Every dog in the facility, grouped by check-in, in-care, and check-out.",
  },
  {
    Icon: MessageSquareText,
    title: "AI copilot in chat",
    body: "Update statuses, log incidents, and look things up by typing or speaking.",
  },
  {
    Icon: Stethoscope,
    title: "Live health research",
    body: "Get cited answers on breed health, behavior, and care from the live web.",
  },
  {
    Icon: ShieldCheck,
    title: "Safety guardrails",
    body: "DogBuddy never gives medication doses — it always defers to your vet.",
  },
];

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
    <main className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
      {/* Left: brand panel */}
      <aside className="relative hidden overflow-hidden lg:flex lg:flex-col lg:justify-between bg-gradient-to-br from-accent/20 via-bg to-bg p-12">
        {/* Soft accent blob */}
        <div className="pointer-events-none absolute -top-32 -left-32 h-96 w-96 rounded-full bg-accent/30 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 right-0 h-72 w-72 rounded-full bg-accent/10 blur-3xl" />

        <header className="relative flex items-center gap-3 text-accent">
          <DogIcon className="h-9 w-9" />
          <span className="text-2xl font-semibold tracking-tight">
            DogBuddy
          </span>
        </header>

        <div className="relative max-w-md space-y-8">
          <div>
            <h1 className="text-4xl font-semibold leading-tight tracking-tight text-text">
              The senior colleague every dog boarding facility needs.
            </h1>
            <p className="mt-4 text-base text-muted">
              Track every dog, log every incident, and get instant answers — by
              chat or by voice. Built for staff on the kennel floor.
            </p>
          </div>

          <ul className="space-y-4">
            {FEATURES.map(({ Icon, title, body }) => (
              <li key={title} className="flex gap-3">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-accent">
                  <Icon className="h-4 w-4" />
                </span>
                <div>
                  <p className="font-medium text-text">{title}</p>
                  <p className="text-sm text-muted">{body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <footer className="relative text-xs text-muted">
          Prototype · v1 · {new Date().getFullYear()}
        </footer>
      </aside>

      {/* Right: form */}
      <section className="flex items-center justify-center px-6 py-10 sm:px-12">
        <div className="w-full max-w-sm">
          {/* Mobile-only logo (hidden on lg where the left panel shows it) */}
          <div className="mb-8 flex items-center justify-center gap-2 text-accent lg:hidden">
            <DogIcon className="h-7 w-7" />
            <span className="text-2xl font-semibold tracking-tight">
              DogBuddy
            </span>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-semibold tracking-tight">
              Welcome back
            </h2>
            <p className="mt-1 text-sm text-muted">
              Sign in with your staff credentials to continue.
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label htmlFor="phone" className="mb-1 block text-sm text-muted">
                Phone
              </label>
              <input
                id="phone"
                type="tel"
                autoComplete="username"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text outline-none transition focus:border-accent"
                placeholder="9999900001"
                required
                disabled={busy}
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1 block text-sm text-muted"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text outline-none transition focus:border-accent"
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
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 font-medium text-bg transition hover:opacity-90 disabled:opacity-50"
            >
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              {busy ? "Logging in..." : "Log in"}
            </button>
          </form>

          {process.env.NODE_ENV !== "production" && (
            <div className="mt-8 rounded-lg border border-border bg-surface/60 p-3 text-xs text-muted">
              <p className="mb-1 font-medium text-text">Dev login</p>
              Phone <span className="font-mono text-text">9999900001</span> ·
              Password <span className="font-mono text-text">dogbuddy123</span>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
