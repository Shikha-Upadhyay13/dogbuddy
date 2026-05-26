"use client";

import { Footprints, UtensilsCrossed, Pill, ChevronRight } from "lucide-react";
import { relTime } from "@/lib/time";
import type { TodayBookingItem } from "@/lib/types";

const STATUS_DOT: Record<string, string> = {
  scheduled: "bg-accent",
  checked_in: "bg-warning",
  in_care: "bg-success",
  checked_out: "bg-muted",
};
const STATUS_LABEL: Record<string, string> = {
  scheduled: "Scheduled",
  checked_in: "Checked In",
  in_care: "In Care",
  checked_out: "Checked Out",
};

// Deterministic gradient avatar.
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
      className="group flex w-full items-center gap-4 border-b border-border bg-bg px-4 py-3 text-left transition hover:bg-surface/50"
    >
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-gradient-to-br text-sm font-semibold text-white ${grad}`}
      >
        {dog.name[0]}
      </div>

      {/* Name + status + breed */}
      <div className="min-w-0 flex-1 md:flex-none md:basis-52">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-semibold text-text">
            {dog.name}
          </span>
          <span className="inline-flex items-center gap-1.5 text-xs text-muted">
            <span
              className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[item.status] ?? "bg-muted"}`}
            />
            {STATUS_LABEL[item.status] ?? item.status}
          </span>
        </div>
        <div className="mt-0.5 truncate text-xs text-muted">
          {dog.breed} · {dog.age_years}y · {dog.weight_kg}kg
        </div>
      </div>

      {/* Kennel + owner */}
      <div className="hidden min-w-0 md:flex md:basis-56 md:flex-col">
        <span className="font-mono text-xs text-text">
          {item.kennel_id ?? "—"}
        </span>
        <span className="truncate text-xs text-muted">
          {dog.owner_name} ·{" "}
          <span className="font-mono">{dog.owner_phone}</span>
        </span>
      </div>

      {/* Activity */}
      <div className="ml-auto hidden items-center gap-4 md:flex">
        <ActivityChip
          Icon={Footprints}
          when={item.last_walked_at}
          stale={walkStale}
          tip="Walk"
        />
        <ActivityChip
          Icon={UtensilsCrossed}
          when={item.last_fed_at}
          stale={fedStale}
          tip="Fed"
        />
        {dog.medications ? (
          <ActivityChip
            Icon={Pill}
            when={item.last_meds_at}
            stale={medsStale}
            tip="Meds"
          />
        ) : (
          <span className="w-12" />
        )}
      </div>

      <ChevronRight className="h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-0.5 group-hover:text-text" />
    </button>
  );
}

function ActivityChip({
  Icon,
  when,
  stale,
  tip,
}: {
  Icon: typeof Footprints;
  when: string | null;
  stale: boolean;
  tip: string;
}) {
  return (
    <span
      className={`inline-flex w-20 items-center gap-1.5 font-mono text-[11px] tracking-tight ${
        stale ? "text-warning" : "text-muted"
      }`}
      title={`${tip} · ${when ? new Date(when).toLocaleString() : "never"}`}
    >
      <Icon className="h-3.5 w-3.5" />
      {relTime(when)}
    </span>
  );
}
