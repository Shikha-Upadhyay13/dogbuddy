"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Filter,
  Loader2,
  RefreshCw,
} from "lucide-react";

import AuthGate from "@/components/AuthGate";
import BottomNav from "@/components/BottomNav";
import Sidebar from "@/components/Sidebar";
import TopNav from "@/components/TopNav";
import { api, ApiError } from "@/lib/api";
import { relTime } from "@/lib/time";
import type { Dog, Incident } from "@/lib/types";

const SEVERITY_STYLE: Record<string, string> = {
  mild: "border-border bg-bg text-muted",
  moderate: "border-warning/40 bg-warning/10 text-warning",
  severe: "border-danger/40 bg-danger/10 text-danger",
};

const TYPE_LABEL: Record<string, string> = {
  health: "Health",
  behavior: "Behavior",
  feeding: "Feeding",
  other: "Other",
};

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[] | null>(null);
  const [dogs, setDogs] = useState<Dog[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const load = async (silent = false) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    try {
      const [i, d] = await Promise.all([
        api.get<Incident[]>("/incidents/recent"),
        api.get<Dog[]>("/dogs"),
      ]);
      setIncidents(i);
      setDogs(d);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const dogById = useMemo(() => {
    const m: Record<number, Dog> = {};
    (dogs || []).forEach((d) => (m[d.id] = d));
    return m;
  }, [dogs]);

  const filtered = useMemo(() => {
    if (!incidents) return [];
    return incidents.filter((i) => {
      if (severityFilter !== "all" && i.severity !== severityFilter)
        return false;
      if (typeFilter !== "all" && i.type !== typeFilter) return false;
      return true;
    });
  }, [incidents, severityFilter, typeFilter]);

  const counts = useMemo(() => {
    const c = { mild: 0, moderate: 0, severe: 0 };
    (incidents || []).forEach((i) => {
      if (i.severity in c) c[i.severity as keyof typeof c]++;
    });
    return c;
  }, [incidents]);

  return (
    <AuthGate>
      <Sidebar />
      <TopNav />
      <main className="mx-auto max-w-5xl px-4 pb-24 pt-6 md:ml-60 md:max-w-none md:px-10 md:pb-10 md:pt-8">
        <header className="mb-8 flex items-end justify-between gap-4">
          <div>
            <p className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted">
              <AlertTriangle className="h-3 w-3" />
              Incidents
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-text md:text-3xl">
              Recent incidents
            </h1>
            <p className="mt-1 text-sm text-muted">
              Last 20 incidents across all dogs, newest first.
            </p>
          </div>
          <button
            onClick={() => load(true)}
            disabled={refreshing || loading}
            className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-medium text-text transition hover:border-accent hover:text-accent disabled:opacity-50"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
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
            {/* Stats */}
            <div className="mb-6 grid grid-cols-3 gap-px overflow-hidden rounded-lg border border-border bg-border">
              <SeverityStat label="Mild" value={counts.mild} tone="default" />
              <SeverityStat label="Moderate" value={counts.moderate} tone="warn" />
              <SeverityStat label="Severe" value={counts.severe} tone="danger" />
            </div>

            {/* Filters */}
            <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
              <span className="inline-flex items-center gap-1 text-muted">
                <Filter className="h-3 w-3" />
                Filter:
              </span>
              <FilterPills
                label="Severity"
                value={severityFilter}
                options={["all", "mild", "moderate", "severe"]}
                onChange={setSeverityFilter}
              />
              <FilterPills
                label="Type"
                value={typeFilter}
                options={["all", "health", "behavior", "feeding", "other"]}
                onChange={setTypeFilter}
              />
              <span className="ml-auto font-mono text-[11px] text-muted">
                {filtered.length} / {incidents?.length ?? 0}
              </span>
            </div>

            {/* List */}
            {filtered.length === 0 ? (
              <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-muted">
                No incidents match the current filter.
              </p>
            ) : (
              <ul className="overflow-hidden rounded-lg border border-border bg-bg">
                {filtered.map((i) => {
                  const dog = dogById[i.dog_id];
                  return (
                    <li
                      key={i.id}
                      className="flex items-start gap-4 border-b border-border px-4 py-3 last:border-0"
                    >
                      <span
                        className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                          SEVERITY_STYLE[i.severity] ??
                          "border-border bg-bg text-muted"
                        }`}
                      >
                        {i.severity}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 text-sm">
                          <span className="font-semibold text-text">
                            {dog?.name ?? `Dog #${i.dog_id}`}
                          </span>
                          <span className="text-muted">·</span>
                          <span className="text-muted">
                            {TYPE_LABEL[i.type] ?? i.type}
                          </span>
                          <span className="ml-auto font-mono text-[11px] text-muted">
                            {relTime(i.created_at)}
                          </span>
                        </div>
                        <p className="mt-1 text-sm text-text">
                          {i.description}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        )}
      </main>
      <BottomNav />
    </AuthGate>
  );
}

function SeverityStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "default" | "warn" | "danger";
}) {
  return (
    <div className="bg-bg px-4 py-3">
      <div className="text-[11px] uppercase tracking-wider text-muted">
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

function FilterPills({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="inline-flex items-center gap-1">
      <span className="text-muted">{label}:</span>
      {options.map((o) => {
        const active = o === value;
        return (
          <button
            key={o}
            onClick={() => onChange(o)}
            className={`rounded-md border px-2 py-0.5 transition ${
              active
                ? "border-accent/40 bg-accent/10 text-accent"
                : "border-border bg-surface text-muted hover:border-accent/40 hover:text-text"
            }`}
          >
            {o}
          </button>
        );
      })}
    </div>
  );
}
