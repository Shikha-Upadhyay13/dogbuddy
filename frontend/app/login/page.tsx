"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Dog as DogIcon, Loader2, ArrowRight } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import type { AuthResponse } from "@/lib/types";

// Stable Unsplash hot-link (no API key required). A warm portrait of a
// golden retriever — sets the emotional tone for a dog-boarding product.
const HERO_IMG =
  "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?auto=format&fit=crop&w=1400&q=85";

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
    <main className="grid min-h-screen grid-cols-1 lg:grid-cols-[1.1fr_1fr]">
      {/* Left: hero image with overlay */}
      <aside className="relative hidden overflow-hidden lg:block">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={HERO_IMG}
          alt="A dog looking up — calm, attentive."
          className="absolute inset-0 h-full w-full object-cover"
        />
        {/* Top-to-bottom darkening + tinted overlay for legibility */}
        <div className="absolute inset-0 bg-gradient-to-b from-bg/40 via-bg/55 to-bg/95" />
        <div className="absolute inset-0 bg-gradient-to-r from-transparent to-bg/30" />

        {/* Content */}
        <div className="relative flex h-full flex-col justify-between p-12 xl:p-16">
          <header className="flex items-center gap-3 text-text">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-text/15 bg-bg/40 text-accent backdrop-blur">
              <DogIcon className="h-5 w-5" />
            </span>
            <span className="text-xl font-semibold tracking-tight">
              DogBuddy
            </span>
          </header>

          <div className="max-w-xl space-y-6">
            <h1 className="text-5xl font-semibold leading-[1.05] tracking-tight text-text xl:text-6xl">
              Every dog.
              <br />
              Every detail.
              <br />
              <span className="text-accent">Every shift.</span>
            </h1>
            <p className="text-lg leading-relaxed text-text/80">
              DogBuddy is the senior colleague on every shift — tracking every
              dog, logging every incident, and answering questions about care,
              breeds, and behavior in seconds.
            </p>
            <div className="flex items-center gap-2 text-sm font-medium text-accent">
              Built for the kennel floor, not the office desk.
              <ArrowRight className="h-4 w-4" />
            </div>
          </div>

          <footer className="text-xs text-text/50">
            DogBuddy · Prototype v1 · {new Date().getFullYear()}
          </footer>
        </div>
      </aside>

      {/* Right: form */}
      <section className="relative flex items-center justify-center px-6 py-10 sm:px-12">
        {/* Subtle accent behind the form on mobile too */}
        <div className="pointer-events-none absolute -top-24 right-0 h-72 w-72 rounded-full bg-accent/10 blur-3xl lg:hidden" />

        <div className="relative w-full max-w-md">
          {/* Mobile brand */}
          <div className="mb-10 flex items-center justify-center gap-2 text-accent lg:hidden">
            <DogIcon className="h-7 w-7" />
            <span className="text-2xl font-semibold tracking-tight">
              DogBuddy
            </span>
          </div>

          <div className="mb-8">
            <h2 className="text-3xl font-semibold tracking-tight">Sign in</h2>
            <p className="mt-2 text-sm text-muted">
              Welcome back. Continue managing today&apos;s shift.
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="phone"
                className="mb-1.5 block text-sm font-medium text-text/90"
              >
                Phone
              </label>
              <input
                id="phone"
                type="tel"
                autoComplete="username"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 text-text outline-none ring-accent/30 transition focus:border-accent focus:ring-2"
                placeholder="9999900001"
                required
                disabled={busy}
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block text-sm font-medium text-text/90"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 text-text outline-none ring-accent/30 transition focus:border-accent focus:ring-2"
                required
                disabled={busy}
              />
            </div>

            {error && (
              <div className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2.5 text-sm text-danger">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="group flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-3 font-semibold text-bg shadow-lg shadow-accent/20 transition hover:opacity-90 disabled:opacity-50"
            >
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              {busy ? "Signing in..." : "Sign in"}
              {!busy && (
                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
              )}
            </button>
          </form>

          {process.env.NODE_ENV !== "production" && (
            <div className="mt-10 rounded-xl border border-border bg-surface/60 p-4 text-xs text-muted">
              <p className="mb-2 font-semibold uppercase tracking-wider text-text/80">
                Dev login
              </p>
              <div className="flex flex-col gap-1 font-mono text-text">
                <span>
                  <span className="text-muted">phone </span>9999900001
                </span>
                <span>
                  <span className="text-muted">pass </span>dogbuddy123
                </span>
              </div>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
