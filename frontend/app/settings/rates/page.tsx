"use client";

import { useEffect, useState } from "react";

import AuthGate from "@/components/AuthGate";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";

type Rates = {
  nightly_rate_paise: number;
  addons: { id: number; name: string; price_paise: number }[];
};

export default function RatesPage() {
  const [rates, setRates] = useState<Rates | null>(null);
  const [nightly, setNightly] = useState("");
  const [addonName, setAddonName] = useState("");
  const [addonPrice, setAddonPrice] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const load = () => {
    api
      .get<Rates>("/settings/rates")
      .then((row) => {
        setRates(row);
        setNightly(String(row.nightly_rate_paise / 100));
      })
      .catch((err) =>
        setMessage(err instanceof ApiError ? err.detail : "Admins only"),
      );
  };

  useEffect(() => {
    load();
  }, []);

  const saveNightly = async () => {
    const paise = Math.round(Number(nightly) * 100);
    await api.patch("/settings/facility", { nightly_rate_paise: paise });
    setMessage("Nightly rate saved");
    load();
  };

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/settings/rates/addons", {
      name: addonName,
      price_paise: Math.round(Number(addonPrice) * 100),
    });
    setAddonName("");
    setAddonPrice("");
    load();
  };

  return (
    <AuthGate>
      <Sidebar />
      <main className="mx-auto max-w-lg px-4 py-8 md:ml-60">
        <h1 className="text-2xl font-semibold">Rates</h1>
        <p className="mt-2 text-sm text-muted">Amounts are rupees. Stored as paise.</p>
        <div className="mt-6 flex gap-2">
          <input
            value={nightly}
            onChange={(e) => setNightly(e.target.value)}
            className="flex-1 rounded-md border border-border bg-surface px-3 py-2"
            placeholder="Nightly rate"
          />
          <button
            onClick={() => void saveNightly()}
            className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-bg"
          >
            Save
          </button>
        </div>
        <ul className="mt-6 space-y-2 text-sm">
          {(rates?.addons ?? []).map((row) => (
            <li key={row.id}>
              {row.name} — ₹{(row.price_paise / 100).toFixed(2)}
            </li>
          ))}
        </ul>
        <form onSubmit={add} className="mt-4 flex gap-2">
          <input
            value={addonName}
            onChange={(e) => setAddonName(e.target.value)}
            placeholder="Add-on"
            className="flex-1 rounded-md border border-border bg-surface px-3 py-2"
            required
          />
          <input
            value={addonPrice}
            onChange={(e) => setAddonPrice(e.target.value)}
            placeholder="₹"
            className="w-24 rounded-md border border-border bg-surface px-3 py-2"
            required
          />
          <button className="rounded-md border border-border px-3 py-2 text-sm">Add</button>
        </form>
        {message && <p className="mt-3 text-sm text-muted">{message}</p>}
      </main>
    </AuthGate>
  );
}
