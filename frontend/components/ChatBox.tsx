"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Send,
  Mic,
  MicOff,
  ArrowLeft,
  Loader2,
  Sparkles,
  Plus,
  Stethoscope,
  MessageSquare,
  Trash2,
} from "lucide-react";
import Link from "next/link";

import { API_BASE } from "@/lib/api";
import { getToken, getUser } from "@/lib/auth";
import { streamSse } from "@/lib/sse";
import ChatMessageView, {
  type ChatMessage,
  type ToolEvent,
} from "./ChatMessage";

const SUGGESTED_PROMPTS = [
  { text: "Who's in today?", hint: "read facility data" },
  { text: "What does Bruno eat?", hint: "look up a dog" },
  { text: "Mark Rex as checked in", hint: "update a status" },
  { text: "Symptoms of heatstroke in dogs?", hint: "search the web" },
];

// thread_id per PRD line 353: staff_{staff_id}_{YYYY_MM_DD}.
// `sessionSuffix` lets the "+ New Chat" button start a fresh thread within
// the same day so the agent's memory resets without waiting for midnight.
function threadIdFor(staffId: number, sessionSuffix?: string): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const base = `staff_${staffId}_${yyyy}_${mm}_${dd}`;
  return sessionSuffix ? `${base}_s${sessionSuffix}` : base;
}

// Web Speech API typing (browser-prefixed, not in lib.dom).
type SpeechRecognitionLike = {
  start(): void;
  stop(): void;
  abort(): void;
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((ev: unknown) => void) | null;
  onend: (() => void) | null;
  onerror: ((ev: unknown) => void) | null;
};

function getSpeechCtor(): { new (): SpeechRecognitionLike } | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: { new (): SpeechRecognitionLike };
    webkitSpeechRecognition?: { new (): SpeechRecognitionLike };
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

// localStorage key per (staff, thread). Keyed off thread_id so each
// "+ New Chat" session gets its own cache and the agent's memory resets
// in lockstep with what the UI shows.
function cacheKeyForThread(threadId: string): string {
  return `dogbuddy_chat_${threadId}`;
}

type ChatSummary = {
  threadId: string;
  title: string;
  msgCount: number;
  sortKey: number; // newer = larger
};

// Scan localStorage for every chat thread belonging to this user. Returns
// them sorted newest-first so the chat-history rail puts the latest at top.
function listChats(userId: number): ChatSummary[] {
  if (typeof window === "undefined") return [];
  const prefix = `dogbuddy_chat_staff_${userId}_`;
  const results: ChatSummary[] = [];
  for (let i = 0; i < window.localStorage.length; i++) {
    const key = window.localStorage.key(i);
    if (!key || !key.startsWith(prefix)) continue;
    const threadId = key.slice("dogbuddy_chat_".length);
    let msgs: ChatMessage[] = [];
    try {
      msgs = JSON.parse(window.localStorage.getItem(key) || "[]");
    } catch {
      continue;
    }
    if (!Array.isArray(msgs)) continue;
    const firstUser = msgs.find((m) => m?.role === "user");
    const title = firstUser?.text?.trim().slice(0, 48) || "Empty chat";
    // Sort: explicit _s<ts> suffix wins; otherwise use date YYYYMMDD as a
    // smaller baseline so day-default threads sit below new-chat threads
    // from the same day.
    const sufMatch = threadId.match(/_s(\d+)$/);
    let sortKey: number;
    if (sufMatch) {
      sortKey = Number(sufMatch[1]);
    } else {
      const dateMatch = threadId.match(/_(\d{4})_(\d{2})_(\d{2})$/);
      sortKey = dateMatch
        ? Number(dateMatch[1] + dateMatch[2] + dateMatch[3])
        : 0;
    }
    results.push({ threadId, title, msgCount: msgs.length, sortKey });
  }
  results.sort((a, b) => b.sortKey - a.sortKey);
  return results;
}

