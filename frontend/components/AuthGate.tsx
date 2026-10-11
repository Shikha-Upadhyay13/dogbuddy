"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { clearAuth, homeForRole, isStaffRole, saveUser } from "@/lib/auth";
import type { SessionUser } from "@/lib/types";

function isPublic(pathname: string | null): boolean {
  if (!pathname) return false;
  return (
    pathname === "/login" ||
    pathname === "/signup" ||
    pathname === "/reset-password" ||
    pathname === "/accept-invite" ||
    pathname.startsWith("/f/")
  );
}

// Client-only gate: confirms the cookie session, then routes by role.
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const onPublic = isPublic(pathname);

    (async () => {
      try {
        const me = await api.get<SessionUser>("/auth/me");
        if (cancelled) return;
        saveUser(me);
        if (onPublic) {
          router.replace(homeForRole(me.role));
          return;
        }
        const STAFF_ONLY_PREFIXES = [
          "/dashboard",
          "/health",
          "/incidents",
          "/owners",
          "/queue",
          "/kennels",
          "/invoices",
        ];
        const isOwnerOnly =
          pathname === "/owner" || pathname?.startsWith("/owner/");
        const isStaffOnly = STAFF_ONLY_PREFIXES.some((p) =>
          pathname?.startsWith(p),
        );
        if (isStaffRole(me.role) && isOwnerOnly) {
          router.replace("/dashboard");
          return;
        }
        if (!isStaffRole(me.role) && isStaffOnly) {
          router.replace("/owner/dashboard");
          return;
        }
        setReady(true);
      } catch {
        if (cancelled) return;
        clearAuth();
        if (!onPublic) {
          router.replace("/login");
          return;
        }
        setReady(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted">
        Loading...
      </div>
    );
  }
  return <>{children}</>;
}
