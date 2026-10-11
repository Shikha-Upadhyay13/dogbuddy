"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SettingsKennelsRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/kennels");
  }, [router]);
  return (
    <div className="flex min-h-screen items-center justify-center text-muted">
      Loading...
    </div>
  );
}
