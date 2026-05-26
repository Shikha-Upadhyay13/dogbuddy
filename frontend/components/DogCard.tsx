"use client";

import { Footprints, UtensilsCrossed, Pill } from "lucide-react";
import { relTime } from "@/lib/time";
import type { TodayBookingItem } from "@/lib/types";
import StatusBadge from "./StatusBadge";

// Deterministic avatar color from the dog's name.
const AVATAR_COLORS = [
  "bg-rose-500",
  "bg-amber-500",
  "bg-lime-500",
  "bg-emerald-500",
  "bg-cyan-500",
  "bg-indigo-500",
  "bg-fuchsia-500",
  "bg-violet-500",
];
function avatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++)
    hash = (hash * 31 + name.charCodeAt(i)) | 0;
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export default function DogCard({
  item,
  onOpen,
}: {
  item: TodayBookingItem;
  onOpen: () => void;
}) {
  const { dog } = item;

  return (
    <button
      onClick={onOpen}
      className="group flex w-full items-center gap-3 rounded-xl border border-border bg-surface p-4 text-left transition hover:border-accent/60"
    >
      <div
        className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-lg font-semibold text-white ${avatarColor(dog.name)}`}
      >
        {dog.name[0]}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-semibold text-text">{dog.name}</span>
          <StatusBadge status={item.status} />
          {item.kennel_id && (
            <span className="ml-auto text-xs text-muted">{item.kennel_id}</span>
          )}
        </div>
        <div className="mt-0.5 text-sm text-muted">
          {dog.breed} · {dog.age_years}y
        </div>
        <div className="text-xs text-muted">
          {dog.owner_name} · {dog.owner_phone}
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          <span className="inline-flex items-center gap-1">
            <Footprints className="h-3.5 w-3.5" />
            {relTime(item.last_walked_at)}
          </span>
          <span className="inline-flex items-center gap-1">
            <UtensilsCrossed className="h-3.5 w-3.5" />
            {relTime(item.last_fed_at)}
          </span>
          <span className="inline-flex items-center gap-1">
            <Pill className="h-3.5 w-3.5" />
            {relTime(item.last_meds_at)}
          </span>
        </div>
      </div>
    </button>
  );
}
