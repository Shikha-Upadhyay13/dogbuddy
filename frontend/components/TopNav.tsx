"use client";

// Slim MOBILE-only top bar with the DogBuddy brand. Desktop uses the
// full Sidebar instead.

import Link from "next/link";
import { Dog as DogIcon } from "lucide-react";

import { getUser } from "@/lib/auth";

export default function TopNav() {
  const user = getUser();
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-bg/85 px-4 py-3 backdrop-blur md:hidden">
      <Link href="/dashboard" className="flex items-center gap-2 text-text">
        <span className="flex h-7 w-7 items-center justify-center rounded-md border border-border bg-surface text-accent">
          <DogIcon className="h-4 w-4" />
        </span>
        <span className="text-sm font-semibold tracking-tight">DogBuddy</span>
      </Link>
      <span className="text-xs text-muted">{user?.name ?? "Staff"}</span>
    </header>
  );
}
