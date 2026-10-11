// Session user is cached in sessionStorage. The credential itself is an
// httpOnly cookie set by the API, never a token in localStorage.

import type { SessionUser } from "./types";

const USER_KEY = "dogbuddy_user";

const isBrowser = () => typeof window !== "undefined";

export function isStaffRole(role: string | undefined): boolean {
  return role === "admin" || role === "attendant";
}

export function homeForRole(role: string | undefined): string {
  return isStaffRole(role) ? "/dashboard" : "/owner/dashboard";
}

export function getUser(): SessionUser | null {
  if (!isBrowser()) return null;
  const raw = window.sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}

export function saveUser(user: SessionUser): void {
  if (!isBrowser()) return;
  window.sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  if (!isBrowser()) return;
  window.sessionStorage.removeItem(USER_KEY);
  window.localStorage.removeItem("dogbuddy_token");
  window.localStorage.removeItem("dogbuddy_user");
}

export function isLoggedIn(): boolean {
  return !!getUser();
}
