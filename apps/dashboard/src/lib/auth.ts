"use client";

const USER_KEY = "aether_user";
/** Legacy keys — cleared on logout; tokens now live in HttpOnly cookies. */
const ACCESS_KEY = "aether_access";
const REFRESH_KEY = "aether_refresh";

export type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  role: string;
};

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function clearAuth(): void {
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function storeUser(user: AuthUser): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function canRunCycle(role: string | undefined | null): boolean {
  return role === "trader" || role === "admin";
}