export default function ChatBox() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hydrated, setHydrated] = useState(false);
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

  // getUser() parses fresh from localStorage on every call -- capture it
  // ONCE so the reference is stable for the lifetime of the component.
  const [user] = useState(() => getUser());

  // Active thread id. Default to today's date-based id (the natural
  // continuous-day thread). The "+ New Chat" button sets this to a new
  // value with a session suffix.
  const [threadId, setThreadId] = useState(() =>
    user ? threadIdFor(user.id) : "",
  );

  // Restore messages from the active thread's localStorage cache. Re-fires
  // when threadId changes (e.g. user hit "+ New Chat" then switched back
  // to an older thread, if we add a history list later).
  useEffect(() => {
    if (!user || !threadId) {
      setHydrated(true);
      return;
    }
    try {
      const raw = window.localStorage.getItem(cacheKeyForThread(threadId));
      if (raw) {
        const parsed = JSON.parse(raw) as ChatMessage[];
        if (Array.isArray(parsed)) {
          setMessages(
            parsed.map((m) => ({ ...m, done: true, thinking: false })),
          );
        } else {
          setMessages([]);
        }
      } else {
        setMessages([]);
      }
    } catch {
      setMessages([]);
    }
    setHydrated(true);
  }, [threadId, user]);

  // Save on every messages change once we've hydrated.
  useEffect(() => {
    if (!hydrated || !threadId) return;
    try {
      window.localStorage.setItem(
        cacheKeyForThread(threadId),
        JSON.stringify(messages),
      );
    } catch {
      /* localStorage full or unavailable */
    }
  }, [messages, hydrated, threadId]);

  const newChat = () => {
    if (!user) return;
    // Don't interrupt an in-flight stream.
    if (sending) abortRef.current?.abort();
    const suffix = String(Date.now());
    setThreadId(threadIdFor(user.id, suffix));
    setMessages([]);
    setInput("");
  };

  // Chat-history rail state. Refreshes whenever we touch localStorage
  // (mount, switch thread, message updates, delete).
  const [chats, setChats] = useState<ChatSummary[]>([]);
  useEffect(() => {
    if (!user) return;
    setChats(listChats(user.id));
  }, [user, threadId, messages]);

  const switchTo = (id: string) => {
    if (id === threadId) return;
    if (sending) abortRef.current?.abort();
    setThreadId(id);
    setInput("");
  };

  const deleteChat = (id: string) => {
    if (!user) return;
    try {
      window.localStorage.removeItem(cacheKeyForThread(id));
    } catch {
      /* ignore */
    }
    // If we deleted the active chat, pivot to the most recent remaining
    // one, or spin up a new default.
    if (id === threadId) {
      const remaining = listChats(user.id);
      if (remaining.length > 0) {
        setThreadId(remaining[0].threadId);
      } else {
        setThreadId(threadIdFor(user.id, String(Date.now())));
      }
      setMessages([]);
    }
    setChats(listChats(user.id));
  };

  useEffect(() => {
    const el = scrollerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

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
            thread_id: threadId,
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
        updateAsst(asstId, (m) => ({ ...m, done: true }));
        abortRef.current = null;
        setSending(false);
      }
    },
    [sending, user, threadId],
  );

  const updateAsst = (id: string, fn: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)));
  };

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
    r.onresult = (e: unknown) => {
      const ev = e as {
        resultIndex: number;
        results: { [k: number]: { [k: number]: { transcript: string } } } & {
          length: number;
        };
      };
      let buf = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        buf += ev.results[i][0].transcript;
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
    <div className="flex h-[100dvh] md:ml-60">
      {/* Chat-history rail (desktop only) */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-bg/60 md:flex">
        <div className="flex items-center justify-between border-b border-border px-3 py-3">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
            Chats
          </span>
          <button
            onClick={newChat}
            className="inline-flex items-center gap-1 rounded-md border border-border bg-surface px-2 py-1 text-[11px] text-text transition hover:border-accent hover:text-accent"
            title="Start a new chat"
          >
            <Plus className="h-3 w-3" />
            New
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 py-2">
          {chats.length === 0 ? (
            <p className="px-2 py-4 text-xs text-muted">No chats yet.</p>
          ) : (
            <ul className="space-y-0.5">
              {chats.map((c) => {
                const active = c.threadId === threadId;
                return (
                  <li key={c.threadId}>
                    <div
                      className={`group flex items-center gap-2 rounded-md px-2 py-1.5 transition ${
                        active
                          ? "bg-surface text-text"
                          : "text-muted hover:bg-surface/60 hover:text-text"
                      }`}
                    >
                      <button
                        onClick={() => switchTo(c.threadId)}
                        className="flex min-w-0 flex-1 items-center gap-2 text-left"
                      >
                        <MessageSquare
                          className={`h-3.5 w-3.5 shrink-0 ${active ? "text-accent" : ""}`}
                        />
                        <span className="truncate text-xs">{c.title}</span>
                        <span className="ml-auto shrink-0 font-mono text-[10px] text-muted">
                          {c.msgCount}
                        </span>
                      </button>
                      <button
                        onClick={() => deleteChat(c.threadId)}
                        className="rounded p-0.5 text-muted opacity-0 transition hover:bg-bg/60 hover:text-danger group-hover:opacity-100"
                        aria-label="Delete chat"
                        title="Delete chat"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </aside>

      {/* Main chat column */}
      <div className="flex min-w-0 flex-1 flex-col h-[100dvh]">
      {/* Mobile-only header (desktop has Sidebar) */}
      <header className="flex items-center justify-between border-b border-border bg-bg/85 px-4 py-3 backdrop-blur md:hidden">
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard"
            className="rounded p-1 text-muted transition hover:bg-border/40 hover:text-text"
            aria-label="Back to dashboard"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <h1 className="text-sm font-semibold">DogBuddy</h1>
        </div>
        <button
          onClick={newChat}
          className="inline-flex items-center gap-1 rounded-md border border-border bg-surface px-2 py-1 text-xs text-text transition hover:border-accent hover:text-accent"
          aria-label="New chat"
        >
          <Plus className="h-3.5 w-3.5" />
          New
        </button>
      </header>

      {/* Desktop chat header */}
      <header className="hidden items-center justify-between border-b border-border px-8 py-4 md:flex">
        <div>
          <h1 className="text-sm font-semibold tracking-tight text-text">
            Ask DogBuddy
          </h1>
          <p className="font-mono text-[11px] text-muted">thread · {threadId}</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Agent constellation badge — clarifies that this is a
              multi-agent setup. The main agent delegates to health_advisor
              for medical questions. */}
          <span
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1 font-mono text-[11px] text-muted"
            title="Main agent (DogBuddy) delegates to Health Advisor for medical questions"
          >
            <Sparkles className="h-3 w-3 text-accent" />
            <span className="text-text">DogBuddy</span>
            <span>+</span>
            <Stethoscope className="h-3 w-3 text-accent" />
            <span className="text-text">Health Advisor</span>
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1 font-mono text-[11px] text-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-success" /> gpt-4o-mini
          </span>
          <button
            onClick={newChat}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1 text-xs font-medium text-text transition hover:border-accent hover:text-accent"
            title="Start a new chat (resets the agent's memory)"
          >
            <Plus className="h-3.5 w-3.5" />
            New chat
          </button>
        </div>
      </header>

      {/* Messages */}
      <div
        ref={scrollerRef}
        className="flex-1 overflow-y-auto px-4 pb-40 pt-4 md:px-8 md:pb-36"
      >
        {messages.length === 0 ? (
          <div className="mx-auto mt-12 max-w-2xl">
            <div className="mb-6 flex items-center gap-2 text-accent">
              <Sparkles className="h-4 w-4" />
              <p className="text-sm font-medium">Suggestions</p>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {SUGGESTED_PROMPTS.map((p) => (
                <button
                  key={p.text}
                  onClick={() => setInput(p.text)}
                  className="group flex flex-col gap-1 rounded-lg border border-border bg-bg px-4 py-3 text-left text-sm text-text transition hover:border-accent/60 hover:bg-surface/60"
                >
                  <span className="font-medium">{p.text}</span>
                  <span className="font-mono text-[10px] uppercase tracking-wider text-muted group-hover:text-accent">
                    {p.hint}
                  </span>
                </button>
              ))}
            </div>
            <p className="mt-10 text-center text-xs text-muted">
              DogBuddy follows the medication-safety guardrail — it never
              prescribes doses.
            </p>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-5">
            {messages.map((m) => (
              <ChatMessageView key={m.id} msg={m} />
            ))}
          </div>
        )}
      </div>

      {/* Composer */}
      <form
        onSubmit={onSubmit}
        className="fixed inset-x-0 bottom-14 z-20 border-t border-border bg-bg/95 px-3 py-3 backdrop-blur md:bottom-0 md:left-[30rem] md:px-8 md:py-5"
      >
        <div className="mx-auto flex max-w-3xl items-center gap-2">
          {speechAvailable && (
            <button
              type="button"
              onClick={toggleMic}
              className={`shrink-0 rounded-md border border-border p-2 transition ${
                recording
                  ? "border-danger/40 bg-danger/10 text-danger"
                  : "bg-surface text-muted hover:border-accent/60 hover:text-text"
              }`}
              aria-label={recording ? "Stop recording" : "Start voice input"}
              title={recording ? "Stop recording" : "Voice input"}
            >
              {recording ? (
                <MicOff className="h-4 w-4" />
              ) : (
                <Mic className="h-4 w-4" />
              )}
            </button>
          )}
          <div className="flex flex-1 items-end gap-2 rounded-md border border-border bg-surface px-3 py-2 ring-accent/30 focus-within:border-accent focus-within:ring-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                // Enter sends, Shift+Enter inserts a newline.
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  if (!sending && input.trim()) send(input);
                }
              }}
              ref={(el) => {
                if (!el) return;
                el.style.height = "auto";
                el.style.height = Math.min(el.scrollHeight, 160) + "px";
              }}
              rows={1}
              disabled={sending}
              placeholder={recording ? "Listening..." : "Message DogBuddy..."}
              className="flex-1 resize-none bg-transparent text-sm leading-5 text-text outline-none placeholder:text-muted disabled:opacity-50"
            />
            <kbd
              className="hidden whitespace-nowrap rounded border border-border bg-bg/40 px-1.5 font-mono text-[10px] text-muted md:inline"
              title="Press Enter to send, Shift+Enter for a new line"
            >
              ⇧⏎ newline
            </kbd>
          </div>
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="shrink-0 rounded-md bg-accent px-3 py-2 text-bg shadow shadow-accent/20 transition hover:opacity-90 disabled:opacity-50"
            aria-label="Send"
          >
            {sending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
      </form>
      </div>
    </div>
  );
}
