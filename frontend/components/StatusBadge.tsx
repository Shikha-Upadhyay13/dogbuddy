// Colored pill for a booking status.

const STYLES: Record<string, string> = {
  requested: "border-accent/40 bg-accent/10 text-accent",
  waitlisted: "border-warning/40 bg-warning/10 text-warning",
  awaiting_payment: "border-warning/40 bg-warning/10 text-warning",
  confirmed: "border-accent/40 bg-accent/10 text-accent",
  scheduled: "border-accent/40 bg-accent/10 text-accent",
  checked_in: "border-success/40 bg-success/10 text-success",
  in_care: "border-success/40 bg-success/10 text-success",
  checked_out: "border-border bg-border/30 text-muted",
  declined: "border-border bg-border/30 text-muted",
  cancelled: "border-border bg-border/30 text-muted",
};

const LABEL: Record<string, string> = {
  requested: "Requested",
  waitlisted: "Waitlisted",
  awaiting_payment: "Awaiting payment",
  confirmed: "Confirmed",
  scheduled: "Scheduled",
  checked_in: "Checked In",
  in_care: "In Care",
  checked_out: "Checked Out",
  declined: "Declined",
  cancelled: "Cancelled",
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = STYLES[status] ?? "border-border bg-border/30 text-muted";
  const label = LABEL[status] ?? status;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}
    >
      {label}
    </span>
  );
}
