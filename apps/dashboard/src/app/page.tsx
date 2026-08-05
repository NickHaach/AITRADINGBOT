import {
  RISK_LIMITS,
  fetchAnnouncements,
  fetchHealth,
  fetchNews,
} from "@/lib/api";
import { MarketChartPanel } from "@/components/MarketChartPanel";
import { DeskSession } from "@/components/DeskSession";

function badgeClass(level: string): string {
  const v = level.toLowerCase();
  if (v.includes("critical") || v.includes("very_bearish") || v === "breaking" || v === "sell") {
    return "text-danger";
  }
  if (v.includes("high") || v.includes("bearish") || v === "hold") return "text-warn";
  if (v.includes("bullish") || v === "buy") return "text-signal";
  return "text-mist/60";
}

function pct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

export default async function HomePage() {
  const [news, health, announcements] = await Promise.all([
    fetchNews(8),
    fetchHealth(),
    fetchAnnouncements(6),
  ]);

  return (
    <main className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
      <header className="fade-up mb-14 border-b border-line pb-10">
        <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-signal">Aether Desk</p>
        <h1 className="mt-4 max-w-xl text-4xl font-semibold tracking-tight text-white md:text-[3.25rem] md:leading-[1.1]">
          Investment assistant
        </h1>
        <p className="mt-4 max-w-lg text-[15px] leading-relaxed text-mist/70">
          Multi-source intelligence, risk-gated paper execution, and explainable signals.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-2 font-mono text-[11px]">
          <StatusDot ok={health.api} label="API" />
          <StatusDot ok={health.news} label="News" />
          <StatusDot ok={health.market} label="Market" />
          <StatusDot ok={health.announcements} label="Filings" />
          <StatusDot ok={health.portfolio} label="Book" />
          <span className="ml-1 border border-warn/30 px-2.5 py-1.5 tracking-[0.12em] text-warn/90">
            PAPER
          </span>
        </div>
      </header>

      <DeskSession>
        {({ user, portfolio, recs }) => (
          <>
            <section className="fade-up fade-up-delay-2 mb-12 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Metric label="Equity" value={user ? `$${portfolio.equity.toLocaleString()}` : "—"} />
              <Metric label="Cash" value={user ? `$${portfolio.cash.toLocaleString()}` : "—"} />
              <Metric label="Drawdown" value={user ? pct(portfolio.drawdown) : "—"} />
              <Metric label="News / filings" value={`${news.length} / ${announcements.length}`} />
            </section>

            <section className="mb-14">
              <MarketChartPanel ticker="AAPL" />
            </section>

            <div className="fade-up fade-up-delay-3 mb-14 grid gap-10 lg:grid-cols-2">
              <section>
                <SectionTitle
                  title="Positions"
                  hint={!user ? "sign in" : portfolio.source === "live" ? "live book" : "demo"}
                />
                {!user ? (
                  <Empty hint="Authenticate to load the paper book." />
                ) : (
                  <div className="surface overflow-hidden">
                    <table className="w-full text-left text-sm">
                      <thead className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/40">
                        <tr className="border-b border-line">
                          <th className="px-4 py-3 font-medium">Ticker</th>
                          <th className="px-4 py-3 font-medium">Qty</th>
                          <th className="px-4 py-3 font-medium">Last</th>
                          <th className="px-4 py-3 font-medium">PnL</th>
                          <th className="px-4 py-3 font-medium">Weight</th>
                        </tr>
                      </thead>
                      <tbody>
                        {portfolio.positions.map((p) => (
                          <tr key={p.ticker} className="row-slide border-b border-line/60 last:border-0">
                            <td className="px-4 py-3.5 font-medium text-white">{p.ticker}</td>
                            <td className="px-4 py-3.5 font-mono text-xs tabular-nums text-mist/80">
                              {p.qty}
                            </td>
                            <td className="px-4 py-3.5 font-mono text-xs tabular-nums text-mist/80">
                              ${p.last.toFixed(2)}
                            </td>
                            <td
                              className={`px-4 py-3.5 font-mono text-xs tabular-nums ${p.pnl >= 0 ? "text-signal" : "text-danger"}`}
                            >
                              {p.pnl >= 0 ? "+" : ""}
                              {p.pnl}
                            </td>
                            <td className="px-4 py-3.5 font-mono text-xs tabular-nums text-mist/60">
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
                <ul className="space-y-2">
                  <RiskRow label="Max position" value={pct(RISK_LIMITS.maxPositionPct)} ok />
                  <RiskRow label="Daily loss limit" value={pct(RISK_LIMITS.dailyLossPct)} ok />
                  <RiskRow label="Max drawdown" value={pct(RISK_LIMITS.maxDrawdownPct)} ok />
                  <RiskRow label="Max sector" value={pct(RISK_LIMITS.maxSectorPct)} ok />
                  <RiskRow
                    label="Current drawdown"
                    value={user ? pct(portfolio.drawdown) : "—"}
                    ok={!user || portfolio.drawdown < RISK_LIMITS.maxDrawdownPct}
                  />
                  <li className="surface px-4 py-3 text-sm text-mist/55">
                    Kill switch off · live trading disabled
                  </li>
                </ul>
              </section>
            </div>

            <section className="fade-up fade-up-delay-4 mb-14">
              <SectionTitle title="Recommendations" hint="explainable" />
              {!user ? (
                <Empty hint="Sign in to load live recommendations." />
              ) : (
                <div className="grid gap-3 md:grid-cols-2">
                  {recs.map((r) => (
                    <article key={r.ticker} className="surface surface-hover px-5 py-5">
                      <div className="flex items-baseline justify-between gap-3">
                        <h3 className="text-lg tracking-tight text-white">{r.ticker}</h3>
                        <span className={`font-mono text-[11px] uppercase tracking-wider ${badgeClass(r.action)}`}>
                          {r.action}
                        </span>
                      </div>
                      <p className="mt-3 text-sm leading-relaxed text-mist/70">{r.why}</p>
                      <div className="mt-4 flex flex-wrap gap-4 font-mono text-[11px] text-mist/40">
                        <span>conf {pct(r.confidence)}</span>
                        <span>E[r] {pct(r.expectedReturn)}</span>
                      </div>
                      <ul className="mt-4 space-y-1.5 border-t border-line pt-4 text-sm text-mist/55">
                        {r.risks.map((risk) => (
                          <li key={risk} className="flex gap-2">
                            <span className="text-mist/25">—</span>
                            {risk}
                          </li>
                        ))}
                      </ul>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </DeskSession>

      <div className="fade-up fade-up-delay-4 grid gap-10 lg:grid-cols-2">
        <section>
          <SectionTitle title="News" hint="classified" />
          {news.length === 0 ? (
            <Empty hint="Start news on :8001 to populate." />
          ) : (
            <ul className="space-y-2">
              {news.map((article) => (
                <li key={article.id} className="surface surface-hover px-5 py-4">
                  <div className="flex flex-wrap gap-3 font-mono text-[10px] uppercase tracking-[0.12em]">
                    <span className="text-signal">{article.category}</span>
                    <span className={badgeClass(article.risk_level)}>{article.risk_level}</span>
                    <span className={badgeClass(article.sentiment)}>{article.sentiment}</span>
                  </div>
                  <h3 className="mt-2.5 text-[15px] leading-snug text-white">{article.title}</h3>
                  <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-mist/55">{article.body}</p>
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
            <ul className="space-y-2">
              {announcements.map((a) => (
                <li key={a.id} className="surface surface-hover px-5 py-4">
                  <div className="flex flex-wrap gap-3 font-mono text-[10px] uppercase tracking-[0.12em]">
                    <span className="text-signal">{a.company_ticker}</span>
                    <span className="text-mist/40">{a.filing_type}</span>
                    <span className={a.impact_score >= 0 ? "text-signal" : "text-danger"}>
                      {a.impact_score >= 0 ? "+" : ""}
                      {a.impact_score.toFixed(2)}
                    </span>
                  </div>
                  <h3 className="mt-2.5 text-[15px] leading-snug text-white">{a.title}</h3>
                  {a.summary ? (
                    <p className="mt-1.5 text-sm leading-relaxed text-mist/55">{a.summary}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}

function StatusDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 border border-line px-2.5 py-1.5 text-mist/70">
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-signal pulse-dot" : "bg-danger/80"}`} />
      {label}
    </span>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="surface px-4 py-5">
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist/40">{label}</p>
      <p className="mt-3 text-2xl font-medium tracking-tight tabular-nums text-white">{value}</p>
    </div>
  );
}

function SectionTitle({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="mb-4 flex items-baseline justify-between gap-3">
      <h2 className="text-lg font-medium tracking-tight text-white md:text-xl">{title}</h2>
      <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/35">{hint}</span>
    </div>
  );
}

function RiskRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <li className="surface flex items-center justify-between px-4 py-3 text-sm">
      <span className="text-mist/65">{label}</span>
      <span className={`font-mono text-[11px] tabular-nums ${ok ? "text-signal/90" : "text-danger"}`}>
        {ok ? "OK" : "WATCH"} · {value}
      </span>
    </li>
  );
}

function Empty({ hint }: { hint: string }) {
  return <p className="surface px-5 py-8 text-sm text-mist/50">{hint}</p>;
}
