"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getUser, isLoggedIn } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();
  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    const user = getUser();
    router.replace(user?.role === "staff" ? "/dashboard" : "/owner/dashboard");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center text-muted">
      Loading DogBuddy...
    </div>
  );
}
