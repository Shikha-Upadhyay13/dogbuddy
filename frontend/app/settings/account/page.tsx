"use client";

import { useEffect, useState } from "react";

import Link from "next/link";

import AuthGate from "@/components/AuthGate";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";
import { isStaffRole, getUser } from "@/lib/auth";

export default function AccountSettingsPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [billingState, setBillingState] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<{ name: string; email: string | null; phone: string; billing_state: string | null }>(
        "/settings/account",
      )
      .then((row) => {
        setName(row.name);
        setEmail(row.email ?? "");
        setPhone(row.phone);
        setBillingState(row.billing_state ?? "");
      })
      .catch(() => setMessage("Could not load account"));
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.patch("/settings/account", { name, email, billing_state: billingState });
      setMessage("Saved");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.detail : "Could not save");
    }
  };

  return (
    <AuthGate>
      <Sidebar />
      <main className="mx-auto max-w-lg px-4 py-8 md:ml-60">
        <h1 className="text-2xl font-semibold">Account</h1>
        <nav className="mt-4 flex flex-wrap gap-3 text-sm text-accent">
          <Link href="/settings/notifications">Notifications</Link>
          {isStaffRole(getUser()?.role) && getUser()?.role === "admin" && (
            <>
              <Link href="/settings/facility">Facility</Link>
              <Link href="/settings/team">Team</Link>
              <Link href="/settings/rates">Rates</Link>
              <Link href="/settings/kennels">Kennels</Link>
            </>
          )}
        </nav>
        <form onSubmit={save} className="mt-6 space-y-4">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border border-border bg-surface px-3 py-2"
            placeholder="Name"
          />
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-border bg-surface px-3 py-2"
            placeholder="Email"
          />
          <p className="font-mono text-sm text-muted">{phone}</p>
          <input
            value={billingState}
            onChange={(e) => setBillingState(e.target.value)}
            className="w-full rounded-md border border-border bg-surface px-3 py-2"
            placeholder="Billing state"
          />
          <button className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg">
            Save
          </button>
          {message && <p className="text-sm text-muted">{message}</p>}
        </form>
      </main>
    </AuthGate>
  );
}
