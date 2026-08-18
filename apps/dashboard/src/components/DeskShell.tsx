"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  canRunCycle,
  clearAuth,
  storeUser,
  type AuthUser,
} from "@/lib/auth";
import {
  connectAlpacaBroker,
  demoPortfolio,
  demoRecommendations,
  disconnectAlpacaBroker,
  fetchBrokerStatus,
  fetchMe,
  fetchPortfolioAuthed,
  fetchRecommendationsAuthed,
  runPortfolioCycle,
  sessionLogin,
  sessionLogout,
  type Announcement,
  type BrokerStatus,
  type CycleResult,
  type DemoRecommendation,
  type LivePortfolio,
  type NewsArticle,
} from "@/lib/api";
import { MarketsBoard } from "@/components/MarketsBoard";
import { TickerTape } from "@/components/TickerTape";
import { ActivityPanel } from "@/components/ActivityPanel";

const RISK_LIMITS = {
  maxPositionPct: 0.05,
  dailyLossPct: 0.02,
  maxDrawdownPct: 0.15,
  maxSectorPct: 0.25,
};

type Workspace = "floor" | "book" | "intel" | "activity" | "broker";

function badgeClass(level: string): string {
  const v = level.toLowerCase();
  if (v.includes("critical") || v.includes("very_bearish") || v === "breaking" || v === "sell") {
    return "text-danger";
  }
  if (v.includes("high") || v.includes("bearish") || v === "hold") return "text-warn";
  if (v.includes("bullish") || v === "buy") return "text-gain";
  return "text-mist/55";
}

function actionRail(action: string): string {
  const v = action.toLowerCase();
  if (v === "buy") return "action-rail action-rail-buy";
  if (v === "sell") return "action-rail action-rail-sell";
  return "action-rail action-rail-hold";
}

function pct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

