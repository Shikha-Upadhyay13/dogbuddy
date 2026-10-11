"use client";

import { useEffect, useState } from "react";

import AuthGate from "@/components/AuthGate";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";

type Invoice = {
  id: number;
  number: string;
  kind: string;
  total_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
  payment_link: string | null;
  pdf_url: string | null;
};

function rupees(paise: number): string {
  const sign = paise < 0 ? "-" : "";
  const abs = Math.abs(paise);
  return `${sign}₹${Math.floor(abs / 100).toLocaleString("en-IN")}.${String(abs % 100).padStart(2, "0")}`;
}

export default function InvoicesPage() {
  const [rows, setRows] = useState<Invoice[] | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [amount, setAmount] = useState<Record<number, string>>({});

  const load = () => {
    api
      .get<Invoice[]>("/invoices")
      .then(setRows)
      .catch((err) =>
        setMessage(err instanceof ApiError ? err.detail : "Could not load invoices"),
      );
  };

  useEffect(() => {
    load();
  }, []);

  const record = async (id: number, method: "cash" | "upi") => {
    const rupee = Number(amount[id] || "0");
    try {
      await api.post(`/invoices/${id}/payments`, {
        method,
        amount_paise: Math.round(rupee * 100),
      });
      setMessage("Payment recorded");
      load();
    } catch (err) {
      setMessage(err instanceof ApiError ? err.detail : "Could not record payment");
    }
  };

  return (
    <AuthGate>
      <Sidebar />
      <main className="mx-auto max-w-3xl px-4 py-8 md:ml-60">
        <h1 className="text-2xl font-semibold">Invoices</h1>
        {message && <p className="mt-3 text-sm text-muted">{message}</p>}
        <ul className="mt-6 space-y-3">
          {(rows ?? []).map((row) => (
            <li key={row.id} className="rounded-lg border border-border bg-bg p-4">
              <div className="flex items-baseline justify-between gap-3">
                <p className="font-medium">
                  {row.number}{" "}
                  <span className="text-sm text-muted">{row.kind}</span>
                </p>
                <p className="font-mono text-sm">{rupees(row.total_paise)}</p>
              </div>
              <p className="mt-1 text-xs text-muted">
                CGST {rupees(row.cgst_paise)} · SGST {rupees(row.sgst_paise)} · IGST{" "}
                {rupees(row.igst_paise)}
              </p>
              {row.payment_link && (
                <a className="mt-2 block text-sm text-accent" href={row.payment_link}>
                  Payment link
                </a>
              )}
              {row.pdf_url && (
                <a className="mt-1 block text-sm text-accent" href={`/backend${row.pdf_url}`}>
                  PDF
                </a>
              )}
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <input
                  value={amount[row.id] ?? ""}
                  onChange={(e) => setAmount({ ...amount, [row.id]: e.target.value })}
                  placeholder="Amount in rupees"
                  className="rounded-md border border-border bg-surface px-2 py-1 text-sm"
                />
                <button
                  type="button"
                  onClick={() => record(row.id, "cash")}
                  className="rounded-md border border-border px-2 py-1 text-sm"
                >
                  Cash
                </button>
                <button
                  type="button"
                  onClick={() => record(row.id, "upi")}
                  className="rounded-md border border-border px-2 py-1 text-sm"
                >
                  UPI
                </button>
              </div>
            </li>
          ))}
        </ul>
      </main>
    </AuthGate>
  );
}
