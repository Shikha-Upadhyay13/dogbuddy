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

  // We don't know in this snapshot which dogs have meds at all, so this is
  // a rough "no meds recorded recently" signal across in-facility dogs.
  const noMedsRecent = inFacility.filter((b) =>
    isStale(b.last_meds_at, 12),
  ).length;

  const stats = [
    {
      Icon: DogIcon,
      label: "Active bookings",
      value: total,
      tone: "accent",
    },
    {
      Icon: Footprints,
      label: "Need walking",
      value: overdueWalk,
      tone: overdueWalk > 0 ? "warning" : "muted",
    },
    {
      Icon: AlertTriangle,
      label: "Not fed >6h",
      value: overdueFed,
      tone: overdueFed > 0 ? "warning" : "muted",
    },
    {
      Icon: Pill,
      label: "No meds >12h",
      value: noMedsRecent,
      tone: noMedsRecent > 0 ? "warning" : "muted",
    },
  ] as const;

  return (
    <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4">
      {stats.map(({ Icon, label, value, tone }) => (
        <div
          key={label}
          className="rounded-2xl border border-border bg-surface p-4"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wide text-muted">
              {label}
            </span>
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-lg ${
                tone === "accent"
                  ? "bg-accent/10 text-accent"
                  : tone === "warning"
                    ? "bg-warning/10 text-warning"
                    : "bg-border/40 text-muted"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
            </span>
          </div>
          <div className="mt-2 text-2xl font-semibold tracking-tight">
            {value}
          </div>
        </div>
      ))}
    </div>
  );
}
