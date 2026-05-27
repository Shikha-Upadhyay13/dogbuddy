"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2, AlertCircle, CalendarPlus } from "lucide-react";

import AuthGate from "@/components/AuthGate";
import { api, ApiError } from "@/lib/api";
import type { Booking, Dog } from "@/lib/types";

// today's date as YYYY-MM-DD so we can set the <input type=date> min
function todayISO(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function addDaysISO(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function BookStayPage() {
  const router = useRouter();
  const [dogs, setDogs] = useState<Dog[] | null>(null);
  const [loadingDogs, setLoadingDogs] = useState(true);
  const [dogsError, setDogsError] = useState<string | null>(null);

  const [dogId, setDogId] = useState<number | "">("");
  const [start, setStart] = useState(todayISO());
  const [end, setEnd] = useState(addDaysISO(todayISO(), 7));
  const [kennel, setKennel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const d = await api.get<Dog[]>("/dogs/mine");
        setDogs(d);
        if (d.length > 0) setDogId(d[0].id);
      } catch (err) {
        setDogsError(err instanceof ApiError ? err.detail : "Failed to load dogs");
      } finally {
        setLoadingDogs(false);
      }
    })();
  }, []);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy || dogId === "") return;
    if (end < start) {
      setError("End date must be on or after start date.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await api.post<Booking>("/bookings", {
        dog_id: dogId,
        start_date: start,
        end_date: end,
        kennel_id: kennel || null,
      });
      router.replace("/owner/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to book stay");
      setBusy(false);
    }
  };

  const noDogs = !loadingDogs && (dogs?.length ?? 0) === 0;

  return (
    <AuthGate>
      <main className="mx-auto max-w-2xl px-4 pb-24 pt-6 md:px-8 md:pt-10">
        <Link
          href="/owner/dashboard"
          className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted transition hover:text-text"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to dashboard
        </Link>

        <h1 className="text-3xl font-semibold tracking-tight">Book a stay</h1>
        <p className="mt-1 text-sm text-muted">
          Pick a dog and the dates you&apos;ll be away. Staff will check your
          dog in on the start date.
        </p>

        {dogsError && (
          <div className="mt-6 flex items-center gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            <AlertCircle className="h-4 w-4" /> {dogsError}
          </div>
        )}

        {noDogs ? (
          <div className="mt-8 rounded-xl border border-dashed border-border p-8 text-center">
            <CalendarPlus className="mx-auto mb-3 h-8 w-8 text-muted" />
            <p className="text-sm text-text">
              You don&apos;t have any dogs on file yet.
            </p>
            <p className="mt-1 text-sm text-muted">
              Register your dog first, then come back to book a stay.
            </p>
            <Link
              href="/owner/register-dog"
              className="mt-5 inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg shadow shadow-accent/20 transition hover:opacity-90"
            >
              Register a dog
            </Link>
          </div>
        ) : (
          <form
            onSubmit={onSubmit}
            className="mt-8 space-y-5 rounded-xl border border-border bg-surface p-6"
          >
            <Field label="Dog" required>
              <select
                value={dogId}
                onChange={(e) =>
                  setDogId(e.target.value ? parseInt(e.target.value, 10) : "")
                }
                disabled={busy || loadingDogs}
                required
                className={inputCls}
              >
                <option value="" disabled>
                  {loadingDogs ? "Loading..." : "Pick a dog"}
                </option>
                {dogs?.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} · {d.breed}
                  </option>
                ))}
              </select>
            </Field>

            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Start date" required>
                <input
                  type="date"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  min={todayISO()}
                  required
                  disabled={busy}
                  className={inputCls}
                />
              </Field>
              <Field label="End date" required>
                <input
                  type="date"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  min={start}
                  required
                  disabled={busy}
                  className={inputCls}
                />
              </Field>
            </div>

            <Field label="Preferred kennel (optional)">
              <input
                value={kennel}
                onChange={(e) => setKennel(e.target.value)}
                disabled={busy}
                placeholder="K-04"
                className={inputCls}
              />
            </Field>

            {error && (
              <div className="flex items-center gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
                <AlertCircle className="h-4 w-4" /> {error}
              </div>
            )}

            <div className="flex items-center justify-end gap-3">
              <Link
                href="/owner/dashboard"
                className="rounded-md border border-border px-3 py-2 text-sm text-muted transition hover:text-text"
              >
                Cancel
              </Link>
              <button
                type="submit"
                disabled={busy || dogId === ""}
                className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg shadow shadow-accent/20 transition hover:opacity-90 disabled:opacity-50"
              >
                {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                {busy ? "Booking..." : "Confirm booking"}
              </button>
            </div>
          </form>
        )}
      </main>
    </AuthGate>
  );
}

const inputCls =
  "w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none ring-accent/30 transition focus:border-accent focus:ring-2 disabled:opacity-50";

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-text/90">
        {label}
        {required && <span className="ml-0.5 text-danger">*</span>}
      </span>
      {children}
    </label>
  );
}
