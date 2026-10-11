"use client";

import { useCallback, useEffect, useState } from "react";

import AuthGate from "@/components/AuthGate";
import Sidebar from "@/components/Sidebar";
import TopNav from "@/components/TopNav";
import StatusBadge from "@/components/StatusBadge";
import { api, ApiError } from "@/lib/api";
import type { Booking } from "@/lib/types";

type QueueItem = {
  booking: Booking;
  dog_name: string;
  owner_name: string;
};

export default function QueuePage() {
  const [rows, setRows] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await api.get<QueueItem[]>("/bookings/queue"));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load the queue");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const decide = async (id: number, action: string) => {
    setError(null);
    try {
      await api.post(`/bookings/${id}/decision`, { action });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not update the request");
    }
  };

  return (
    <AuthGate>
      <Sidebar />
      <TopNav />
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-6 md:ml-60 md:px-10">
        <h1 className="text-2xl font-semibold tracking-tight">Booking queue</h1>
        <p className="mt-1 text-sm text-muted">
          Requests waiting for a decision. Accepting a full day moves the stay to the waitlist.
        </p>
        {error && <p className="mt-4 text-sm text-danger">{error}</p>}
        <ul className="mt-6 space-y-3">
          {(rows ?? []).map((row) => (
            <li
              key={row.booking.id}
              className="rounded-lg border border-border bg-surface p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium">
                    {row.dog_name}{" "}
                    <span className="text-muted">· {row.owner_name}</span>
                  </p>
                  <p className="text-sm text-muted">
                    {row.booking.start_date} → {row.booking.end_date}
                  </p>
                </div>
                <StatusBadge status={row.booking.status} />
              </div>
              {row.booking.status !== "awaiting_payment" && (
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => decide(row.booking.id, "accept")}
                    className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-bg"
                  >
                    Accept
                  </button>
                  <button
                    onClick={() => decide(row.booking.id, "waitlist")}
                    className="rounded-md border border-border px-3 py-1.5 text-sm"
                  >
                    Waitlist
                  </button>
                  <button
                    onClick={() => decide(row.booking.id, "decline")}
                    className="rounded-md border border-border px-3 py-1.5 text-sm text-danger"
                  >
                    Decline
                  </button>
                </div>
              )}
            </li>
          ))}
          {rows && rows.length === 0 && (
            <li className="text-sm text-muted">No open requests.</li>
          )}
        </ul>
      </main>
    </AuthGate>
  );
}
