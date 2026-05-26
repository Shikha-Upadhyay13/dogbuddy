"use client";

import { Dog as DogIcon, Footprints, AlertTriangle, Pill } from "lucide-react";
import type { BookingsToday } from "@/lib/types";

const HOUR = 60 * 60 * 1000;

function isStale(iso: string | null | undefined, hours: number): boolean {
  if (!iso) return true;
  return Date.now() - new Date(iso).getTime() > hours * HOUR;
}

export default function StatsRow({ data }: { data: BookingsToday }) {
  const inFacility = [...data.checking_in, ...data.in_care];
  const total =
    data.checking_in.length + data.in_care.length + data.checking_out.length;
  const overdueWalk = inFacility.filter((b) =>
    isStale(b.last_walked_at, 4),
  ).length;
  const overdueFed = inFacility.filter((b) => isStale(b.last_fed_at, 6)).length;
  const overdueMeds = inFacility.filter((b) =>
    isStale(b.last_meds_at, 12),
  ).length;

  const stats = [
    {
      Icon: DogIcon,
      label: "Active",
      value: total,
      tone: "default" as const,
    },
    {
      Icon: Footprints,
      label: "Walk overdue",
      value: overdueWalk,
      tone: overdueWalk > 0 ? "warn" : "default",
    },
    {
      Icon: AlertTriangle,
      label: "Feed overdue",
      value: overdueFed,
      tone: overdueFed > 0 ? "warn" : "default",
    },
    {
      Icon: Pill,
      label: "Meds overdue",
      value: overdueMeds,
      tone: overdueMeds > 0 ? "warn" : "default",
    },
  ] as const;

  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border md:grid-cols-4">
      {stats.map(({ Icon, label, value, tone }) => (
        <div key={label} className="bg-bg px-4 py-3">
          <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted">
            <Icon
              className={`h-3 w-3 ${tone === "warn" ? "text-warning" : ""}`}
            />
            {label}
          </div>
          <div
            className={`mt-1 font-mono text-2xl font-semibold tabular-nums tracking-tight ${
              tone === "warn" ? "text-warning" : "text-text"
            }`}
          >
            {value}
          </div>
        </div>
      ))}
    </div>
  );
}
