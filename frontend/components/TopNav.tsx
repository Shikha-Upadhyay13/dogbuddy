"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Dog as DogIcon, Home, MessageSquare, LogOut } from "lucide-react";

import { clearAuth, getUser } from "@/lib/auth";

const TABS = [
  { href: "/dashboard", label: "Dashboard", Icon: Home },
  { href: "/chat", label: "Chat", Icon: MessageSquare },
] as const;

// Desktop top navigation. Hidden on mobile (BottomNav takes over there).
export default function TopNav() {
  const pathname = usePathname();
  const router = useRouter();
  const user = getUser();

  const onLogout = () => {
    clearAuth();
    router.replace("/login");
  };

  return (
    <header className="sticky top-0 z-30 hidden border-b border-border bg-bg/85 backdrop-blur md:block">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <Link href="/dashboard" className="flex items-center gap-2 text-accent">
          <DogIcon className="h-6 w-6" />
          <span className="text-lg font-semibold tracking-tight text-text">
            DogBuddy
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          {TABS.map(({ href, label, Icon }) => {
            const active = pathname?.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition ${
                  active
                    ? "bg-accent/10 text-accent"
                    : "text-muted hover:bg-border/40 hover:text-text"
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3 text-sm">
          <span className="text-muted">{user?.name ?? "Staff"}</span>
          <button
            onClick={onLogout}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-text transition hover:border-accent hover:text-accent"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
