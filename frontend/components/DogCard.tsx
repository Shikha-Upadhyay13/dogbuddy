"use client";

import { Footprints, UtensilsCrossed, Pill, ChevronRight } from "lucide-react";
import { relTime } from "@/lib/time";
import type { TodayBookingItem } from "@/lib/types";
import StatusBadge from "./StatusBadge";

// Deterministic gradient avatar so the same dog gets the same colour.
const AVATAR_GRADIENTS = [
  "from-rose-400 to-rose-600",
  "from-amber-400 to-orange-600",
  "from-lime-400 to-emerald-600",
  "from-emerald-400 to-teal-600",
  "from-cyan-400 to-sky-600",
  "from-indigo-400 to-violet-600",
  "from-fuchsia-400 to-pink-600",
  "from-violet-400 to-purple-600",
];
function avatarGradient(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++)
    hash = (hash * 31 + name.charCodeAt(i)) | 0;
  return AVATAR_GRADIENTS[Math.abs(hash) % AVATAR_GRADIENTS.length];
}

// Highlight stale activity so the eye lands on it.
function staleFor(iso: string | null, hours: number): boolean {
  if (!iso) return true;
  return Date.now() - new Date(iso).getTime() > hours * 60 * 60 * 1000;
}

export default function DogCard({
  item,
  onOpen,
}: {
  item: TodayBookingItem;
  onOpen: () => void;
}) {
  const { dog } = item;
  const grad = avatarGradient(dog.name);

  const walkStale = staleFor(item.last_walked_at, 4);
  const fedStale = staleFor(item.last_fed_at, 6);
  const medsStale = !!dog.medications && staleFor(item.last_meds_at, 8);

  return (
    <button
      onClick={onOpen}
      className="group relative flex w-full items-start gap-4 overflow-hidden rounded-2xl border border-border bg-surface p-4 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-accent/60 hover:shadow-lg hover:shadow-accent/5"
    >
      {/* Subtle gradient accent on hover */}
      <div className="pointer-events-none absolute inset-x-0 -top-px h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent opacity-0 transition group-hover:opacity-100" />

      <div
        className={`relative flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br text-xl font-bold text-white shadow-md ${grad}`}
      >
        <span className="drop-shadow-sm">{dog.name[0]}</span>
        {item.kennel_id && (
          <span className="absolute -bottom-1 -right-1 rounded-md border border-border bg-surface px-1 py-0.5 text-[10px] font-medium text-muted">
            {item.kennel_id}
          </span>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0 flex items-center gap-2">
            <span className="truncate text-base font-semibold text-text">
              {dog.name}
            </span>
            <StatusBadge status={item.status} />
          </div>
          <ChevronRight className="h-4 w-4 text-muted transition group-hover:translate-x-0.5 group-hover:text-accent" />
        </div>

        <div className="mt-0.5 truncate text-sm text-muted">
          {dog.breed} · {dog.age_years}y · {dog.weight_kg} kg
        </div>
        <div className="truncate text-xs text-muted">
          {dog.owner_name} · {dog.owner_phone}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <ActivityChip
            Icon={Footprints}
            label="walk"
            when={item.last_walked_at}
            stale={walkStale}
          />
          <ActivityChip
            Icon={UtensilsCrossed}
            label="fed"
            when={item.last_fed_at}
            stale={fedStale}
          />
          {dog.medications ? (
            <ActivityChip
              Icon={Pill}
              label="meds"
              when={item.last_meds_at}
              stale={medsStale}
            />
          ) : null}
        </div>
      </div>
    </button>
  );
}

function ActivityChip({
  Icon,
  label,
  when,
  stale,
}: {
  Icon: typeof Footprints;
  label: string;
  when: string | null;
  stale: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 ${
        stale ? "bg-warning/10 text-warning" : "text-muted"
      }`}
      title={`${label} — ${when ? new Date(when).toLocaleString() : "never"}`}
    >
      <Icon className="h-3.5 w-3.5" />
      {relTime(when)}
    </span>
  );
}
