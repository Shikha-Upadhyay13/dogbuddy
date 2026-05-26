"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/auth";

// Client-only gate: redirects unauthenticated users to /login, and bounces
// logged-in users away from /login.
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const loggedIn = isLoggedIn();
    if (!loggedIn && pathname !== "/login") {
      router.replace("/login");
      return;
    }
    if (loggedIn && pathname === "/login") {
      router.replace("/dashboard");
      return;
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
