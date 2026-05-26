"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Loader2,
  AlertCircle,
} from "lucide-react";

import AuthGate from "@/components/AuthGate";
import BottomNav from "@/components/BottomNav";
import DogCard from "@/components/DogCard";
import DogDetailModal from "@/components/DogDetailModal";
import { api, ApiError } from "@/lib/api";
import { clearAuth, getUser } from "@/lib/auth";
import type { BookingsToday, TodayBookingItem } from "@/lib/types";

type SectionKey = "checking_in" | "in_care" | "checking_out";

const SECTION_TITLES: Record<SectionKey, string> = {
  checking_in: "Checking In Today",
  in_care: "In Care",
  checking_out: "Checking Out Today",
};

export default function DashboardPage() {
  const router = useRouter();
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

  const user = getUser();

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

  const onLogout = () => {
    clearAuth();
    router.replace("/login");
  };

  const toggle = (k: SectionKey) => setOpen((o) => ({ ...o, [k]: !o[k] }));

  return (
    <AuthGate>
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-6">
        <header className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Today</h1>
          <div className="flex items-center gap-2 text-sm text-muted">
            <button
              onClick={() => load(true)}
              disabled={refreshing || loading}
              className="rounded p-2 text-muted transition hover:bg-border/40 hover:text-text disabled:opacity-50"
              aria-label="Refresh"
            >
              <RefreshCw
                className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
              />
            </button>
            <span>{user?.name ?? "Staff"}</span>
            <button
              onClick={onLogout}
              className="rounded border border-border px-2 py-1 text-text transition hover:border-accent hover:text-accent"
            >
              Logout
            </button>
          </div>
        </header>

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
          <div className="space-y-6">
            {(Object.keys(SECTION_TITLES) as SectionKey[]).map((key) => {
              const items = data[key];
              const expanded = open[key];
              return (
                <section key={key}>
                  <button
                    onClick={() => toggle(key)}
                    className="mb-2 flex w-full items-center gap-2 text-left"
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
                    <div className="space-y-2">
                      {items.length === 0 ? (
                        <p className="rounded-lg border border-dashed border-border px-3 py-4 text-sm text-muted">
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
