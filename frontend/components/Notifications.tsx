"use client";

import { useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";

import { api } from "@/lib/api";
import { relTime } from "@/lib/time";
import type { AuditEntry } from "@/lib/types";

const POLL_MS = 15_000;
const STORAGE_KEY = "dogbuddy_notif_last_seen_id";

// Pretty labels for each audit `action` so users see human text.
const ACTION_LABELS: Record<string, string> = {
  update_status: "Status updated",
  update_activity: "Activity recorded",
  log_incident: "Incident logged",
  register_dog: "Dog registered",
  create_booking: "Booking created",
};

function describe(e: AuditEntry): string {
  const label = ACTION_LABELS[e.action] ?? e.action;
  const target = `${e.target_type} #${e.target_id}`;
  const actor = e.staff_name ?? `user ${e.staff_id}`;
  return `${label} · ${target} · by ${actor}`;
}

export default function Notifications() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [open, setOpen] = useState(false);
  const [lastSeenId, setLastSeenId] = useState<number>(() => {
    if (typeof window === "undefined") return 0;
    return Number(window.localStorage.getItem(STORAGE_KEY) ?? 0) || 0;
  });
  const panelRef = useRef<HTMLDivElement | null>(null);

  // Poll
  useEffect(() => {
    let stopped = false;
    const tick = async () => {
      try {
        const rows = await api.get<AuditEntry[]>("/audit_log/recent");
        if (!stopped) setEntries(rows);
      } catch {
        /* ignore polling failures */
      }
    };
    void tick();
    const id = window.setInterval(tick, POLL_MS);
    return () => {
      stopped = true;
      window.clearInterval(id);
    };
  }, []);

  // Click-outside to close
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [open]);

  const unread = entries.filter((e) => e.id > lastSeenId).length;

  const onOpen = () => {
    setOpen((v) => !v);
    if (!open && entries.length > 0) {
      const top = entries[0].id;
      setLastSeenId(top);
      try {
        window.localStorage.setItem(STORAGE_KEY, String(top));
      } catch {
        /* ignore */
      }
    }
  };

  return (
    <div ref={panelRef} className="relative">
      <button
        onClick={onOpen}
        className="relative rounded-md p-1.5 text-muted transition hover:bg-surface hover:text-text"
        aria-label="Notifications"
        title="Notifications"
      >
        <Bell className="h-4 w-4" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-3.5 min-w-[14px] items-center justify-center rounded-full bg-accent px-1 font-mono text-[9px] font-bold text-bg">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-40 mt-2 w-80 overflow-hidden rounded-lg border border-border bg-surface shadow-xl">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">
              Recent activity
            </p>
            <span className="font-mono text-[10px] text-muted">
              {entries.length}
            </span>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {entries.length === 0 ? (
              <p className="px-3 py-6 text-center text-xs text-muted">
                No activity yet.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {entries.map((e) => (
                  <li key={e.id} className="px-3 py-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm text-text">{describe(e)}</p>
                      <span className="shrink-0 font-mono text-[10px] text-muted">
                        {relTime(e.created_at)}
                      </span>
                    </div>
                    {e.details && (
                      <p className="mt-0.5 truncate font-mono text-[10px] text-muted">
                        {e.details}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
