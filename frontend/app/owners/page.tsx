"use client";

import { useEffect, useState } from "react";
import { Users, Phone, PawPrint, Loader2, RefreshCw } from "lucide-react";

import AuthGate from "@/components/AuthGate";
import BottomNav from "@/components/BottomNav";
import Sidebar from "@/components/Sidebar";
import TopNav from "@/components/TopNav";
import { api, ApiError } from "@/lib/api";
import { relTime } from "@/lib/time";
import type { Owner } from "@/lib/types";

export default function OwnersPage() {
  const [owners, setOwners] = useState<Owner[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async (silent = false) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    try {
      const o = await api.get<Owner[]>("/owners");
      setOwners(o);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const withDogs = owners?.filter((o) => o.dog_count > 0).length ?? 0;
  const totalDogs =
    owners?.reduce((sum, o) => sum + o.dog_count, 0) ?? 0;

  return (
    <AuthGate>
      <Sidebar />
      <TopNav />
      <main className="mx-auto max-w-5xl px-4 pb-24 pt-6 md:ml-60 md:max-w-none md:px-10 md:pb-10 md:pt-8">
        <header className="mb-8 flex items-end justify-between gap-4">
          <div>
            <p className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted">
              <Users className="h-3 w-3" />
              Owners
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-text md:text-3xl">
              Owner directory
            </h1>
            <p className="mt-1 text-sm text-muted">
              Customers who signed up via the owner-mode app.
            </p>
          </div>
          <button
            onClick={() => load(true)}
            disabled={refreshing || loading}
            className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-medium text-text transition hover:border-accent hover:text-accent disabled:opacity-50"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
        </header>

        {loading ? (
          <div className="flex items-center gap-2 text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading...
          </div>
        ) : error ? (
          <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        ) : (
          <>
            <div className="mb-6 grid grid-cols-3 gap-px overflow-hidden rounded-lg border border-border bg-border">
              <Stat label="Total owners" value={owners?.length ?? 0} />
              <Stat label="With ≥ 1 dog" value={withDogs} />
              <Stat label="Owner dogs total" value={totalDogs} />
            </div>

            {owners && owners.length > 0 ? (
              <ul className="overflow-hidden rounded-lg border border-border bg-bg">
                {owners.map((o) => (
                  <li
                    key={o.id}
                    className="flex items-center gap-4 border-b border-border px-4 py-3 last:border-0"
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-fuchsia-400 to-violet-600 text-sm font-semibold text-white">
                      {o.name[0]?.toUpperCase() ?? "?"}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-text">
                          {o.name}
                        </span>
                        <span className="inline-flex items-center gap-1 font-mono text-xs text-muted">
                          <Phone className="h-3 w-3" />
                          {o.phone}
                        </span>
                      </div>
                      <p className="mt-0.5 font-mono text-[11px] text-muted">
                        joined {relTime(o.created_at)}
                      </p>
                    </div>
                    <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-text">
                      <PawPrint className="h-3.5 w-3.5" />
                      <span className="font-mono">{o.dog_count}</span>
                      {o.dog_count === 1 ? "dog" : "dogs"}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-muted">
                No owner accounts yet. They appear here as soon as someone
                signs up via /signup.
              </p>
            )}
          </>
        )}
      </main>
      <BottomNav />
    </AuthGate>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-bg px-4 py-3">
      <div className="text-[11px] uppercase tracking-wider text-muted">
        {label}
      </div>
      <div className="mt-1 font-mono text-2xl font-semibold tabular-nums tracking-tight text-text">
        {value}
      </div>
    </div>
  );
}
