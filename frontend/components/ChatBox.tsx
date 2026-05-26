"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Send, Mic, MicOff, ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

import { API_BASE } from "@/lib/api";
import { getToken, getUser } from "@/lib/auth";
import { streamSse } from "@/lib/sse";
import ChatMessageView, {
  type ChatMessage,
  type ToolEvent,
} from "./ChatMessage";

const SUGGESTED_PROMPTS = [
  "Who's in today?",
  "What does Bruno eat?",
  "Mark Rex as checked in",
  "Symptoms of heatstroke in dogs?",
];

// thread_id per PRD line 353: staff_{staff_id}_{YYYY_MM_DD}
function threadIdFor(staffId: number): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `staff_${staffId}_${yyyy}_${mm}_${dd}`;
}

// Web Speech API typing (browser-prefixed, not in lib.dom).
type SpeechRecognitionLike = {
  start(): void;
  stop(): void;
  abort(): void;
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((ev: any) => void) | null;
  onend: (() => void) | null;
  onerror: ((ev: any) => void) | null;
};

function getSpeechCtor(): { new (): SpeechRecognitionLike } | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export default function ChatBox() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [recording, setRecording] = useState(false);
  const [speechAvailable, setSpeechAvailable] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setSpeechAvailable(!!getSpeechCtor());
  }, []);

  // Auto-scroll to bottom whenever messages change.
  useEffect(() => {
    const el = scrollerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const user = getUser();

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || sending || !user) return;
      setSending(true);
      setInput("");

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        text: trimmed,
        tools: [],
        thinking: false,
        done: true,
      };
      const asstId = crypto.randomUUID();
      const asstMsg: ChatMessage = {
        id: asstId,
        role: "assistant",
        text: "",
        tools: [],
        thinking: true,
        done: false,
      };
      setMessages((prev) => [...prev, userMsg, asstMsg]);

      const controller = new AbortController();
      abortRef.current = controller;
      const token = getToken();

      try {
        const res = await fetch(`${API_BASE}/chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            Authorization: token ? `Bearer ${token}` : "",
          },
          body: JSON.stringify({
            message: trimmed,
            thread_id: threadIdFor(user.id),
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const errTxt = await res.text();
          updateAsst(asstId, (m) => ({
            ...m,
            thinking: false,
            done: true,
            error: `HTTP ${res.status}: ${errTxt.slice(0, 200)}`,
          }));
          return;
        }

        for await (const ev of streamSse(res, controller.signal)) {
          const d = (ev.data ?? {}) as Record<string, unknown>;
          if (ev.event === "token") {
            const piece = String(d.content ?? "");
            updateAsst(asstId, (m) => ({
              ...m,
              thinking: false,
              text: m.text + piece,
            }));
          } else if (ev.event === "tool_call") {
            const next: ToolEvent = {
              name: String(d.name ?? "tool"),
              args: (d.args as Record<string, unknown>) ?? undefined,
            };
            updateAsst(asstId, (m) => ({
              ...m,
              thinking: false,
              tools: [...m.tools, next],
            }));
          } else if (ev.event === "tool_result") {
            const name = String(d.name ?? "tool");
            const result = String(d.result_summary ?? "");
            updateAsst(asstId, (m) => {
              // Find the last in-flight call with this name; fall back to last entry.
              const tools = [...m.tools];
              for (let i = tools.length - 1; i >= 0; i--) {
                if (tools[i].name === name && tools[i].result === undefined) {
                  tools[i] = { ...tools[i], result };
                  return { ...m, tools };
                }
              }
              tools.push({ name, result });
              return { ...m, tools };
            });
          } else if (ev.event === "error") {
            updateAsst(asstId, (m) => ({
              ...m,
              thinking: false,
              error: String(d.detail ?? "Agent error"),
            }));
          } else if (ev.event === "done") {
            updateAsst(asstId, (m) => ({ ...m, thinking: false, done: true }));
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Stream error";
        updateAsst(asstId, (m) => ({
          ...m,
          thinking: false,
          done: true,
          error: msg,
        }));
      } finally {
        // Ensure the bubble stops blinking even if stream ends without a "done" event.
        updateAsst(asstId, (m) => ({ ...m, done: true }));
        abortRef.current = null;
        setSending(false);
      }
    },
    [sending, user],
  );

  const updateAsst = (id: string, fn: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)));
  };

  // Voice input
  const toggleMic = () => {
    if (!speechAvailable) return;
    if (recording) {
      recognitionRef.current?.stop();
      return;
    }
    const Ctor = getSpeechCtor();
    if (!Ctor) return;
    const r = new Ctor();
    r.continuous = false;
    r.interimResults = true;
    r.lang = "en-US";
    r.onresult = (e: any) => {
      let buf = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        buf += e.results[i][0].transcript;
      }
      setInput((prev) => (prev ? prev + " " : "") + buf);
    };
    r.onend = () => {
      setRecording(false);
      recognitionRef.current = null;
    };
    r.onerror = () => {
      setRecording(false);
      recognitionRef.current = null;
    };
    recognitionRef.current = r;
    setRecording(true);
    r.start();
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input);
  };

  return (
    <div className="mx-auto flex h-[100dvh] max-w-3xl flex-col md:h-[calc(100dvh-3.5rem)]">
      {/* Mobile-only header (desktop has the TopNav above) */}
      <header className="flex items-center justify-between border-b border-border px-4 py-3 md:hidden">
        <h1 className="text-lg font-semibold">DogBuddy</h1>
        <Link
          href="/dashboard"
          className="rounded p-1 text-muted transition hover:bg-border/40 hover:text-text"
          aria-label="Back to dashboard"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
      </header>

      <div
        ref={scrollerRef}
        className="flex-1 space-y-4 overflow-y-auto px-4 py-4 pb-32"
      >
        {messages.length === 0 ? (
          <div className="mt-12 text-center text-muted">
            <p className="mb-6 text-sm">
              Ask DogBuddy anything. Tap a suggestion to start.
            </p>
            <div className="mx-auto grid max-w-md grid-cols-1 gap-2 sm:grid-cols-2">
              {SUGGESTED_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => setInput(p)}
                  className="rounded-xl border border-border bg-surface px-3 py-2 text-left text-sm text-text transition hover:border-accent/60"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => <ChatMessageView key={m.id} msg={m} />)
        )}
      </div>

      <form
        onSubmit={onSubmit}
        className="fixed inset-x-0 bottom-14 z-20 border-t border-border bg-bg/95 px-3 py-3 backdrop-blur md:bottom-0"
      >
        <div className="mx-auto flex max-w-3xl items-center gap-2">
          {speechAvailable && (
            <button
              type="button"
              onClick={toggleMic}
              className={`shrink-0 rounded-full p-2 transition ${
                recording
                  ? "bg-danger text-white"
                  : "bg-surface text-muted hover:text-text"
              }`}
              aria-label={recording ? "Stop recording" : "Start voice input"}
            >
              {recording ? (
                <MicOff className="h-5 w-5" />
              ) : (
                <Mic className="h-5 w-5" />
              )}
            </button>
          )}
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
            placeholder={recording ? "Listening..." : "Type a message"}
            className="flex-1 rounded-full border border-border bg-surface px-4 py-2 text-text outline-none focus:border-accent disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="shrink-0 rounded-full bg-accent p-2 text-bg transition hover:opacity-90 disabled:opacity-50"
            aria-label="Send"
          >
            {sending ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
