"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Users,
  Search,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
  Loader2,
  RefreshCw,
} from "lucide-react";

import AuthGate from "@/components/AuthGate";
import BottomNav from "@/components/BottomNav";
import Sidebar from "@/components/Sidebar";
import TopNav from "@/components/TopNav";
import { api, ApiError } from "@/lib/api";
import { relTime } from "@/lib/time";
import type { Owner } from "@/lib/types";

type SortKey = "name" | "phone" | "created_at" | "dog_count";
type SortDir = "asc" | "desc";

export default function OwnersPage() {
  const [owners, setOwners] = useState<Owner[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const load = async (silent = false) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    try {
      const o = await api.get<Owner[]>("/owners");
      setOwners(o);
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

  const filtered = useMemo(() => {
    if (!owners) return [];
    let r = owners;
    const q = search.trim().toLowerCase();
    if (q) {
      r = r.filter(
        (o) =>
          o.name.toLowerCase().includes(q) ||
          o.phone.toLowerCase().includes(q),
      );
    }
    r = [...r].sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case "name":
          cmp = a.name.localeCompare(b.name);
          break;
        case "phone":
          cmp = a.phone.localeCompare(b.phone);
          break;
        case "created_at":
          cmp = a.created_at.localeCompare(b.created_at);
          break;
        case "dog_count":
          cmp = a.dog_count - b.dog_count;
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return r;
  }, [owners, search, sortBy, sortDir]);

  const onSort = (col: SortKey) => {
    if (sortBy === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir(col === "name" || col === "phone" ? "asc" : "desc");
    }
  };

  return (
    <AuthGate>
      <Sidebar />
      <TopNav />
      <main className="mx-auto max-w-6xl px-4 pb-24 pt-6 md:ml-60 md:max-w-none md:px-10 md:pb-10 md:pt-8">
        <header className="mb-6 flex items-end justify-between gap-4">
          <div>
            <p className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted">
              <Users className="h-3 w-3" />
              Directory
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-text md:text-3xl">
              Owners
            </h1>
            <p className="mt-1 font-mono text-xs text-muted">
              {filtered.length} of {owners?.length ?? 0} accounts
              {search.trim() && ` · filter "${search.trim()}"`}
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

        {/* Search */}
        <div className="mb-4 flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 ring-accent/30 focus-within:border-accent focus-within:ring-2">
          <Search className="h-4 w-4 text-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or phone…"
            className="flex-1 bg-transparent text-sm text-text outline-none placeholder:text-muted"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="rounded px-1 font-mono text-[10px] text-muted hover:text-text"
            >
              clear
            </button>
          )}
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading...
          </div>
        ) : error ? (
          <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-border bg-surface/60">
                  <ColHeader
                    label="Name"
                    col="name"
                    active={sortBy === "name"}
                    dir={sortDir}
                    onSort={onSort}
                  />
                  <ColHeader
                    label="Phone"
                    col="phone"
                    active={sortBy === "phone"}
                    dir={sortDir}
                    onSort={onSort}
                  />
                  <ColHeader
                    label="Joined"
                    col="created_at"
                    active={sortBy === "created_at"}
                    dir={sortDir}
                    onSort={onSort}
                  />
                  <ColHeader
                    label="Dogs"
                    col="dog_count"
                    align="right"
                    active={sortBy === "dog_count"}
                    dir={sortDir}
                    onSort={onSort}
                  />
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td
                      colSpan={4}
                      className="px-3 py-8 text-center text-sm text-muted"
                    >
                      {search.trim()
                        ? `No owners match "${search.trim()}".`
                        : "No owner accounts yet. They appear here as soon as someone signs up."}
                    </td>
                  </tr>
                ) : (
                  filtered.map((o, i) => (
                    <tr
                      key={o.id}
                      className={`border-b border-border last:border-0 transition hover:bg-surface/40 ${
                        i % 2 === 0 ? "bg-bg" : "bg-bg/60"
                      }`}
                    >
                      <td className="px-3 py-2.5 text-text">{o.name}</td>
                      <td className="px-3 py-2.5 font-mono text-xs text-muted">
                        {o.phone}
                      </td>
                      <td className="px-3 py-2.5 font-mono text-xs text-muted">
                        {relTime(o.created_at)}
                      </td>
                      <td
                        className={`px-3 py-2.5 text-right font-mono tabular-nums ${
                          o.dog_count > 0 ? "text-text" : "text-muted"
                        }`}
                      >
                        {o.dog_count}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Footnote: aggregate */}
        {owners && owners.length > 0 && !loading && (
          <p className="mt-4 font-mono text-[11px] text-muted">
            {owners.length} accounts ·{" "}
            {owners.filter((o) => o.dog_count > 0).length} with ≥1 dog ·{" "}
            {owners.reduce((s, o) => s + o.dog_count, 0)} owner-registered dogs total
          </p>
        )}
      </main>
      <BottomNav />
    </AuthGate>
  );
}

function ColHeader({
  label,
  col,
  active,
  dir,
  align = "left",
  onSort,
}: {
  label: string;
  col: SortKey;
  active: boolean;
  dir: SortDir;
  align?: "left" | "right";
  onSort: (col: SortKey) => void;
}) {
  return (
    <th
      onClick={() => onSort(col)}
      className={`cursor-pointer select-none px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-muted transition hover:text-text ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      <span
        className={`inline-flex items-center gap-1 ${
          align === "right" ? "" : ""
        }`}
      >
        {label}
        {active ? (
          dir === "asc" ? (
            <ArrowUp className="h-3 w-3 text-accent" />
          ) : (
            <ArrowDown className="h-3 w-3 text-accent" />
          )
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-40" />
        )}
      </span>
    </th>
  );
}
