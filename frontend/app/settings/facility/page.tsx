"use client";

import { useEffect, useState } from "react";

import AuthGate from "@/components/AuthGate";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";

type FacilitySettings = {
  name: string;
  state: string;
  phone: string | null;
  booking_mode: string;
  deposit_percent: number;
  max_dogs: number;
  require_vaccination: boolean;
  waiver_text: string;
  whatsapp_enabled: boolean;
  email_enabled: boolean;
  nightly_rate_paise: number;
  gstin: string | null;
  gst_rate_bps: number;
  razorpay_key_id: string | null;
};

export default function FacilitySettingsPage() {
  const [form, setForm] = useState<FacilitySettings | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [keySecret, setKeySecret] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");

  useEffect(() => {
    api
      .get<FacilitySettings>("/settings/facility")
      .then(setForm)
      .catch((err) =>
        setMessage(err instanceof ApiError ? err.detail : "Admins only"),
      );
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form) return;
    try {
      await api.patch("/settings/facility", {
        ...form,
        ...(keySecret ? { razorpay_key_secret: keySecret } : {}),
        ...(webhookSecret ? { razorpay_webhook_secret: webhookSecret } : {}),
      });
      setMessage("Saved");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.detail : "Could not save");
    }
  };

  return (
    <AuthGate>
      <Sidebar />
      <main className="mx-auto max-w-lg px-4 py-8 md:ml-60">
        <h1 className="text-2xl font-semibold">Facility</h1>
        {!form ? (
          <p className="mt-4 text-sm text-muted">{message ?? "Loading..."}</p>
        ) : (
          <form onSubmit={save} className="mt-6 space-y-3">
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full rounded-md border border-border bg-surface px-3 py-2"
            />
            <input
              value={form.state}
              onChange={(e) => setForm({ ...form, state: e.target.value })}
              className="w-full rounded-md border border-border bg-surface px-3 py-2"
              placeholder="State"
            />
            <label className="flex gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.require_vaccination}
                onChange={(e) =>
                  setForm({ ...form, require_vaccination: e.target.checked })
                }
              />
              Require valid vaccination
            </label>
            <label className="flex gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.whatsapp_enabled}
                onChange={(e) =>
                  setForm({ ...form, whatsapp_enabled: e.target.checked })
                }
              />
              WhatsApp
            </label>
            <label className="flex gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.email_enabled}
                onChange={(e) => setForm({ ...form, email_enabled: e.target.checked })}
              />
              Email
            </label>
            <input
              value={form.gstin ?? ""}
              onChange={(e) => setForm({ ...form, gstin: e.target.value })}
              className="w-full rounded-md border border-border bg-surface px-3 py-2"
              placeholder="GSTIN"
            />
            <input
              value={form.razorpay_key_id ?? ""}
              onChange={(e) => setForm({ ...form, razorpay_key_id: e.target.value })}
              className="w-full rounded-md border border-border bg-surface px-3 py-2"
              placeholder="Razorpay key id"
            />
            <input
              type="password"
              value={keySecret}
              onChange={(e) => setKeySecret(e.target.value)}
              className="w-full rounded-md border border-border bg-surface px-3 py-2"
              placeholder="Razorpay key secret"
            />
            <input
              type="password"
              value={webhookSecret}
              onChange={(e) => setWebhookSecret(e.target.value)}
              className="w-full rounded-md border border-border bg-surface px-3 py-2"
              placeholder="Razorpay webhook secret"
            />
            <textarea
              value={form.waiver_text}
              onChange={(e) => setForm({ ...form, waiver_text: e.target.value })}
              className="h-28 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
            />
            <button className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg">
              Save
            </button>
            {message && <p className="text-sm text-muted">{message}</p>}
          </form>
        )}
      </main>
    </AuthGate>
  );
}
