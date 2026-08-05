"use client";

import { FormEvent, ReactNode, useEffect, useState } from "react";
import {
  clearAuth,
  getAccessToken,
  getStoredUser,
  storeAuth,
  type AuthUser,
} from "@/lib/auth";
import {
  demoPortfolio,
  demoRecommendations,
  fetchPortfolioAuthed,
  fetchRecommendationsAuthed,
  loginRequest,
  type DemoRecommendation,
  type LivePortfolio,
} from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function DeskSession({
  children,
}: {
  children: (ctx: {
    user: AuthUser | null;
    portfolio: LivePortfolio;
    recs: DemoRecommendation[];
    loading: boolean;
  }) => ReactNode;
}) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [email, setEmail] = useState("admin@local.dev");
  const [password, setPassword] = useState("ChangeMeAdmin123!");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [portfolio, setPortfolio] = useState<LivePortfolio>({
    ...demoPortfolio(),
    source: "demo",
  });
  const [recs, setRecs] = useState<DemoRecommendation[]>(demoRecommendations());

  useEffect(() => {
    const token = getAccessToken();
    const stored = getStoredUser();
    if (!token || !stored) {
      setLoading(false);
      return;
    }
    setUser(stored);
    void loadBook(token).finally(() => setLoading(false));
  }, []);

  async function loadBook(token: string) {
    const [book, recommendations] = await Promise.all([
      fetchPortfolioAuthed(token),
      fetchRecommendationsAuthed(token),
    ]);
    setPortfolio(book);
    setRecs(recommendations.length ? recommendations : demoRecommendations());
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const tokens = await loginRequest(email, password);
      const meRes = await fetch(`${API_URL}/v1/me`, {
        headers: { Authorization: `Bearer ${tokens.access_token}` },
        cache: "no-store",
      });
      if (!meRes.ok) throw new Error("Could not load profile");
      const me = (await meRes.json()) as AuthUser;
      storeAuth(tokens.access_token, tokens.refresh_token, me);
      setUser(me);
      await loadBook(tokens.access_token);
    } catch (err) {
      clearAuth();
      setUser(null);
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  function onSignOut() {
    clearAuth();
    setUser(null);
    setPortfolio({ ...demoPortfolio(), source: "demo" });
    setRecs(demoRecommendations());
  }

  return (
    <div className="fade-up fade-up-delay-1">
      <div className="surface mb-10 px-5 py-4 md:px-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          {user ? (
            <div className="flex items-center gap-3">
              <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-signal" />
              <div className="font-mono text-xs leading-relaxed">
                <p className="tracking-[0.18em] text-signal">SESSION</p>
                <p className="mt-0.5 text-white/90">
                  {user.email}
                  <span className="text-mist/40"> · </span>
                  <span className="text-mist/70">{user.role}</span>
                </p>
              </div>
            </div>
          ) : (
            <form
              onSubmit={onSubmit}
              className="grid w-full gap-3 md:max-w-2xl md:grid-cols-[1fr_1fr_auto] md:items-end"
            >
              <label className="block font-mono text-[10px] uppercase tracking-[0.16em] text-mist/45">
                Email
                <input
                  className="desk-input mt-1.5"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                />
              </label>
              <label className="block font-mono text-[10px] uppercase tracking-[0.16em] text-mist/45">
                Password
                <input
                  type="password"
                  className="desk-input mt-1.5"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
              </label>
              <button type="submit" className="desk-btn desk-btn-primary md:mb-px" disabled={loading}>
                {loading ? "…" : "Sign in"}
              </button>
            </form>
          )}
          {user ? (
            <button type="button" onClick={onSignOut} className="desk-btn desk-btn-ghost self-start md:self-center">
              Sign out
            </button>
          ) : null}
        </div>
        {error ? (
          <p className="mt-3 font-mono text-[11px] text-danger">{error}</p>
        ) : null}
        {!user && !loading ? (
          <p className="mt-3 text-sm text-mist/55">
            Sign in for the live paper book. Dev admin{" "}
            <span className="font-mono text-signal/80">admin@local.dev</span>
          </p>
        ) : null}
      </div>

      <div
        className={`transition-opacity duration-300 ${loading ? "opacity-50" : "opacity-100"}`}
        style={{ transitionTimingFunction: "var(--ease-out)" }}
      >
        {children({ user, portfolio, recs, loading })}
      </div>
    </div>
  );
}
