"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { api, ApiError } from "@/lib/api";
import { homeForRole, saveUser } from "@/lib/auth";
import type { AuthResponse } from "@/lib/types";

export default function AcceptInvitePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-muted">
          Loading...
        </div>
      }
    >
      <AcceptForm />
    </Suspense>
  );
}

function AcceptForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [phone, setPhone] = useState(params.get("phone") ?? "");
  const [code, setCode] = useState(params.get("code") ?? "");
  const [facilitySlug, setFacilitySlug] = useState(params.get("facility") ?? "demo");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<AuthResponse>(
        "/auth/accept-invite",
        { phone, code, password, facility_slug: facilitySlug },
        { skipAuth: true },
      );
      if (!res.user) throw new Error("No session");
      saveUser(res.user);
      router.replace(homeForRole(res.user.role));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Invite could not be accepted");
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <h1 className="text-3xl font-semibold tracking-tight">Accept invite</h1>
      <p className="mt-2 text-sm text-muted">
        Set a password to join the facility as staff.
      </p>
      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <input
          value={facilitySlug}
          onChange={(e) => setFacilitySlug(e.target.value)}
          placeholder="Facility slug"
          className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 outline-none focus:border-accent"
          required
        />
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="Phone"
          className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 outline-none focus:border-accent"
          required
        />
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="Invite code"
          className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 outline-none focus:border-accent"
          required
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 outline-none focus:border-accent"
          required
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <button
          disabled={busy}
          className="w-full rounded-lg bg-accent px-4 py-3 font-semibold text-bg disabled:opacity-50"
        >
          Join facility
        </button>
      </form>
    </main>
  );
}
