"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Dog as DogIcon, Loader2, ArrowRight } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import type { AuthResponse } from "@/lib/types";

// Same hero image as /login -- consistent brand on the public surface.
const HERO_IMG =
  "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?auto=format&fit=crop&w=1400&q=85";

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
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
        "/auth/signup",
        { name, phone, password },
        { skipAuth: true },
      );
      saveAuth(res.token, res.staff);
      // Self-signups are always owners; backend enforces this.
      router.replace("/owner/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 400) {
          setError("That phone is already registered. Try logging in.");
        } else {
          setError(err.detail);
        }
      } else {
        setError("Network error. Is the backend running on :8000?");
      }
      setBusy(false);
    }
  };

  return (
    <main className="grid min-h-screen grid-cols-1 lg:grid-cols-[1.1fr_1fr]">
      {/* Left: hero image */}
      <aside className="relative hidden overflow-hidden lg:block">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={HERO_IMG}
          alt="A dog looking up — calm, attentive."
          className="absolute inset-0 h-full w-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-bg/40 via-bg/55 to-bg/95" />
        <div className="absolute inset-0 bg-gradient-to-r from-transparent to-bg/30" />

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
              Travel with peace of mind.
            </h1>
            <p className="text-lg leading-relaxed text-text/80">
              Register your dog, book a stay for the days you&apos;ll be away,
              and get updates while you&apos;re gone. Our staff handles every
              walk, meal, and medication.
            </p>
            <div className="flex items-center gap-2 text-sm font-medium text-accent">
              Your dog. Our care. Your itinerary.
              <ArrowRight className="h-4 w-4" />
            </div>
          </div>

          <footer className="text-xs text-text/50">
            DogBuddy · Prototype v1 · {new Date().getFullYear()}
          </footer>
        </div>
      </aside>

      {/* Right: signup form */}
      <section className="relative flex items-center justify-center px-6 py-10 sm:px-12">
        <div className="pointer-events-none absolute -top-24 right-0 h-72 w-72 rounded-full bg-accent/10 blur-3xl lg:hidden" />

        <div className="relative w-full max-w-md">
          <div className="mb-10 flex items-center justify-center gap-2 text-accent lg:hidden">
            <DogIcon className="h-7 w-7" />
            <span className="text-2xl font-semibold tracking-tight">
              DogBuddy
            </span>
          </div>

          <div className="mb-8">
            <h2 className="text-3xl font-semibold tracking-tight">
              Create your account
            </h2>
            <p className="mt-2 text-sm text-muted">
              Register as a dog owner — book stays for when you travel.
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="name"
                className="mb-1.5 block text-sm font-medium text-text/90"
              >
                Your name
              </label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 text-text outline-none ring-accent/30 transition focus:border-accent focus:ring-2"
                placeholder="Priya Sharma"
                required
                disabled={busy}
              />
            </div>

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
                autoComplete="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 text-text outline-none ring-accent/30 transition focus:border-accent focus:ring-2"
                placeholder="9876543210"
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
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 text-text outline-none ring-accent/30 transition focus:border-accent focus:ring-2"
                placeholder="At least 6 characters"
                minLength={6}
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
              {busy ? "Creating account..." : "Create account"}
              {!busy && (
                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            Already have an account?{" "}
            <Link
              href="/login"
              className="font-medium text-accent hover:underline"
            >
              Sign in
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
