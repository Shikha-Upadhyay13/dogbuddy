"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Stethoscope,
  AlertTriangle,
  ShieldCheck,
  Pill,
  Loader2,
  ArrowRight,
} from "lucide-react";

import AuthGate from "@/components/AuthGate";
import BottomNav from "@/components/BottomNav";
import Sidebar from "@/components/Sidebar";
import TopNav from "@/components/TopNav";
import { api, ApiError } from "@/lib/api";
import { threadIdFor } from "@/lib/chats";
import { getUser } from "@/lib/auth";
import type { Dog, Incident } from "@/lib/types";

type DogWithSignals = {
  dog: Dog;
  vaccUrgency: 0 | 1 | 2; // 0 = ok, 1 = expiring_soon, 2 = expired
  recentHealthIncidents: Incident[];
};

function computeUrgency(d: Dog): 0 | 1 | 2 {
  if (d.vaccination_status === "expired") return 2;
  if (d.vaccination_status === "expiring_soon") return 1;
  return 0;
}

export default function HealthPage() {
  const router = useRouter();
  const [user] = useState(() => getUser());
  const [rows, setRows] = useState<DogWithSignals[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [dogs, incidents] = await Promise.all([
          api.get<Dog[]>("/dogs"),
          api.get<Incident[]>("/incidents/recent"),
        ]);
        const byDog: Record<number, Incident[]> = {};
        for (const i of incidents) {
          if (i.type !== "health") continue;
          (byDog[i.dog_id] ||= []).push(i);
        }
        const merged: DogWithSignals[] = dogs.map((d) => ({
          dog: d,
          vaccUrgency: computeUrgency(d),
          recentHealthIncidents: byDog[d.id] || [],
        }));
        // Sort: expired first, then expiring_soon, then dogs with health incidents.
        merged.sort((a, b) => {
          const score = (r: DogWithSignals) =>
            r.vaccUrgency * 100 + r.recentHealthIncidents.length;
          return score(b) - score(a);
        });
        setRows(merged);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Helper to deep-link into the chat with a prefilled prompt.
  const askAdvisor = (dogName: string) => {
    if (!user) return;
    const id = threadIdFor(user.id, String(Date.now()));
    const q = encodeURIComponent(
      `Ask the health advisor about ${dogName}: any breed-specific risks, vaccination concerns, or general care notes.`,
    );
    router.push(`/chat?thread=${encodeURIComponent(id)}&q=${q}`);
  };

  const totalDogs = rows?.length ?? 0;
  const expiredCount = rows?.filter((r) => r.vaccUrgency === 2).length ?? 0;
  const expiringCount = rows?.filter((r) => r.vaccUrgency === 1).length ?? 0;
  const withIncidents =
    rows?.filter((r) => r.recentHealthIncidents.length > 0).length ?? 0;
  const onMeds = rows?.filter((r) => !!r.dog.medications).length ?? 0;

  return (
    <AuthGate>
      <Sidebar />
      <TopNav />
      <main className="mx-auto max-w-5xl px-4 pb-24 pt-6 md:ml-60 md:max-w-none md:px-10 md:pb-10 md:pt-8">
        <header className="mb-8 flex items-end justify-between gap-4">
          <div>
            <p className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted">
              <Stethoscope className="h-3 w-3" />
              Health
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-text md:text-3xl">
              Care signals
            </h1>
            <p className="mt-1 text-sm text-muted">
              Dogs that may need attention — vaccination concerns, recent
              health incidents, or active medications.
            </p>
          </div>
        </header>

        {loading ? (
          <div className="flex items-center gap-2 text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading...
          </div>
        ) : error ? (
          <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        ) : (
          <>
            {/* Stat row */}
            <div className="mb-10 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border md:grid-cols-4">
              <Stat
                Icon={ShieldCheck}
                label="Total dogs"
                value={totalDogs}
                tone="default"
              />
              <Stat
                Icon={AlertTriangle}
                label="Vacc expired"
                value={expiredCount}
                tone={expiredCount > 0 ? "danger" : "default"}
              />
              <Stat
                Icon={AlertTriangle}
                label="Vacc expiring"
                value={expiringCount}
                tone={expiringCount > 0 ? "warn" : "default"}
              />
              <Stat
                Icon={Pill}
                label="On meds"
                value={onMeds}
                tone="default"
              />
            </div>

            {/* Dog list */}
            {rows && rows.length > 0 ? (
              <ul className="overflow-hidden rounded-lg border border-border bg-bg">
                {rows.map((r) => (
                  <li
                    key={r.dog.id}
                    className="flex items-center gap-4 border-b border-border px-4 py-3 last:border-0"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-cyan-400 to-sky-600 text-sm font-semibold text-white">
                      {r.dog.name[0]}
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-text">
                          {r.dog.name}
                        </span>
                        <span className="text-xs text-muted">
                          {r.dog.breed} · {r.dog.age_years}y
                        </span>
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                        <VaccPill
                          status={r.dog.vaccination_status}
                          expires={r.dog.vaccination_expires}
                        />
                        {r.dog.medications && (
                          <span className="inline-flex items-center gap-1 text-muted">
                            <Pill className="h-3 w-3" />
                            <span className="font-mono">
                              {r.dog.medications}
                            </span>
                          </span>
                        )}
                        {r.recentHealthIncidents.length > 0 && (
                          <span className="inline-flex items-center gap-1 text-warning">
                            <AlertTriangle className="h-3 w-3" />
                            {r.recentHealthIncidents.length} recent health
                            incident
                            {r.recentHealthIncidents.length === 1 ? "" : "s"}
                          </span>
                        )}
                      </div>
                    </div>

                    <button
                      onClick={() => askAdvisor(r.dog.name)}
                      className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs text-text transition hover:border-accent hover:text-accent"
                      title="Open chat with a prefilled health-advisor prompt"
                    >
                      <Stethoscope className="h-3.5 w-3.5" />
                      Ask Health Advisor
                      <ArrowRight className="h-3 w-3" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-muted">
                No dogs in the system yet.
              </p>
            )}
          </>
        )}
      </main>
      <BottomNav />
    </AuthGate>
  );
}

function Stat({
  Icon,
  label,
  value,
  tone,
}: {
  Icon: typeof Stethoscope;
  label: string;
  value: number;
  tone: "default" | "warn" | "danger";
}) {
  return (
    <div className="bg-bg px-4 py-3">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted">
        <Icon className="h-3 w-3" />
        {label}
      </div>
      <div
        className={`mt-1 font-mono text-2xl font-semibold tabular-nums tracking-tight ${
          tone === "danger"
            ? "text-danger"
            : tone === "warn"
              ? "text-warning"
              : "text-text"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function VaccPill({
  status,
  expires,
}: {
  status: string;
  expires: string | null;
}) {
  const map: Record<string, { label: string; cls: string }> = {
    up_to_date: {
      label: "Vacc up to date",
      cls: "text-success",
    },
    expiring_soon: {
      label: `Vacc expiring${expires ? ` (${expires})` : ""}`,
      cls: "text-warning",
    },
    expired: {
      label: `Vacc EXPIRED${expires ? ` (${expires})` : ""}`,
      cls: "text-danger",
    },
  };
  const v = map[status] ?? { label: status, cls: "text-muted" };
  return (
    <span className={`inline-flex items-center gap-1 ${v.cls}`}>
      <ShieldCheck className="h-3 w-3" />
      {v.label}
    </span>
  );
}
