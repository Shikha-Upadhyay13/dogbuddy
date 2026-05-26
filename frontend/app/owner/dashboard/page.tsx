"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Dog as DogIcon,
  Plus,
  CalendarPlus,
  LogOut,
  MessageSquare,
  Loader2,
  AlertCircle,
} from "lucide-react";

import AuthGate from "@/components/AuthGate";
import { api, ApiError } from "@/lib/api";
import { clearAuth, getUser } from "@/lib/auth";
import type { Booking, Dog } from "@/lib/types";

export default function OwnerDashboardPage() {
  const router = useRouter();
  const [user] = useState(() => getUser());

  const [dogs, setDogs] = useState<Dog[] | null>(null);
  const [bookings, setBookings] = useState<Booking[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [d, b] = await Promise.all([
          api.get<Dog[]>("/dogs/mine"),
          api.get<Booking[]>("/bookings/mine"),
        ]);
        setDogs(d);
        setBookings(b);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const onLogout = () => {
    clearAuth();
    router.replace("/login");
  };

  return (
    <AuthGate>
      <main className="mx-auto max-w-4xl px-4 pb-24 pt-6 md:px-8 md:pt-10">
        {/* Header */}
        <header className="mb-10 flex items-end justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2 text-accent">
              <DogIcon className="h-5 w-5" />
              <span className="font-mono text-[11px] uppercase tracking-wider">
                Owner mode
              </span>
            </div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
              Hi, {user?.name?.split(" ")[0] ?? "there"}
            </h1>
            <p className="mt-1 text-sm text-muted">
              Manage your dogs and book stays for when you&apos;re away.
            </p>
          </div>
          <button
            onClick={onLogout}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-sm text-text transition hover:border-accent hover:text-accent"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </header>

        {error && (
          <div className="mb-6 flex items-center gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            <AlertCircle className="h-4 w-4" /> {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center gap-2 text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading...
          </div>
        ) : (
          <div className="space-y-8">
            {/* My dogs */}
            <section>
              <div className="mb-3 flex items-baseline justify-between">
                <div className="flex items-baseline gap-2">
                  <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
                    My dogs
                  </h2>
                  <span className="font-mono text-xs text-muted">
                    {String(dogs?.length ?? 0).padStart(2, "0")}
                  </span>
                </div>
                <button
                  disabled
                  title="Coming next: register-a-dog form"
                  className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-muted opacity-60"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Register a dog
                </button>
              </div>

              {dogs && dogs.length > 0 ? (
                <ul className="overflow-hidden rounded-lg border border-border bg-bg">
                  {dogs.map((d) => (
                    <li
                      key={d.id}
                      className="flex items-center gap-4 border-b border-border px-4 py-3 last:border-0"
                    >
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-cyan-400 to-sky-600 text-sm font-semibold text-white">
                        {d.name[0]}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-semibold text-text">
                          {d.name}
                        </div>
                        <div className="text-xs text-muted">
                          {d.breed} · {d.age_years}y · {d.weight_kg}kg
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-muted">
                  No dogs registered yet. Register your first dog to start
                  booking stays.
                </p>
              )}
            </section>

            {/* My bookings */}
            <section>
              <div className="mb-3 flex items-baseline justify-between">
                <div className="flex items-baseline gap-2">
                  <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
                    My bookings
                  </h2>
                  <span className="font-mono text-xs text-muted">
                    {String(bookings?.length ?? 0).padStart(2, "0")}
                  </span>
                </div>
                <button
                  disabled
                  title="Coming next: book-a-stay form"
                  className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-muted opacity-60"
                >
                  <CalendarPlus className="h-3.5 w-3.5" />
                  Book a stay
                </button>
              </div>

              {bookings && bookings.length > 0 ? (
                <ul className="overflow-hidden rounded-lg border border-border bg-bg">
                  {bookings.map((b) => (
                    <li
                      key={b.id}
                      className="flex items-center justify-between gap-4 border-b border-border px-4 py-3 font-mono text-xs last:border-0"
                    >
                      <span>
                        Booking #{b.id}{" "}
                        <span className="text-muted">· dog #{b.dog_id}</span>
                      </span>
                      <span className="text-muted">
                        {b.start_date} → {b.end_date}
                      </span>
                      <span className="rounded border border-border bg-surface px-1.5 py-0.5 text-text">
                        {b.status}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-muted">
                  No bookings yet. Pick a dog and pick your travel dates.
                </p>
              )}
            </section>

            {/* Chat call-to-action */}
            <section className="rounded-xl border border-border bg-surface p-5">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent/10 text-accent">
                  <MessageSquare className="h-4 w-4" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-text">
                    Need to ask something?
                  </p>
                  <p className="mt-0.5 text-xs text-muted">
                    Chat with DogBuddy — questions about your booking, what to
                    pack, general care advice. (Owner-mode chat coming soon.)
                  </p>
                </div>
              </div>
            </section>
          </div>
        )}
      </main>
    </AuthGate>
  );
}
