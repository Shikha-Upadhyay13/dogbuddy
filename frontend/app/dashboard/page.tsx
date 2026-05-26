"use client";

import AuthGate from "@/components/AuthGate";
import { getUser, clearAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";

// Placeholder dashboard. Phase 5 fills this in.
export default function DashboardPage() {
  const router = useRouter();
  const user = getUser();

  const onLogout = () => {
    clearAuth();
    router.replace("/login");
  };

  return (
    <AuthGate>
      <main className="mx-auto max-w-3xl px-4 py-6">
        <header className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Today</h1>
          <div className="flex items-center gap-3 text-sm text-muted">
            <span>{user?.name ?? "Staff"}</span>
            <button
              onClick={onLogout}
              className="rounded border border-border px-2 py-1 text-text transition hover:border-accent hover:text-accent"
            >
              Logout
            </button>
          </div>
        </header>
        <div className="rounded-lg border border-border bg-surface p-6 text-muted">
          Dashboard placeholder. Phase 5 lists today&apos;s dogs here.
        </div>
      </main>
    </AuthGate>
  );
}
