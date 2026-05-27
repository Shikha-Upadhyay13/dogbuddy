"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";

import AuthGate from "@/components/AuthGate";
import { api, ApiError } from "@/lib/api";
import type { Dog } from "@/lib/types";

const VACC_OPTIONS = [
  { value: "up_to_date", label: "Up to date" },
  { value: "expiring_soon", label: "Expiring soon" },
  { value: "expired", label: "Expired" },
];

export default function RegisterDogPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [breed, setBreed] = useState("");
  const [age, setAge] = useState("");
  const [weight, setWeight] = useState("");
  const [diet, setDiet] = useState("");
  const [medications, setMedications] = useState("");
  const [allergies, setAllergies] = useState("");
  const [vaccinationStatus, setVaccinationStatus] = useState("up_to_date");
  const [vetContact, setVetContact] = useState("");
  const [notes, setNotes] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      await api.post<Dog>("/dogs", {
        name,
        breed,
        age_years: parseInt(age, 10),
        weight_kg: parseFloat(weight),
        diet: diet || null,
        medications: medications || null,
        allergies: allergies || null,
        vaccination_status: vaccinationStatus,
        vet_contact: vetContact || null,
        notes: notes || null,
      });
      router.replace("/owner/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to register dog");
      setBusy(false);
    }
  };

  return (
    <AuthGate>
      <main className="mx-auto max-w-2xl px-4 pb-24 pt-6 md:px-8 md:pt-10">
        <Link
          href="/owner/dashboard"
          className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted transition hover:text-text"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to dashboard
        </Link>

        <h1 className="text-3xl font-semibold tracking-tight">
          Register a dog
        </h1>
        <p className="mt-1 text-sm text-muted">
          Add your dog to your profile so you can book stays.
        </p>

        <form
          onSubmit={onSubmit}
          className="mt-8 space-y-5 rounded-xl border border-border bg-surface p-6"
        >
          <Section title="Basics">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Dog's name" required>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  disabled={busy}
                  placeholder="Bruno"
                  className={inputCls}
                />
              </Field>
              <Field label="Breed" required>
                <input
                  value={breed}
                  onChange={(e) => setBreed(e.target.value)}
                  required
                  disabled={busy}
                  placeholder="Labrador"
                  className={inputCls}
                />
              </Field>
              <Field label="Age (years)" required>
                <input
                  type="number"
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                  required
                  min={0}
                  max={30}
                  disabled={busy}
                  placeholder="4"
                  className={inputCls}
                />
              </Field>
              <Field label="Weight (kg)" required>
                <input
                  type="number"
                  value={weight}
                  onChange={(e) => setWeight(e.target.value)}
                  required
                  step="0.1"
                  min={0.1}
                  max={100}
                  disabled={busy}
                  placeholder="28"
                  className={inputCls}
                />
              </Field>
            </div>
          </Section>

          <Section title="Care details (optional)">
            <Field label="Diet">
              <input
                value={diet}
                onChange={(e) => setDiet(e.target.value)}
                disabled={busy}
                placeholder="Twice daily kibble, 1.5 cups"
                className={inputCls}
              />
            </Field>
            <Field label="Medications">
              <input
                value={medications}
                onChange={(e) => setMedications(e.target.value)}
                disabled={busy}
                placeholder="Levothyroxine (thyroid), comma-separated"
                className={inputCls}
              />
            </Field>
            <Field label="Allergies">
              <input
                value={allergies}
                onChange={(e) => setAllergies(e.target.value)}
                disabled={busy}
                placeholder="Chicken, peanuts"
                className={inputCls}
              />
            </Field>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Vaccination status">
                <select
                  value={vaccinationStatus}
                  onChange={(e) => setVaccinationStatus(e.target.value)}
                  disabled={busy}
                  className={inputCls}
                >
                  {VACC_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Vet contact">
                <input
                  value={vetContact}
                  onChange={(e) => setVetContact(e.target.value)}
                  disabled={busy}
                  placeholder="Dr. Mehta - 9811122233"
                  className={inputCls}
                />
              </Field>
            </div>
            <Field label="Notes (anything else staff should know)">
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={busy}
                rows={3}
                placeholder="Reactive to other dogs, walk alone."
                className={`${inputCls} resize-none`}
              />
            </Field>
          </Section>

          {error && (
            <div className="flex items-center gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
              <AlertCircle className="h-4 w-4" /> {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-3">
            <Link
              href="/owner/dashboard"
              className="rounded-md border border-border px-3 py-2 text-sm text-muted transition hover:text-text"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg shadow shadow-accent/20 transition hover:opacity-90 disabled:opacity-50"
            >
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              {busy ? "Saving..." : "Register dog"}
            </button>
          </div>
        </form>
      </main>
    </AuthGate>
  );
}

const inputCls =
  "w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none ring-accent/30 transition focus:border-accent focus:ring-2 disabled:opacity-50";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-4">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
        {title}
      </h2>
      {children}
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-text/90">
        {label}
        {required && <span className="ml-0.5 text-danger">*</span>}
      </span>
      {children}
    </label>
  );
}
