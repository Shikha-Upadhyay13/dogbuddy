"use client";

import { useEffect, useState } from "react";
import {
  X,
  Footprints,
  UtensilsCrossed,
  Pill,
  LogIn,
  LogOut,
  Loader2,
  AlertCircle,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { relTime } from "@/lib/time";
import type {
  Booking,
  DogDetail,
  Incident,
  TodayBookingItem,
} from "@/lib/types";
import StatusBadge from "./StatusBadge";

type Props = {
  item: TodayBookingItem;
  onClose: () => void;
  onAction: () => void;
};

const SEVERITY_STYLE: Record<string, string> = {
  mild: "text-muted",
  moderate: "text-warning",
  severe: "text-danger",
};

export default function DogDetailModal({ item, onClose, onAction }: Props) {
  const [detail, setDetail] = useState<DogDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<string | null>(null);

  const bookingId = item.booking_id;

  const loadDetail = async () => {
    try {
      const d = await api.get<DogDetail>(`/dogs/${item.dog.id}`);
      setDetail(d);
      setError(null);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "Could not load dog details",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDetail();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item.dog.id]);

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const currentStatus = detail?.current_booking?.status ?? item.status;

  const doActivity = async (
    activity: "walk" | "feed" | "meds",
    label: string,
  ) => {
    if (actionBusy) return;
    setActionBusy(label);
    try {
      await api.patch<Booking>(`/bookings/${bookingId}/activity`, { activity });
      await loadDetail();
      onAction();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : `Failed to mark ${label}`,
      );
    } finally {
      setActionBusy(null);
    }
  };

  const doStatus = async (
    status: "checked_in" | "checked_out",
    label: string,
  ) => {
    if (actionBusy) return;
    setActionBusy(label);
    try {
      await api.patch<Booking>(`/bookings/${bookingId}/status`, { status });
      await loadDetail();
      onAction();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : `Failed to ${label.toLowerCase()}`,
      );
    } finally {
      setActionBusy(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-border bg-surface p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute right-3 top-3 rounded-md p-1 text-muted hover:bg-border/40 hover:text-text"
          aria-label="Close"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="mb-4 flex items-center gap-3 pr-8">
          <h2 className="text-xl font-semibold">{item.dog.name}</h2>
          <StatusBadge status={currentStatus} />
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading...
          </div>
        )}
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            <AlertCircle className="h-4 w-4" /> {error}
          </div>
        )}

        {detail && (
          <>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <Row k="Breed" v={detail.breed} />
              <Row k="Age" v={`${detail.age_years}y`} />
              <Row k="Weight" v={`${detail.weight_kg} kg`} />
              <Row k="Vacc" v={fmtVacc(detail)} />
              <Row k="Diet" v={detail.diet || "—"} span />
              <Row k="Medications" v={detail.medications || "—"} span />
              <Row k="Allergies" v={detail.allergies || "—"} span />
              <Row
                k="Owner"
                v={`${detail.owner_name} · ${detail.owner_phone}`}
                span
              />
              <Row k="Vet" v={detail.vet_contact || "—"} span />
              <Row k="Notes" v={detail.notes || "—"} span />
            </dl>

            <hr className="my-5 border-border" />

            <h3 className="mb-2 text-sm font-semibold text-muted">Activity</h3>
            <div className="grid grid-cols-3 gap-2">
              <ActionBtn
                Icon={Footprints}
                label="Walked"
                busy={actionBusy === "walked"}
                onClick={() => doActivity("walk", "walked")}
                sub={relTime(detail.current_booking?.last_walked_at)}
              />
              <ActionBtn
                Icon={UtensilsCrossed}
                label="Fed"
                busy={actionBusy === "fed"}
                onClick={() => doActivity("feed", "fed")}
                sub={relTime(detail.current_booking?.last_fed_at)}
              />
              <ActionBtn
                Icon={Pill}
                label="Meds"
                busy={actionBusy === "meds"}
                onClick={() => doActivity("meds", "meds")}
                sub={relTime(detail.current_booking?.last_meds_at)}
              />
            </div>

            <h3 className="mb-2 mt-5 text-sm font-semibold text-muted">
              Status
            </h3>
            <div className="flex gap-2">
              {currentStatus === "scheduled" && (
                <StatusBtn
                  Icon={LogIn}
                  label="Check In"
                  busy={actionBusy === "Check In"}
                  onClick={() => doStatus("checked_in", "Check In")}
                />
              )}
              {(currentStatus === "checked_in" ||
                currentStatus === "in_care") && (
                <StatusBtn
                  Icon={LogOut}
                  label="Check Out"
                  busy={actionBusy === "Check Out"}
                  onClick={() => doStatus("checked_out", "Check Out")}
                />
              )}
              {currentStatus === "checked_out" && (
                <p className="text-sm text-muted">Already checked out.</p>
              )}
            </div>

            <hr className="my-5 border-border" />

            <h3 className="mb-2 text-sm font-semibold text-muted">
              Recent incidents{" "}
              {detail.recent_incidents.length > 0 &&
                `(${detail.recent_incidents.length})`}
            </h3>
            {detail.recent_incidents.length === 0 ? (
              <p className="text-sm text-muted">No incidents on record.</p>
            ) : (
              <ul className="space-y-2">
                {detail.recent_incidents.map((i: Incident) => (
                  <li
                    key={i.id}
                    className="rounded-lg border border-border bg-bg/40 p-2 text-sm"
                  >
                    <div className="flex items-center justify-between text-xs text-muted">
                      <span>
                        {i.type} ·{" "}
                        <span
                          className={SEVERITY_STYLE[i.severity] ?? "text-muted"}
                        >
                          {i.severity}
                        </span>
                      </span>
                      <span>{relTime(i.created_at)}</span>
                    </div>
                    <p className="mt-1 text-text">{i.description}</p>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Row({ k, v, span = false }: { k: string; v: string; span?: boolean }) {
  return (
    <div className={span ? "col-span-2" : ""}>
      <dt className="text-xs uppercase tracking-wide text-muted">{k}</dt>
      <dd className="text-text">{v}</dd>
    </div>
  );
}

function fmtVacc(d: DogDetail): string {
  if (d.vaccination_status === "up_to_date") return "Up to date";
  if (d.vaccination_status === "expiring_soon")
    return `Expiring soon${d.vaccination_expires ? ` (${d.vaccination_expires})` : ""}`;
  if (d.vaccination_status === "expired")
    return `EXPIRED${d.vaccination_expires ? ` (${d.vaccination_expires})` : ""}`;
  return d.vaccination_status;
}

function ActionBtn({
  Icon,
  label,
  sub,
  busy,
  onClick,
}: {
  Icon: typeof Footprints;
  label: string;
  sub: string;
  busy: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className="flex flex-col items-center justify-center gap-1 rounded-lg border border-border bg-bg/40 px-2 py-3 text-sm transition hover:border-accent disabled:opacity-50"
    >
      {busy ? (
        <Loader2 className="h-5 w-5 animate-spin" />
      ) : (
        <Icon className="h-5 w-5 text-accent" />
      )}
      <span className="font-medium text-text">Mark {label}</span>
      <span className="text-xs text-muted">{sub}</span>
    </button>
  );
}

function StatusBtn({
  Icon,
  label,
  busy,
  onClick,
}: {
  Icon: typeof LogIn;
  label: string;
  busy: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-bg transition hover:opacity-90 disabled:opacity-50"
    >
      {busy ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Icon className="h-4 w-4" />
      )}
      {label}
    </button>
  );
}
