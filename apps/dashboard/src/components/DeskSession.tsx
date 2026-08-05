"use client";

import { FormEvent, ReactNode, useEffect, useState } from "react";
import {
  canRunCycle,
  clearAuth,
  storeUser,
  type AuthUser,
} from "@/lib/auth";
import {
  demoPortfolio,
  demoRecommendations,
  fetchMe,
  fetchPortfolioAuthed,
  fetchRecommendationsAuthed,
  runPortfolioCycle,
  sessionLogin,
  sessionLogout,
  type CycleResult,
  type DemoRecommendation,
  type LivePortfolio,
} from "@/lib/api";

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
  const [running, setRunning] = useState(false);
  const [lastCycle, setLastCycle] = useState<CycleResult | null>(null);
  const [portfolio, setPortfolio] = useState<LivePortfolio>({
    ...demoPortfolio(),
    source: "demo",
  });
  const [recs, setRecs] = useState<DemoRecommendation[]>(demoRecommendations());

  useEffect(() => {
    void (async () => {
      try {
        const me = await fetchMe();
        if (me) {
          const authUser: AuthUser = me;
          storeUser(authUser);
          setUser(authUser);
          await loadBook();
          setLoading(false);
          return;
        }
      } catch {
        /* fall through */
      }
      clearAuth();
      setUser(null);
      setLoading(false);
    })();
  }, []);

  async function loadBook() {
    const [book, recommendations] = await Promise.all([
      fetchPortfolioAuthed(),
      fetchRecommendationsAuthed(),
    ]);
    setPortfolio(book);
    setRecs(recommendations.length ? recommendations : demoRecommendations());
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const me = await sessionLogin(email, password);
      storeUser(me);
      setUser(me);
      await loadBook();
    } catch (err) {
      clearAuth();
      setUser(null);
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  async function onSignOut() {
    await sessionLogout();
    clearAuth();
    setUser(null);
    setLastCycle(null);
    setPortfolio({ ...demoPortfolio(), source: "demo" });
    setRecs(demoRecommendations());
  }

  async function onRunCycle() {
    setError(null);
    setRunning(true);
    try {
      const result = await runPortfolioCycle();
      setLastCycle(result);
      await loadBook();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cycle failed");
    } finally {
      setRunning(false);
    }
  }

  const showRun = canRunCycle(user?.role);

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
            <div className="flex flex-wrap items-center gap-2 self-start md:self-center">
              {showRun ? (
                <button
                  type="button"
                  onClick={onRunCycle}
                  className="desk-btn desk-btn-primary"
                  disabled={running || loading}
                >
                  {running ? "Running…" : "Run cycle"}
                </button>
              ) : null}
              <button type="button" onClick={onSignOut} className="desk-btn desk-btn-ghost">
                Sign out
              </button>
            </div>
          ) : null}
        </div>
        {error ? <p className="mt-3 font-mono text-[11px] text-danger">{error}</p> : null}
        {lastCycle ? (
          <p className="mt-3 font-mono text-[11px] text-mist/55">
            Last cycle · approved {lastCycle.approved_trades ?? 0} · rejected{" "}
            {lastCycle.rejected_trades ?? 0} · closed {lastCycle.closed_outcomes ?? 0} · open lots{" "}
            {lastCycle.open_lots ?? 0}
          </p>
        ) : null}
        {!user && !loading ? (
          <p className="mt-3 text-sm text-mist/55">
            Sign in for the live paper book. Dev admin{" "}
            <span className="font-mono text-signal/80">admin@local.dev</span>
          </p>
        ) : null}
      </div>

      <div
        className={`transition-opacity duration-300 ${loading || running ? "opacity-55" : "opacity-100"}`}
        style={{ transitionTimingFunction: "var(--ease-out)" }}
      >
        {children({ user, portfolio, recs, loading })}
      </div>
    </div>
  );
}