function money(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

function moneyExact(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

type Health = {
  api: boolean;
  news: boolean;
  market: boolean;
  announcements: boolean;
  portfolio: boolean;
};

export function DeskShell({
  news,
  announcements,
  health,
}: {
  news: NewsArticle[];
  announcements: Announcement[];
  health: Health;
}) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [email, setEmail] = useState("admin@local.dev");
  const [password, setPassword] = useState("ChangeMeAdmin123!");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [lastCycle, setLastCycle] = useState<CycleResult | null>(null);
  const [workspace, setWorkspace] = useState<Workspace>("floor");
  const [activityKey, setActivityKey] = useState(0);
  const [portfolio, setPortfolio] = useState<LivePortfolio>({
    ...demoPortfolio(),
    source: "demo",
  });
  const [recs, setRecs] = useState<DemoRecommendation[]>(demoRecommendations());
  const [broker, setBroker] = useState<BrokerStatus | null>(null);
  const [alpacaKey, setAlpacaKey] = useState("");
  const [alpacaSecret, setAlpacaSecret] = useState("");
  const [brokerBusy, setBrokerBusy] = useState(false);
  const [connectMode, setConnectMode] = useState<"paper" | "live">("paper");
  const [liveConfirm, setLiveConfirm] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        const me = await fetchMe();
        if (me) {
          storeUser(me);
          setUser(me);
          await loadBook();
          setLoading(false);
          return;
        }
      } catch {
        /* guest */
      }
      setLoading(false);
    })();
  }, []);

  async function loadBook() {
    const [book, recommendations, brokerStatus] = await Promise.all([
      fetchPortfolioAuthed(),
      fetchRecommendationsAuthed(),
      fetchBrokerStatus(),
    ]);
    setPortfolio(book);
    setRecs(recommendations.length ? recommendations : demoRecommendations());
    setBroker(brokerStatus);
    setActivityKey((k) => k + 1);
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
    setBroker(null);
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
      setActivityKey((k) => k + 1);
      setWorkspace("floor");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cycle failed");
    } finally {
      setRunning(false);
    }
  }

  async function onConnectBroker(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const wantLive = connectMode === "live";
    if (wantLive) {
      if (!broker?.live_connect_allowed) {
        setError(
          "Live locked: set EXECUTION_MODE=live and ENABLE_LIVE_TRADING=true in .env, then restart the desk.",
        );
        return;
      }
      if (liveConfirm.trim().toUpperCase() !== "LIVE") {
        setError('Type LIVE in the confirm box to arm real-money trading.');
        return;
      }
      const ok = window.confirm(
        "Connect LIVE Alpaca?\n\nOrders from Run cycle / Autopilot will use REAL MONEY.\n\nOnly continue if you funded a live account and intend to trade with it.",
      );
      if (!ok) return;
    }
    setBrokerBusy(true);
    try {
      const status = await connectAlpacaBroker({
        api_key: alpacaKey,
        secret_key: alpacaSecret,
        paper: !wantLive,
      });
      setBroker(status);
      setAlpacaKey("");
      setAlpacaSecret("");
      setLiveConfirm("");
      setConnectMode("paper");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Broker connect failed");
    } finally {
      setBrokerBusy(false);
    }
  }

  async function onDisconnectBroker() {
    setError(null);
    setBrokerBusy(true);
    try {
      const status = await disconnectAlpacaBroker();
      setBroker(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Disconnect failed");
    } finally {
      setBrokerBusy(false);
    }
  }

  const showRun = canRunCycle(user?.role);
  const modeLabel = broker?.live_trading_armed
    ? "Live"
    : broker?.connected
      ? "Alpaca paper"
      : "Local paper";
  const modeTone = broker?.live_trading_armed
    ? "text-danger border-danger/35"
    : broker?.connected
      ? "text-signal border-signal/35"
      : "text-warn border-warn/30";

  const pnl = portfolio.totalPnl ?? 0;
  const tabs: { id: Workspace; label: string }[] = [
    { id: "floor", label: "Trade floor" },
    { id: "book", label: "Book" },
    { id: "intel", label: "Intelligence" },
    { id: "activity", label: "Activity" },
    { id: "broker", label: "Broker" },
  ];

  return (
    <div className="desk-terminal min-h-screen">
      {/* Sticky command bar — Thinkorswim / IBKR */}
      <header className="desk-command sticky top-0 z-40">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3 px-4 py-2.5 md:px-6">
          <div className="flex items-center gap-4 md:gap-6">
            <p className="brand-mark !text-[0.7rem] !tracking-[0.22em]">Aether Desk</p>
            <div className="hidden items-baseline gap-3 border-l border-line pl-4 sm:flex md:pl-6">
              <div>
                <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-mist/35">Equity</p>
                <p className="font-display text-xl tabular-nums tracking-tight text-ivory md:text-[1.35rem]">
                  {user ? moneyExact(portfolio.equity) : "—"}
                </p>
              </div>
              <p
                className={`font-mono text-[11px] tabular-nums ${
                  !user ? "text-mist/30" : pnl >= 0 ? "text-gain" : "text-danger"
                }`}
              >
                {user ? `${pnl >= 0 ? "+" : ""}${moneyExact(pnl)}` : ""}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className={`hidden border px-2 py-1 font-mono text-[9px] uppercase tracking-[0.16em] sm:inline ${modeTone}`}>
              {modeLabel}
            </span>
            <div className="hidden items-center font-mono text-[9px] uppercase tracking-[0.12em] text-mist/40 lg:flex">
              <StatusDot ok={health.api} label="API" />
              <StatusDot ok={health.market} label="Mkt" />
              <StatusDot ok={health.news} label="News" />
              <StatusDot ok={health.portfolio} label="Book" />
            </div>
            {user ? (
              <>
                {showRun ? (
                  <button
                    type="button"
                    onClick={onRunCycle}
                    className="desk-btn desk-btn-primary !px-4 !py-2 !text-[10px]"
                    disabled={running || loading}
                  >
                    {running ? "Running…" : "Run cycle"}
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={onSignOut}
                  className="desk-btn desk-btn-ghost !px-3 !py-2 !text-[10px]"
                >
                  Sign out
                </button>
              </>
            ) : null}
          </div>
        </div>
        <TickerTape />
      </header>

      <main className="mx-auto max-w-[1400px] px-4 pb-20 pt-8 md:px-6 md:pt-10">
        {/* Account strip — Robinhood hero number + IBKR density */}
        <section className="fade-up mb-6 grid gap-0 border border-line bg-[rgba(10,16,22,0.55)] md:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div className="border-b border-line px-5 py-5 md:border-b-0 md:border-r md:px-6 md:py-6">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/35">
              Net liquidation · USD
            </p>
            <p className="mt-2 font-display text-[2.75rem] font-medium leading-none tracking-tight tabular-nums text-ivory md:text-[3.25rem]">
              {user ? money(portfolio.equity) : "—"}
            </p>
            <p className="mt-3 font-mono text-[11px] text-mist/45">
              {user ? (
                <>
                  <span className={pnl >= 0 ? "text-gain" : "text-danger"}>
                    {pnl >= 0 ? "+" : ""}
                    {moneyExact(pnl)}
                  </span>
                  <span className="text-mist/30"> · total PnL · </span>
                  <span className={portfolio.drawdown > 0 ? "text-danger" : "text-mist/50"}>
                    {pct(portfolio.drawdown)} DD
                  </span>
                </>
              ) : (
                "Sign in to load the book"
              )}
            </p>
          </div>
          <MetricCompact label="Cash" value={user ? money(portfolio.cash) : "—"} />
          <MetricCompact
            label="Positions"
            value={user ? String(portfolio.positions.length) : "—"}
          />
          <MetricCompact
            label="Intel feed"
            value={`${news.length} / ${announcements.length}`}
            hint="news · filings"
          />
        </section>

        {/* Session / auth */}
        <div className="fade-up fade-up-delay-1 mb-5 border border-line bg-[rgba(10,16,22,0.4)] px-4 py-4 md:px-5">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            {user ? (
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-mist/40">Session</p>
                <p className="mt-1.5 flex items-center gap-2.5 text-[14px] text-ivory">
                  <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-signal" />
                  {user.email}
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/40">
                    {user.role}
                  </span>
                </p>
              </div>
            ) : (
              <form
                onSubmit={onSubmit}
                className="grid w-full gap-3 md:max-w-xl md:grid-cols-[1fr_1fr_auto] md:items-end"
              >
                <label className="block font-mono text-[10px] uppercase tracking-[0.16em] text-mist/40">
                  Email
                  <input
                    className="desk-input mt-2"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="username"
                  />
                </label>
                <label className="block font-mono text-[10px] uppercase tracking-[0.16em] text-mist/40">
                  Password
                  <input
                    type="password"
                    className="desk-input mt-2"
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
            {lastCycle ? (
              <p className="font-mono text-[10px] tracking-wide text-mist/40 md:text-right">
                Last cycle · {lastCycle.approved_trades ?? 0} filled · {lastCycle.rejected_trades ?? 0}{" "}
                blocked · {lastCycle.signals ?? 0} signals
              </p>
            ) : null}
          </div>
          {error ? <p className="mt-3 font-mono text-[11px] text-danger">{error}</p> : null}
          {!user && !loading ? (
            <p className="mt-3 text-sm text-mist/45">
              Dev admin <span className="font-mono text-signal/85">admin@local.dev</span>
            </p>
          ) : null}
        </div>

        {/* Workspace tabs — terminal workspaces */}
        <nav className="fade-up fade-up-delay-1 mb-6 flex gap-0 overflow-x-auto border-b border-line" aria-label="Workspace">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setWorkspace(tab.id)}
              className={`shrink-0 border-b-2 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors ${
                workspace === tab.id
                  ? "border-signal text-ivory"
                  : "border-transparent text-mist/40 hover:text-mist/70"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div
          className={`transition-opacity duration-300 ${loading || running ? "opacity-50" : "opacity-100"}`}
          style={{ transitionTimingFunction: "var(--ease-out)" }}
        >
          {workspace === "floor" ? (
            <div className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(280px,0.7fr)]">
              <MarketsBoard />
              <aside className="fade-up fade-up-delay-3 space-y-5">
                <div>
                  <SectionTitle title="Order ticket" hint="AI cycle" />
                  <div className="border border-line bg-[rgba(10,16,22,0.55)] px-4 py-5">
                    <p className="text-sm leading-relaxed text-mist/60">
                      Run cycle gathers news, filings, social, and forums — then scores the book and
                      submits paper orders through risk gates.
                    </p>
                    {showRun && user ? (
                      <button
                        type="button"
                        onClick={onRunCycle}
                        className="desk-btn desk-btn-primary mt-5 w-full"
                        disabled={running || loading}
                      >
                        {running ? "Gathering intel…" : "Execute cycle"}
                      </button>
                    ) : (
                      <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.14em] text-mist/35">
                        Sign in as trader to execute
                      </p>
                    )}
                    {lastCycle?.intelligence?.sources_used?.length ? (
                      <div className="mt-5 border-t border-line pt-4">
                        <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-signal/80">
                          Sources · {lastCycle.intelligence.headline_count ?? 0} hd ·{" "}
                          {lastCycle.intelligence.social_count ?? 0} social
                        </p>
                        <p className="mt-2 font-mono text-[10px] leading-relaxed text-mist/50">
                          {(lastCycle.intelligence.sources_used || []).slice(0, 6).join(" · ")}
                        </p>
                      </div>
                    ) : null}
                    <button
                      type="button"
                      className="mt-4 font-mono text-[10px] uppercase tracking-[0.14em] text-mist/40 hover:text-signal"
                      onClick={() => setWorkspace("activity")}
                    >
                      Open activity →
                    </button>
                  </div>
                </div>

                <div>
                  <SectionTitle title="Signals" hint="explainable" />
                  {!user ? (
                    <Empty hint="Sign in for live signals." />
                  ) : (
                    <div className="space-y-2">
                      {recs.slice(0, 4).map((r) => (
                        <article
                          key={r.ticker}
                          className={`border border-line bg-[rgba(10,16,22,0.45)] px-4 py-3.5 ${actionRail(r.action)}`}
                        >
                          <div className="flex items-baseline justify-between gap-2">
                            <h3 className="font-display text-xl tracking-tight text-ivory">{r.ticker}</h3>
                            <span
                              className={`font-mono text-[10px] uppercase tracking-[0.14em] ${badgeClass(r.action)}`}
                            >
                              {r.action}
                            </span>
                          </div>
                          <p className="mt-1.5 line-clamp-2 text-[12px] leading-snug text-mist/55">{r.why}</p>
                          <div className="mt-2 flex gap-3 font-mono text-[10px] text-mist/35">
                            <span>{pct(r.confidence)}</span>
                            <span>E[r] {pct(r.expectedReturn)}</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              </aside>
            </div>
          ) : null}

          {workspace === "book" ? (
            <div className="fade-up grid gap-8 lg:grid-cols-2">
              <section>
                <SectionTitle
                  title="Positions"
                  hint={!user ? "sign in" : portfolio.source === "live" ? "live book" : "demo"}
                />
                {!user ? (
                  <Empty hint="Sign in to load the book." />
                ) : portfolio.positions.length === 0 ? (
                  <Empty hint="No open positions — run a cycle to seed the book." />
                ) : (
                  <div className="overflow-hidden border border-line">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-[rgba(5,8,12,0.4)] font-mono text-[9px] uppercase tracking-[0.14em] text-mist/35">
                        <tr className="border-b border-line">
                          <th className="px-3 py-2.5 font-medium md:px-4">Ticker</th>
                          <th className="px-3 py-2.5 font-medium md:px-4">Qty</th>
                          <th className="px-3 py-2.5 font-medium md:px-4">Last</th>
                          <th className="px-3 py-2.5 font-medium md:px-4">PnL</th>
                          <th className="px-3 py-2.5 font-medium md:px-4">Wt</th>
                        </tr>
                      </thead>
                      <tbody>
                        {portfolio.positions.map((p) => (
                          <tr key={p.ticker} className="row-slide border-b border-line/50 last:border-0">
                            <td className="px-3 py-2.5 font-medium tracking-tight text-ivory md:px-4">
                              {p.ticker}
                            </td>
                            <td className="px-3 py-2.5 font-mono text-[11px] tabular-nums text-mist/75 md:px-4">
                              {p.qty}
                            </td>
                            <td className="px-3 py-2.5 font-mono text-[11px] tabular-nums text-mist/75 md:px-4">
                              {moneyExact(p.last)}
                            </td>
                            <td
                              className={`px-3 py-2.5 font-mono text-[11px] tabular-nums md:px-4 ${
                                p.pnl >= 0 ? "text-gain" : "text-danger"
                              }`}
                            >
                              {p.pnl >= 0 ? "+" : ""}
                              {moneyExact(p.pnl)}
                            </td>
                            <td className="px-3 py-2.5 font-mono text-[11px] tabular-nums text-mist/50 md:px-4">
                              {pct(p.weight)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section>
                <SectionTitle title="Risk" hint="hard gates" />
                <ul className="divide-y divide-line border border-line">
                  <RiskRow label="Max position" value={pct(RISK_LIMITS.maxPositionPct)} ok />
                  <RiskRow label="Daily loss limit" value={pct(RISK_LIMITS.dailyLossPct)} ok />
                  <RiskRow label="Max drawdown" value={pct(RISK_LIMITS.maxDrawdownPct)} ok />
                  <RiskRow label="Max sector" value={pct(RISK_LIMITS.maxSectorPct)} ok />
                  <RiskRow
                    label="Current drawdown"
                    value={user ? pct(portfolio.drawdown) : "—"}
                    ok={!user || portfolio.drawdown < RISK_LIMITS.maxDrawdownPct}
                  />
                  <li className="flex items-center justify-between px-4 py-3 text-sm text-mist/50">
                    <span>
                      {broker?.live_trading_armed
                        ? "Live trading armed"
                        : broker?.connected
                          ? "Alpaca paper · no real money"
                          : "Live trading locked"}
                    </span>
                    <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/35">
                      kill off
                    </span>
                  </li>
                </ul>

                <div className="mt-8">
                  <SectionTitle title="All signals" hint="explainable" />
                  {!user ? (
                    <Empty hint="Sign in to load recommendations." />
                  ) : (
                    <div className="grid gap-2">
                      {recs.map((r) => (
                        <article
                          key={r.ticker}
                          className={`border border-line px-4 py-4 ${actionRail(r.action)}`}
                        >
                          <div className="flex items-baseline justify-between gap-3">
                            <h3 className="font-display text-xl tracking-tight text-ivory">{r.ticker}</h3>
                            <span
                              className={`font-mono text-[10px] uppercase tracking-[0.14em] ${badgeClass(r.action)}`}
                            >
                              {r.action}
                            </span>
                          </div>
                          <p className="mt-2 text-sm leading-relaxed text-mist/60">{r.why}</p>
                          {r.newsExcerpt || r.socialExcerpt ? (
                            <p className="mt-2 line-clamp-2 text-[12px] text-mist/40">
                              {r.newsExcerpt || r.socialExcerpt}
                            </p>
                          ) : null}
                          <div className="mt-3 flex flex-wrap gap-x-4 font-mono text-[10px] text-mist/35">
                            <span>conf {pct(r.confidence)}</span>
                            <span>E[r] {pct(r.expectedReturn)}</span>
                            {r.sources?.length ? <span>{r.sources.join(" · ")}</span> : null}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            </div>
          ) : null}

          {workspace === "intel" ? (
            <div className="fade-up space-y-8">
              {lastCycle?.intelligence ? (
                <div className="border border-line bg-[rgba(10,16,22,0.5)] px-5 py-5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-signal/80">
                    Last cycle intelligence · {lastCycle.intelligence.headline_count ?? 0} headlines ·{" "}
                    {lastCycle.intelligence.social_count ?? 0} social
                  </p>
                  <p className="mt-2 font-mono text-[11px] leading-relaxed text-mist/55">
                    {(lastCycle.intelligence.sources_used || []).join(" · ")}
                  </p>
                  {(lastCycle.intelligence.sample_headlines || []).length > 0 ? (
                    <ul className="mt-4 grid gap-2 border-t border-line pt-4 md:grid-cols-2">
                      {(lastCycle.intelligence.sample_headlines || []).slice(0, 6).map((h, i) => (
                        <li key={`${h.title}-${i}`} className="text-[13px] leading-snug text-mist/60">
                          <span className="font-mono text-[9px] uppercase tracking-wider text-signal/70">
                            {h.source || "news"}
                          </span>{" "}
                          {h.title}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}

              <div className="grid gap-10 lg:grid-cols-2">
                <section>
                  <SectionTitle title="News" hint="classified" />
                  {news.length === 0 ? (
                    <Empty hint="Start news on :8001 to populate." />
                  ) : (
                    <ul className="divide-y divide-line border border-line">
                      {news.map((article) => (
                        <li key={article.id} className="px-4 py-4">
                          <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-[9px] uppercase tracking-[0.12em]">
                            <span className="text-signal/90">{article.category}</span>
                            <span className={badgeClass(article.risk_level)}>{article.risk_level}</span>
                            <span className={badgeClass(article.sentiment)}>{article.sentiment}</span>
                          </div>
                          <h3 className="mt-2 text-[14px] leading-snug tracking-tight text-ivory">
                            {article.title}
                          </h3>
                          <p className="mt-1.5 line-clamp-2 text-[13px] leading-relaxed text-mist/50">
                            {article.body}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>

                <section>
                  <SectionTitle title="Filings" hint="impact-scored" />
                  {announcements.length === 0 ? (
                    <Empty hint="Start announcements on :8003 to populate." />
                  ) : (
                    <ul className="divide-y divide-line border border-line">
                      {announcements.map((a) => (
                        <li key={a.id} className="px-4 py-4">
                          <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-[9px] uppercase tracking-[0.12em]">
                            <span className="text-signal/90">{a.company_ticker}</span>
                            <span className="text-mist/35">{a.filing_type}</span>
                            <span className={a.impact_score >= 0 ? "text-gain" : "text-danger"}>
                              {a.impact_score >= 0 ? "+" : ""}
                              {a.impact_score.toFixed(2)}
                            </span>
                          </div>
                          <h3 className="mt-2 text-[14px] leading-snug tracking-tight text-ivory">
                            {a.title}
                          </h3>
                          {a.summary ? (
                            <p className="mt-1.5 text-[13px] leading-relaxed text-mist/50">{a.summary}</p>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>
            </div>
          ) : null}

          {workspace === "activity" ? (
            user ? (
              <ActivityPanel canTrade={!!showRun} refreshKey={activityKey} />
            ) : (
              <Empty hint="Sign in to view blotter, journal, and autopilot." />
            )
          ) : null}

          {workspace === "broker" ? (
            <section className="fade-up">
              <SectionTitle title="Broker" hint={modeLabel} />
              <div className="border border-line bg-[rgba(10,16,22,0.45)] px-5 py-6 md:px-7 md:py-7">
                {!user ? (
                  <Empty hint="Sign in to connect a broker." />
                ) : (
                  <>
                    <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                      <div className="max-w-xl">
                        <div className="flex items-center gap-2.5">
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              broker?.account_ok
                                ? "bg-signal pulse-dot"
                                : broker?.connected
                                  ? "bg-warn"
                                  : "bg-mist/35"
                            }`}
                          />
                          <p className="font-display text-2xl tracking-tight text-ivory md:text-[1.75rem]">
                            {broker?.connected
                              ? broker.account_ok
                                ? "Alpaca connected"
                                : "Keys present — verify"
                              : "Not connected"}
                          </p>
                        </div>
                        <p className="mt-3 text-sm leading-relaxed text-mist/60">
                          {broker?.connected
                            ? broker.live_trading_armed
                              ? "Real-money mode is armed. Orders go to Alpaca live."
                              : "Practice capital on Alpaca paper. Run cycle submits real paper orders."
                            : "Connect paper for practice money, or Connect live after arming dual flags in .env."}
                        </p>
                        {!broker?.connected && !broker?.live_connect_allowed ? (
                          <p className="mt-3 font-mono text-[11px] leading-relaxed text-warn/90">
                            Live connect locked until .env has EXECUTION_MODE=live and
                            ENABLE_LIVE_TRADING=true, then restart.
                          </p>
                        ) : null}
                        {broker?.account ? (
                          <p className="mt-4 font-mono text-[11px] text-mist/45">
                            Alpaca {money(Number(broker.account.equity ?? 0))} equity ·{" "}
                            {money(Number(broker.account.cash ?? 0))} cash ·{" "}
                            {broker.account.status ?? "—"}
                          </p>
                        ) : null}
                        {broker?.error ? (
                          <p className="mt-3 font-mono text-[11px] text-danger">{broker.error}</p>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap gap-2 self-start lg:self-end">
                        <a
                          href={
                            broker?.setup_url ??
                            "https://app.alpaca.markets/paper/dashboard/overview"
                          }
                          target="_blank"
                          rel="noreferrer"
                          className="desk-btn desk-btn-ghost shrink-0"
                        >
                          Open Alpaca ↗
                        </a>
                        {broker?.connected ? (
                          <button
                            type="button"
                            className="desk-btn desk-btn-ghost"
                            disabled={brokerBusy}
                            onClick={onDisconnectBroker}
                          >
                            Disconnect
                          </button>
                        ) : null}
                      </div>
                    </div>

                    {!broker?.connected ? (
                      <form
                        onSubmit={onConnectBroker}
                        className="mt-8 space-y-4 border-t border-line pt-6"
                      >
                        <div className="flex w-fit border border-line">
                          <button
                            type="button"
                            onClick={() => {
                              setConnectMode("paper");
                              setLiveConfirm("");
                            }}
                            className={`px-3.5 py-2 font-mono text-[10px] uppercase tracking-[0.14em] ${
                              connectMode === "paper"
                                ? "bg-signal text-ink"
                                : "text-mist/50 hover:text-ivory"
                            }`}
                          >
                            Paper
                          </button>
                          <button
                            type="button"
                            onClick={() => setConnectMode("live")}
                            className={`px-3.5 py-2 font-mono text-[10px] uppercase tracking-[0.14em] ${
                              connectMode === "live"
                                ? "bg-danger text-ivory"
                                : "text-mist/50 hover:text-ivory"
                            }`}
                          >
                            Live
                          </button>
                        </div>

                        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
                          <label className="block font-mono text-[10px] uppercase tracking-[0.16em] text-mist/40">
                            {connectMode === "live" ? "Live API key" : "Paper API key"}
                            <input
                              className="desk-input mt-2"
                              value={alpacaKey}
                              onChange={(e) => setAlpacaKey(e.target.value)}
                              autoComplete="off"
                              spellCheck={false}
                              placeholder="PK…"
                              required
                            />
                          </label>
                          <label className="block font-mono text-[10px] uppercase tracking-[0.16em] text-mist/40">
                            {connectMode === "live" ? "Live secret" : "Paper secret"}
                            <input
                              type="password"
                              className="desk-input mt-2"
                              value={alpacaSecret}
                              onChange={(e) => setAlpacaSecret(e.target.value)}
                              autoComplete="off"
                              required
                            />
                          </label>
                          <button
                            type="submit"
                            className={`desk-btn md:mb-px ${
                              connectMode === "live"
                                ? "border-danger/50 text-danger"
                                : "desk-btn-primary"
                            }`}
                            disabled={
                              brokerBusy ||
                              !alpacaKey ||
                              !alpacaSecret ||
                              (connectMode === "live" &&
                                (!broker?.live_connect_allowed ||
                                  liveConfirm.trim().toUpperCase() !== "LIVE"))
                            }
                          >
                            {brokerBusy
                              ? "…"
                              : connectMode === "live"
                                ? "Connect live"
                                : "Connect paper"}
                          </button>
                        </div>

                        {connectMode === "live" ? (
                          <div className="border border-danger/30 bg-danger/5 px-4 py-4">
                            <p className="text-sm leading-relaxed text-danger/90">
                              Real money. Type <span className="font-mono">LIVE</span> to enable the
                              connect button. Kill switch stays under Activity → Autopilot.
                            </p>
                            <label className="mt-3 block font-mono text-[10px] uppercase tracking-[0.16em] text-mist/40">
                              Confirm
                              <input
                                className="desk-input mt-2 max-w-xs"
                                value={liveConfirm}
                                onChange={(e) => setLiveConfirm(e.target.value)}
                                autoComplete="off"
                                spellCheck={false}
                                placeholder="Type LIVE"
                              />
                            </label>
                          </div>
                        ) : null}
                      </form>
                    ) : null}

                    {!broker?.connected ? (
                      <ol className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {[
                          "Create an Alpaca account (paper first)",
                          "Generate API Key + Secret for paper or live",
                          "Paper: Connect paper — fake money",
                          "Live: dual .env flags, restart, Connect live",
                          "Type LIVE + confirm dialog before real money",
                          "Kill switch under Activity → Autopilot",
                        ].map((step, i) => (
                          <li key={step} className="flex gap-3 text-sm text-mist/65">
                            <span className="font-mono text-[11px] tabular-nums text-signal/80">
                              {String(i + 1).padStart(2, "0")}
                            </span>
                            <span className="leading-snug">{step}</span>
                          </li>
                        ))}
                      </ol>
                    ) : null}
                  </>
                )}
              </div>
            </section>
          ) : null}
        </div>
      </main>
    </div>
  );
}

function StatusDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-1.5 py-1 text-mist/45">
      <span className={`h-1 w-1 rounded-full ${ok ? "bg-gain pulse-dot" : "bg-danger/70"}`} />
      {label}
    </span>
  );
}

function MetricCompact({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="border-b border-line px-5 py-5 last:border-b-0 md:border-b-0 md:border-r md:last:border-r-0 md:px-5 md:py-6">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/35">{label}</p>
      <p className="mt-2 font-display text-[1.65rem] font-medium tracking-tight tabular-nums text-ivory">
        {value}
      </p>
      {hint ? (
        <p className="mt-1 font-mono text-[9px] uppercase tracking-[0.12em] text-mist/30">{hint}</p>
      ) : null}
    </div>
  );
}

function SectionTitle({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="mb-4 flex items-baseline justify-between gap-3">
      <h2 className="section-title text-[1.5rem] md:text-[1.65rem]">{title}</h2>
      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/30">{hint}</span>
    </div>
  );
}

function RiskRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <li className="flex items-center justify-between px-4 py-3 text-sm">
      <span className="text-mist/60">{label}</span>
      <span className={`font-mono text-[11px] tabular-nums ${ok ? "text-gain" : "text-danger"}`}>
        {ok ? "OK" : "WATCH"} · {value}
      </span>
    </li>
  );
}

function Empty({ hint }: { hint: string }) {
  return (
    <p className="border border-dashed border-line px-5 py-10 text-center text-sm text-mist/45">{hint}</p>
  );
}
