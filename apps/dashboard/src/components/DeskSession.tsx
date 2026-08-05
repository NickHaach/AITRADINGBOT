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
    <div>
      <div className="mb-8 flex flex-col gap-4 border border-line bg-panel/40 px-5 py-4 md:flex-row md:items-end md:justify-between">
        {user ? (
          <div className="font-mono text-xs text-mist/80">
            <p className="text-signal">SIGNED IN</p>
            <p className="mt-1 text-white">
              {user.email} · {user.role}
            </p>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="grid w-full gap-3 md:max-w-xl md:grid-cols-[1fr_1fr_auto]">
            <label className="block font-mono text-[11px] uppercase tracking-wider text-mist/50">
              Email
              <input
                className="mt-1 w-full border border-line bg-ink px-3 py-2 text-sm text-white outline-none focus:border-signal"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
              />
            </label>
            <label className="block font-mono text-[11px] uppercase tracking-wider text-mist/50">
              Password
              <input
                type="password"
                className="mt-1 w-full border border-line bg-ink px-3 py-2 text-sm text-white outline-none focus:border-signal"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </label>
            <button
              type="submit"
              className="border border-signal px-4 py-2 font-mono text-xs uppercase tracking-wider text-signal hover:bg-signal/10 md:self-end"
              disabled={loading}
            >
              Sign in
            </button>
          </form>
        )}
        {user ? (
          <button
            type="button"
            onClick={onSignOut}
            className="border border-line px-4 py-2 font-mono text-xs uppercase tracking-wider text-mist/70 hover:text-white"
          >
            Sign out
          </button>
        ) : null}
      </div>
      {error ? <p className="mb-4 font-mono text-xs text-danger">{error}</p> : null}
      {!user ? (
        <p className="mb-8 border border-line bg-panel/60 p-6 text-sm text-mist/80">
          Sign in to load the paper book and live recommendations through the API gateway.
          Dev admin: <span className="font-mono text-signal">admin@local.dev</span>
        </p>
      ) : null}
      {children({ user, portfolio, recs, loading })}
    </div>
  );
}
