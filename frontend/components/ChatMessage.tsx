"use client";

import { Wrench, CheckCircle2, AlertTriangle } from "lucide-react";

export type ToolEvent = {
  name: string;
  args?: Record<string, unknown>;
  result?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  tools: ToolEvent[];
  thinking: boolean;
  done: boolean;
  error?: string;
};

export default function ChatMessageView({ msg }: { msg: ChatMessage }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-lg rounded-br-sm border border-accent/40 bg-accent/15 px-3.5 py-2 text-sm text-text">
          {msg.text}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] space-y-2">
        {msg.tools.map((t, i) => (
          <ToolChip key={i} tool={t} />
        ))}

        {msg.thinking && (
          <div className="inline-flex items-center gap-1.5 text-xs text-muted">
            <span className="inline-flex gap-0.5">
              <Dot delay={0} />
              <Dot delay={120} />
              <Dot delay={240} />
            </span>
            <span>thinking</span>
          </div>
        )}

        {msg.text && (
          <div className="whitespace-pre-wrap rounded-lg rounded-bl-sm border border-border bg-surface px-3.5 py-2 text-sm leading-relaxed text-text">
            {msg.text}
            {!msg.done && (
              <span className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-accent align-middle" />
            )}
          </div>
        )}

        {msg.error && (
          <div className="inline-flex items-center gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-1.5 text-xs text-danger">
            <AlertTriangle className="h-3.5 w-3.5" />
            {msg.error}
          </div>
        )}
      </div>
    </div>
  );
}

function Dot({ delay }: { delay: number }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-muted"
      style={{ animationDelay: `${delay}ms` }}
    />
  );
}

function ToolChip({ tool }: { tool: ToolEvent }) {
  const inFlight = tool.result === undefined;
  const argSummary = tool.args ? summarizeArgs(tool.args) : "";

  return (
    <div
      className={`inline-flex max-w-full items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px] tracking-tight ${
        inFlight
          ? "border-accent/40 bg-accent/5 text-accent"
          : "border-border bg-bg text-muted"
      }`}
    >
      {inFlight ? (
        <Wrench className="h-3 w-3 animate-pulse" />
      ) : (
        <CheckCircle2 className="h-3 w-3 text-success" />
      )}
      <span className="font-semibold text-text">{tool.name}</span>
      {argSummary && (
        <span className="hidden truncate text-muted sm:inline">
          ({argSummary})
        </span>
      )}
      {!inFlight && tool.result && (
        <>
          <span className="text-muted">→</span>
          <span className="max-w-[36ch] truncate text-muted">
            {firstLine(tool.result)}
          </span>
        </>
      )}
    </div>
  );
}

function firstLine(s: string): string {
  const i = s.indexOf("\n");
  return i === -1 ? s : s.slice(0, i);
}

function summarizeArgs(args: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(args)) {
    if (v === null || v === undefined) continue;
    if (typeof v === "object") continue;
    parts.push(`${k}=${String(v)}`);
    if (parts.length >= 2) break;
  }
  return parts.join(", ");
}
