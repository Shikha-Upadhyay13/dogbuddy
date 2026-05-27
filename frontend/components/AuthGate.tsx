"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getUser, isLoggedIn } from "@/lib/auth";

// Per-role home routes. Staff lands on the operational dashboard;
// owners land on their booking/dog-management view.
function homeForRole(role: string | undefined): string {
  return role === "staff" ? "/dashboard" : "/owner/dashboard";
}

// Paths that don't require auth.
const PUBLIC_PATHS = ["/login", "/signup"];

// Client-only gate: routes users based on auth state AND role.
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const loggedIn = isLoggedIn();
    const user = getUser();
    const onPublic = PUBLIC_PATHS.includes(pathname ?? "");

    // Not logged in + on a private path -> bounce to /login
    if (!loggedIn && !onPublic) {
      router.replace("/login");
      return;
    }

    // Logged in + on a public path -> bounce to their role home
    if (loggedIn && onPublic) {
      router.replace(homeForRole(user?.role));
      return;
    }

    // Role guard. /chat is open to both roles (the agent gates its tools
    // by role server-side). Owner UI is /owner/*; staff UI is the listed
    // top-level routes.
    const STAFF_ONLY_PREFIXES = [
      "/dashboard",
      "/health",
      "/incidents",
      "/owners",
    ];
    if (loggedIn && user) {
      // Match /owner exactly or /owner/* -- but NOT /owners (plural,
      // staff-only directory page). String.startsWith("/owner") would
      // catch both.
      const isOwnerOnly =
        pathname === "/owner" || pathname?.startsWith("/owner/");
      const isStaffOnly = STAFF_ONLY_PREFIXES.some((p) =>
        pathname?.startsWith(p),
      );
      if (user.role === "staff" && isOwnerOnly) {
        router.replace("/dashboard");
        return;
      }
      if (user.role === "owner" && isStaffOnly) {
        router.replace("/owner/dashboard");
        return;
      }
    }

    setReady(true);
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
