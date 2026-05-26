"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Loader2,
  AlertCircle,
} from "lucide-react";

import AuthGate from "@/components/AuthGate";
import BottomNav from "@/components/BottomNav";
import TopNav from "@/components/TopNav";
import DogCard from "@/components/DogCard";
import DogDetailModal from "@/components/DogDetailModal";
import StatsRow from "@/components/StatsRow";
import { api, ApiError } from "@/lib/api";
import { getUser } from "@/lib/auth";
import type { BookingsToday, TodayBookingItem } from "@/lib/types";

type SectionKey = "checking_in" | "in_care" | "checking_out";

const SECTION_TITLES: Record<SectionKey, string> = {
  checking_in: "Checking In Today",
  in_care: "In Care",
  checking_out: "Checking Out Today",
};

export default function DashboardPage() {
  const [data, setData] = useState<BookingsToday | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<SectionKey, boolean>>({
    checking_in: true,
    in_care: true,
    checking_out: true,
  });
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

  const toggle = (k: SectionKey) => setOpen((o) => ({ ...o, [k]: !o[k] }));
  const user = getUser();
  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  })();

  return (
    <AuthGate>
      <TopNav />
      <main className="mx-auto max-w-6xl px-4 pb-24 pt-6 md:px-8 md:pt-10">
        <header className="mb-8 flex items-end justify-between gap-4">
          <div>
            <p className="text-sm text-muted">
              {greeting}
              {user?.name ? `, ${user.name}` : ""}.
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight md:text-4xl">
              Today&apos;s shift
            </h1>
          </div>
          <button
            onClick={() => load(true)}
            disabled={refreshing || loading}
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text transition hover:border-accent hover:text-accent disabled:opacity-50"
            aria-label="Refresh"
          >
            <RefreshCw
              className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
        </header>

        {data && <StatsRow data={data} />}

        {loading && (
          <div className="flex items-center gap-2 text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading today...
          </div>
        )}

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            <AlertCircle className="h-4 w-4" /> {error}
          </div>
        )}

        {data && (
          <div className="space-y-8">
            {(Object.keys(SECTION_TITLES) as SectionKey[]).map((key) => {
              const items = data[key];
              const expanded = open[key];
              return (
                <section key={key}>
                  <button
                    onClick={() => toggle(key)}
                    className="mb-3 flex w-full items-center gap-2 text-left"
                  >
                    {expanded ? (
                      <ChevronDown className="h-4 w-4 text-muted" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-muted" />
                    )}
                    <span className="text-sm font-semibold uppercase tracking-wide text-muted">
                      {SECTION_TITLES[key]}
                    </span>
                    <span className="ml-1 rounded-full bg-border/40 px-2 py-0.5 text-xs text-muted">
                      {items.length}
                    </span>
                  </button>
                  {expanded && (
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                      {items.length === 0 ? (
                        <p className="col-span-full rounded-lg border border-dashed border-border px-3 py-6 text-sm text-muted">
                          No dogs in this section right now.
                        </p>
                      ) : (
                        items.map((item) => (
                          <DogCard
                            key={item.booking_id}
                            item={item}
                            onOpen={() => setSelected(item)}
                          />
                        ))
                      )}
                    </div>
                  )}
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
