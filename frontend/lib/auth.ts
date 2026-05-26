// JWT + user persistence in localStorage. Per PRD Section 8 "Behavior".
// Note: localStorage is XSS-vulnerable — accepted prototype limitation
// (PRD Section 13).

import type { Staff } from "./types";

const TOKEN_KEY = "dogbuddy_token";
const USER_KEY = "dogbuddy_user";

const isBrowser = () => typeof window !== "undefined";

export function getToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getUser(): Staff | null {
  if (!isBrowser()) return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Staff;
  } catch {
    return null;
  }
}

export function saveAuth(token: string, staff: Staff): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(staff));
}

export function clearAuth(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export function isLoggedIn(): boolean {
  return !!getToken();
}
