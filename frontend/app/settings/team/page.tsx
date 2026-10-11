"use client";

import { useState } from "react";

import AuthGate from "@/components/AuthGate";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";

export default function TeamSettingsPage() {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState("attendant");
  const [code, setCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const invite = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await api.post<{ code: string; facility_slug: string }>(
        "/team/invites",
        { name, phone, role },
      );
      setCode(res.code);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not invite");
    }
  };

  return (
    <AuthGate>
      <Sidebar />
      <main className="mx-auto max-w-lg px-4 py-8 md:ml-60">
        <h1 className="text-2xl font-semibold">Team</h1>
        <p className="mt-2 text-sm text-muted">
          Invite an attendant or another admin. They set a password on the accept-invite page.
        </p>
        <form onSubmit={invite} className="mt-6 space-y-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name"
            className="w-full rounded-md border border-border bg-surface px-3 py-2"
            required
          />
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="Phone"
            className="w-full rounded-md border border-border bg-surface px-3 py-2"
            required
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full rounded-md border border-border bg-bg px-3 py-2"
          >
            <option value="attendant">Attendant</option>
            <option value="admin">Admin</option>
          </select>
          <button className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg">
            Create invite
          </button>
        </form>
        {code && (
          <p className="mt-4 text-sm">
            Invite code <span className="font-mono text-accent">{code}</span>
          </p>
        )}
        {error && <p className="mt-4 text-sm text-danger">{error}</p>}
      </main>
    </AuthGate>
  );
}
