"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Loader2, AlertCircle } from "lucide-react";

import AuthGate from "@/components/AuthGate";
import BottomNav from "@/components/BottomNav";
import Sidebar from "@/components/Sidebar";
import TopNav from "@/components/TopNav";
import DogCard from "@/components/DogCard";
import DogDetailModal from "@/components/DogDetailModal";
import StatsRow from "@/components/StatsRow";
import { api, ApiError } from "@/lib/api";
import type { BookingsToday, TodayBookingItem } from "@/lib/types";

type SectionKey = "checking_in" | "in_care" | "checking_out";

const SECTION_TITLES: Record<SectionKey, string> = {
  checking_in: "Checking In",
  in_care: "In Care",
  checking_out: "Checking Out",
};

export default function DashboardPage() {
  const [data, setData] = useState<BookingsToday | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<TodayBookingItem | null>(null);

  const load = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    try {
      const d = await api.get<BookingsToday>("/bookings/today");
      setData(d);
      setError(null);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "Could not load today's bookings",
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });

  return (
    <AuthGate>
      <Sidebar />
      <TopNav />
      <main className="mx-auto max-w-5xl px-4 pb-24 pt-6 md:ml-60 md:max-w-none md:px-10 md:pb-10 md:pt-8">
        {/* Header */}
        <div className="mb-8 flex items-end justify-between gap-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-wider text-muted">
              {today}
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-text md:text-3xl">
              Today&apos;s shift
            </h1>
          </div>
          <button
            onClick={() => load(true)}
            disabled={refreshing || loading}
            className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-medium text-text transition hover:border-accent hover:text-accent disabled:opacity-50"
            aria-label="Refresh"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
        </div>

        {data && (
          <div className="mb-10">
            <StatsRow data={data} />
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading...
          </div>
        )}

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            <AlertCircle className="h-4 w-4" /> {error}
          </div>
        )}

        {data && (
          <div className="space-y-10">
            {(Object.keys(SECTION_TITLES) as SectionKey[]).map((key) => {
              const items = data[key];
              return (
                <section key={key}>
                  {/* Section header */}
                  <div className="mb-3 flex items-baseline gap-2">
                    <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
                      {SECTION_TITLES[key]}
                    </h2>
                    <span className="font-mono text-xs text-muted">
                      {String(items.length).padStart(2, "0")}
                    </span>
                    <div className="ml-3 h-px flex-1 bg-border" />
                  </div>

                  {/* List */}
                  <div className="overflow-hidden rounded-lg border border-border bg-bg">
                    {items.length === 0 ? (
                      <p className="px-4 py-6 text-sm text-muted">
                        No dogs in this section right now.
                      </p>
                    ) : (
                      items.map((item, i) => (
                        <DogCard
                          key={item.booking_id}
                          item={item}
                          onOpen={() => setSelected(item)}
                          // hide last border on final row
                          {...(i === items.length - 1 ? {} : {})}
                        />
                      ))
                    )}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </main>

      <BottomNav />

      {selected && (
        <DogDetailModal
          item={selected}
          onClose={() => setSelected(null)}
          onAction={() => load(true)}
        />
      )}
    </AuthGate>
  );
}
