"use client";

import { useEffect, useState } from "react";

import AuthGate from "@/components/AuthGate";
import Sidebar from "@/components/Sidebar";
import { api } from "@/lib/api";

type Pref = { category: string; whatsapp: boolean; email: boolean };

export default function NotificationSettingsPage() {
  const [rows, setRows] = useState<Pref[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    api.get<Pref[]>("/settings/notifications").then(setRows).catch(() => setMessage("Could not load"));
  }, []);

  const toggle = (category: string, key: "whatsapp" | "email") => {
    setRows((prev) =>
      prev.map((row) =>
        row.category === category ? { ...row, [key]: !row[key] } : row,
      ),
    );
  };

  const save = async () => {
    await api.put("/settings/notifications", rows);
    setMessage("Saved. In-app alerts stay on. Severe incidents still send.");
  };

  return (
    <AuthGate>
      <Sidebar />
      <main className="mx-auto max-w-lg px-4 py-8 md:ml-60">
        <h1 className="text-2xl font-semibold">Notifications</h1>
        <p className="mt-2 text-sm text-muted">
          In-app delivery cannot be turned off. A severe incident is sent even if these are off.
        </p>
        <ul className="mt-6 space-y-3">
          {rows.map((row) => (
            <li key={row.category} className="rounded-lg border border-border p-3">
              <p className="font-medium capitalize">{row.category.replace("_", " ")}</p>
              <label className="mt-2 flex gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={row.whatsapp}
                  onChange={() => toggle(row.category, "whatsapp")}
                />
                WhatsApp
              </label>
              <label className="mt-1 flex gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={row.email}
                  onChange={() => toggle(row.category, "email")}
                />
                Email
              </label>
            </li>
          ))}
        </ul>
        <button
          onClick={() => void save()}
          className="mt-4 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg"
        >
          Save
        </button>
        {message && <p className="mt-3 text-sm text-muted">{message}</p>}
      </main>
    </AuthGate>
  );
}
