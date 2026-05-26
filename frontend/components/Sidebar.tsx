"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Dog as DogIcon,
  Home,
  MessageSquare,
  LogOut,
  Sparkles,
} from "lucide-react";

import { clearAuth, getUser } from "@/lib/auth";

const TABS = [
  { href: "/dashboard", label: "Today", Icon: Home, hint: "D" },
  { href: "/chat", label: "Chat", Icon: MessageSquare, hint: "C" },
] as const;

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const user = getUser();

  const onLogout = () => {
    clearAuth();
    router.replace("/login");
  };

  const initial = user?.name?.[0]?.toUpperCase() ?? "?";

  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-border bg-bg/80 backdrop-blur md:flex">
      {/* Brand */}
      <Link
        href="/dashboard"
        className="flex items-center gap-2 border-b border-border px-5 py-4 text-text"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-md border border-border bg-surface text-accent">
          <DogIcon className="h-4 w-4" />
        </span>
        <span className="text-sm font-semibold tracking-tight">DogBuddy</span>
        <span className="ml-auto rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-[10px] text-muted">
          v1
        </span>
      </Link>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-3 py-4">
        <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted">
          Workspace
        </p>
        {TABS.map(({ href, label, Icon, hint }) => {
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

        <p className="px-2 pb-1 pt-5 text-[10px] font-semibold uppercase tracking-wider text-muted">
          AI
        </p>
        <Link
          href="/chat"
          className="group flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm text-muted transition hover:bg-surface/60 hover:text-text"
        >
          <Sparkles className="h-4 w-4 text-accent" />
          <span>Ask DogBuddy</span>
        </Link>
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
