"use client";

import { useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";

import { api } from "@/lib/api";
import { relTime } from "@/lib/time";

type Note = {
  id: number;
  type: string;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
};

const POLL_MS = 15_000;

export default function Notifications() {
  const [entries, setEntries] = useState<Note[]>([]);
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let stopped = false;
    const tick = async () => {
      try {
        const rows = await api.get<Note[]>("/notifications");
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

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [open]);

  const unread = entries.filter((e) => !e.read_at).length;

  const onOpen = () => {
    setOpen((v) => !v);
    if (!open) {
      for (const entry of entries.filter((e) => !e.read_at)) {
        void api.post(`/notifications/${entry.id}/read`, {}).then(() => {
          setEntries((prev) =>
            prev.map((row) =>
              row.id === entry.id
                ? { ...row, read_at: new Date().toISOString() }
                : row,
            ),
          );
        });
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
        <div className="absolute right-0 top-full z-40 mt-2 w-80 overflow-hidden rounded-lg border border-border bg-surface">
          <div className="border-b border-border px-3 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">
              Notifications
            </p>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {entries.length === 0 ? (
              <p className="px-3 py-6 text-center text-xs text-muted">
                Nothing new.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {entries.map((e) => (
                  <li key={e.id} className="px-3 py-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm text-text">{e.title}</p>
                      <span className="shrink-0 font-mono text-[10px] text-muted">
                        {relTime(e.created_at)}
                      </span>
                    </div>
                    <p className="mt-0.5 line-clamp-3 text-xs text-muted">{e.body}</p>
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
