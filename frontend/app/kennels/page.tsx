"use client";

import { useCallback, useEffect, useState } from "react";

import AuthGate from "@/components/AuthGate";
import Sidebar from "@/components/Sidebar";
import TopNav from "@/components/TopNav";
import { api, ApiError } from "@/lib/api";

type Kennel = { id: number; name: string; status: string };

const STATUSES = [
  "available",
  "occupied",
  "reserved",
  "cleaning",
  "maintenance",
];

export default function KennelsPage() {
  const [rows, setRows] = useState<Kennel[] | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await api.get<Kennel[]>("/kennels"));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load kennels");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post("/kennels", { name, status: "available" });
      setName("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not add kennel");
    }
  };

  const setStatus = async (id: number, status: string) => {
    try {
      await api.patch(`/kennels/${id}`, { status });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not update kennel");
    }
  };

  return (
    <AuthGate>
      <Sidebar />
      <TopNav />
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-6 md:ml-60 md:px-10">
        <h1 className="text-2xl font-semibold tracking-tight">Kennels</h1>
        <form onSubmit={add} className="mt-4 flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="K-09"
            className="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm"
            required
          />
          <button className="rounded-md bg-accent px-3 py-2 text-sm font-medium text-bg">
            Add
          </button>
        </form>
        {error && <p className="mt-3 text-sm text-danger">{error}</p>}
        <ul className="mt-6 divide-y divide-border rounded-lg border border-border">
          {(rows ?? []).map((k) => (
            <li key={k.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div>
                <p className="font-medium">{k.name}</p>
                <p className="font-mono text-xs text-muted">#{k.id}</p>
              </div>
              <select
                value={k.status}
                onChange={(e) => setStatus(k.id, e.target.value)}
                className="rounded-md border border-border bg-bg px-2 py-1 text-sm"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </li>
          ))}
        </ul>
      </main>
    </AuthGate>
  );
}
