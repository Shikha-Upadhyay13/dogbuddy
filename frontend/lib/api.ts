// Native fetch wrapper that attaches the JWT and parses JSON.
// Throws ApiError on non-2xx so callers can inline-handle it.

import { getToken, clearAuth } from "./auth";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(`HTTP ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

type ApiOptions = RequestInit & { skipAuth?: boolean };

async function request<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { skipAuth = false, headers, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...(headers as Record<string, string> | undefined),
  };
  if (!skipAuth) {
    const token = getToken();
    if (token) finalHeaders.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}${path}`, { ...rest, headers: finalHeaders });

  if (res.status === 204) {
    return undefined as T;
  }

  const text = await res.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!res.ok) {
    if (res.status === 401 && !skipAuth) {
      // Token is invalid — drop it so /login can take over on next render.
      clearAuth();
    }
    const detail =
      parsed && typeof parsed === "object" && "detail" in parsed
        ? String((parsed as { detail: unknown }).detail)
        : String(parsed || res.statusText);
    throw new ApiError(res.status, detail);
  }

  return parsed as T;
}

export const api = {
  get: <T>(path: string, opts: ApiOptions = {}) =>
    request<T>(path, { method: "GET", ...opts }),
  post: <T>(path: string, body: unknown, opts: ApiOptions = {}) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body), ...opts }),
  patch: <T>(path: string, body: unknown, opts: ApiOptions = {}) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body), ...opts }),
};

export { BASE as API_BASE };
