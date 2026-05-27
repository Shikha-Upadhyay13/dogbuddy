"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";
import {
  Dog as DogIcon,
  Home,
  MessageSquare,
  LogOut,
  PawPrint,
  CalendarDays,
  Plus,
  Trash2,
  Stethoscope,
} from "lucide-react";

import { clearAuth, getUser } from "@/lib/auth";
import {
  CHATS_CHANGED_EVENT,
  cacheKeyForThread,
  listChats,
  notifyChatsChanged,
  threadIdFor,
  type ChatSummary,
} from "@/lib/chats";
import Notifications from "./Notifications";

const STAFF_TABS = [
  { href: "/dashboard", label: "Today", Icon: Home, hint: "D" },
  { href: "/health", label: "Health", Icon: Stethoscope, hint: "H" },
  { href: "/chat", label: "Chat", Icon: MessageSquare, hint: "C" },
] as const;

const OWNER_TABS = [
  { href: "/owner/dashboard", label: "My dogs", Icon: PawPrint, hint: "D" },
  { href: "/owner/book", label: "Book a stay", Icon: CalendarDays, hint: "B" },
  { href: "/chat", label: "Chat", Icon: MessageSquare, hint: "C" },
] as const;

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const search = useSearchParams();
  const [user] = useState(() => getUser());
  const role = user?.role ?? "staff";
  const tabs = role === "owner" ? OWNER_TABS : STAFF_TABS;
  const home = role === "owner" ? "/owner/dashboard" : "/dashboard";
  const sectionLabel = role === "owner" ? "Account" : "Workspace";
  const roleBadge = role === "owner" ? "owner" : "staff";

  const onChat = pathname?.startsWith("/chat");
  const activeThread = search?.get("thread") ?? "";

  const [chats, setChats] = useState<ChatSummary[]>([]);
  useEffect(() => {
    if (!user || !onChat) return;
    const refresh = () => setChats(listChats(user.id));
    refresh();
    window.addEventListener(CHATS_CHANGED_EVENT, refresh);
    return () => window.removeEventListener(CHATS_CHANGED_EVENT, refresh);
  }, [user, onChat]);

  const switchTo = (threadId: string) => {
    router.push(`/chat?thread=${encodeURIComponent(threadId)}`);
  };

  const newChat = () => {
    if (!user) return;
    const id = threadIdFor(user.id, String(Date.now()));
    router.push(`/chat?thread=${encodeURIComponent(id)}`);
  };

  const deleteChat = (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!user) return;
    try {
      window.localStorage.removeItem(cacheKeyForThread(threadId));
    } catch {
      /* ignore */
    }
    notifyChatsChanged();
    if (threadId === activeThread) {
      const remaining = listChats(user.id);
      if (remaining.length > 0) {
        router.push(`/chat?thread=${encodeURIComponent(remaining[0].threadId)}`);
      } else {
        router.push("/chat");
      }
    }
  };

  const onLogout = () => {
    clearAuth();
    router.replace("/login");
  };

  const initial = user?.name?.[0]?.toUpperCase() ?? "?";

  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-border bg-bg/80 backdrop-blur md:flex">
      {/* Brand */}
      <Link
        href={home}
        className="flex items-center gap-2 border-b border-border px-5 py-4 text-text"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-md border border-border bg-surface text-accent">
          <DogIcon className="h-4 w-4" />
        </span>
        <span className="text-sm font-semibold tracking-tight">DogBuddy</span>
        <span className="ml-auto rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-[10px] text-muted">
          {roleBadge}
        </span>
      </Link>

      {/* Nav + (when on /chat) chat history */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
        <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted">
          {sectionLabel}
        </p>
        {tabs.map(({ href, label, Icon, hint }) => {
          const active = pathname?.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`group flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition ${
                active
                  ? "bg-surface text-text"
                  : "text-muted hover:bg-surface/60 hover:text-text"
              }`}
            >
              <Icon
                className={`h-4 w-4 ${active ? "text-accent" : "text-muted group-hover:text-text"}`}
              />
              <span className="flex-1">{label}</span>
              <kbd className="hidden rounded border border-border bg-surface px-1 font-mono text-[10px] text-muted group-hover:text-text md:inline">
                {hint}
              </kbd>
            </Link>
          );
        })}

        {/* Chat history — only visible on /chat */}
        {onChat && (
          <>
            <div className="flex items-center justify-between px-2 pb-1 pt-5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">
                Chats
              </span>
              <button
                onClick={newChat}
                className="inline-flex items-center gap-1 rounded-md border border-border bg-surface px-1.5 py-0.5 text-[10px] text-text transition hover:border-accent hover:text-accent"
                title="Start a new chat"
              >
                <Plus className="h-3 w-3" />
                New
              </button>
            </div>
            {chats.length === 0 ? (
              <p className="px-2 py-2 text-xs text-muted">No chats yet.</p>
            ) : (
              <ul className="space-y-0.5">
                {chats.map((c) => {
                  const active = c.threadId === activeThread;
                  return (
                    <li key={c.threadId}>
                      <div
                        onClick={() => switchTo(c.threadId)}
                        className={`group flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 transition ${
                          active
                            ? "bg-surface text-text"
                            : "text-muted hover:bg-surface/60 hover:text-text"
                        }`}
                      >
                        <MessageSquare
                          className={`h-3.5 w-3.5 shrink-0 ${active ? "text-accent" : ""}`}
                        />
                        <span className="min-w-0 flex-1 truncate text-xs">
                          {c.title}
                        </span>
                        <span className="shrink-0 font-mono text-[10px] text-muted">
                          {c.msgCount}
                        </span>
                        <button
                          onClick={(e) => deleteChat(c.threadId, e)}
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
          </>
        )}
      </nav>

      {/* User */}
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-accent/40 to-accent/10 font-semibold text-text">
            {initial}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-text">
              {user?.name ?? "Staff"}
            </p>
            <p className="truncate font-mono text-[11px] text-muted">
              {user?.phone ?? ""}
            </p>
          </div>
          <Notifications />
          <button
            onClick={onLogout}
            className="rounded-md p-1.5 text-muted transition hover:bg-surface hover:text-text"
            aria-label="Logout"
            title="Logout"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
