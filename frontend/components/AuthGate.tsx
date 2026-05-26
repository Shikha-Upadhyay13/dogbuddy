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

    // Role guard: owner trying to hit staff-only routes, or vice versa.
    if (loggedIn && user) {
      const isOwnerRoute = pathname?.startsWith("/owner");
      const isStaffRoute =
        pathname?.startsWith("/dashboard") || pathname?.startsWith("/chat");
      if (user.role === "staff" && isOwnerRoute) {
        router.replace("/dashboard");
        return;
      }
      if (user.role === "owner" && isStaffRoute) {
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
