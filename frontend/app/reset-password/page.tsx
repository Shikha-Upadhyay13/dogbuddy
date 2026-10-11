"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { api, ApiError } from "@/lib/api";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const requestCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/password-reset/request", { phone }, { skipAuth: true });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not send a code");
    } finally {
      setBusy(false);
    }
  };

  const confirm = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post(
        "/auth/password-reset/confirm",
        { phone, code, password },
        { skipAuth: true },
      );
      router.replace("/login");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not reset password");
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <h1 className="text-3xl font-semibold tracking-tight">Reset password</h1>
      <p className="mt-2 text-sm text-muted">
        We send a one-time code to the phone on the account. In this environment
        the code is delivered by the notification worker once WhatsApp or email
        is connected.
      </p>
      <form onSubmit={sent ? confirm : requestCode} className="mt-8 space-y-4">
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="Phone"
          className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 text-text outline-none focus:border-accent"
          required
        />
        {sent && (
          <>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Code"
              className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 text-text outline-none focus:border-accent"
              required
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="New password"
              className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 text-text outline-none focus:border-accent"
              required
            />
          </>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-accent px-4 py-3 font-semibold text-bg disabled:opacity-50"
        >
          {sent ? "Set new password" : "Send code"}
        </button>
      </form>
      <Link href="/login" className="mt-6 text-sm text-accent">
        Back to sign in
      </Link>
    </main>
  );
}
