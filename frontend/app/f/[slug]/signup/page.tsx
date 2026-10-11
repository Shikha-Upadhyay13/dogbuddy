"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function FacilitySignupRedirect() {
  const params = useParams<{ slug: string }>();
  const router = useRouter();
  useEffect(() => {
    const slug = params.slug ?? "";
    router.replace(`/signup?facility=${encodeURIComponent(slug)}`);
  }, [params.slug, router]);
  return (
    <div className="flex min-h-screen items-center justify-center text-muted">
      Loading...
    </div>
  );
}
