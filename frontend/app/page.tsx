"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { homeForRole, saveUser } from "@/lib/auth";
import type { SessionUser } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  useEffect(() => {
    api
      .get<SessionUser>("/auth/me")
      .then((me) => {
        saveUser(me);
        router.replace(homeForRole(me.role));
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center text-muted">
      Loading DogBuddy...
    </div>
  );
}
