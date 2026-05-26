"use client";

import { Wrench, CheckCircle2 } from "lucide-react";

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
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-accent px-4 py-2 text-bg">
          {msg.text}
        </div>
      </div>
    );
  }

  // Assistant
  return (
    <div className="flex justify-start">
      <div className="max-w-[90%] space-y-2">
        {msg.tools.map((t, i) => (
          <ToolChip key={i} tool={t} />
        ))}

        {msg.thinking && (
          <div className="inline-flex items-center gap-1 text-xs text-muted">
            <span className="inline-flex gap-0.5">
              <Dot delay={0} />
              <Dot delay={150} />
              <Dot delay={300} />
            </span>
            DogBuddy is thinking...
          </div>
        )}

        {msg.text && (
          <div className="whitespace-pre-wrap rounded-2xl rounded-bl-md border border-border bg-surface px-4 py-2 text-text">
            {msg.text}
            {!msg.done && (
              <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-accent align-middle" />
            )}
          </div>
        )}

        {msg.error && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
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
  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs ${
        inFlight
          ? "border-accent/40 bg-accent/10 text-accent"
          : "border-border bg-bg/40 text-muted"
      }`}
    >
      {inFlight ? (
        <Wrench className="h-3 w-3" />
      ) : (
        <CheckCircle2 className="h-3 w-3" />
      )}
      <span className="font-mono">{tool.name}</span>
      {inFlight ? null : <span className="text-muted">·</span>}
      {!inFlight && tool.result && (
        <span className="max-w-[40ch] truncate text-muted">
          {firstLine(tool.result)}
        </span>
      )}
    </div>
  );
}

function firstLine(s: string): string {
  const i = s.indexOf("\n");
  return i === -1 ? s : s.slice(0, i);
}
