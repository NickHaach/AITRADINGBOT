import {
  RISK_LIMITS,
  demoPortfolio,
  demoRecommendations,
  fetchAnnouncements,
  fetchHealth,
  fetchNews,
} from "@/lib/api";
import { MarketChartPanel } from "@/components/MarketChartPanel";

function badgeClass(level: string): string {
  const v = level.toLowerCase();
  if (v.includes("critical") || v.includes("very_bearish") || v === "breaking" || v === "sell") {
    return "text-danger";
  }
  if (v.includes("high") || v.includes("bearish") || v === "hold") return "text-warn";
  if (v.includes("bullish") || v === "buy") return "text-signal";
  return "text-mist";
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
  const portfolio = demoPortfolio();
  const recs = demoRecommendations();

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-12 border-b border-line pb-8">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-signal">Aether Desk</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white md:text-5xl">
          Investment assistant
        </h1>
        <p className="mt-3 max-w-2xl text-base text-mist/90">
          Multi-source intelligence, risk-gated paper execution, and explainable signals —
          built like a research desk, not a tip sheet.
        </p>
        <div className="mt-6 flex flex-wrap gap-4 font-mono text-xs">
          <StatusDot ok={health.api} label="API" />
          <StatusDot ok={health.news} label="News" />
          <StatusDot ok={health.market} label="Market" />
          <StatusDot ok={health.announcements} label="Filings" />
          <span className="rounded border border-line px-3 py-1.5 text-warn">EXECUTION: PAPER</span>
        </div>
      </header>

      <section className="mb-10 grid gap-4 md:grid-cols-4">
        <Metric label="Equity" value={`$${portfolio.equity.toLocaleString()}`} />
        <Metric label="Cash" value={`$${portfolio.cash.toLocaleString()}`} />
        <Metric label="Drawdown" value={pct(portfolio.drawdown)} />
        <Metric label="News / filings" value={`${news.length} / ${announcements.length}`} />
      </section>

      <section className="mb-12">
        <MarketChartPanel ticker="AAPL" />
      </section>

      <div className="mb-12 grid gap-8 lg:grid-cols-2">
        <section>
          <SectionTitle title="Positions" hint="demo book until portfolio API is wired" />
          <div className="overflow-hidden border border-line">
            <table className="w-full text-left text-sm">
              <thead className="font-mono text-[11px] uppercase tracking-wider text-mist/50">
                <tr className="border-b border-line">
                  <th className="px-4 py-3">Ticker</th>
                  <th className="px-4 py-3">Qty</th>
                  <th className="px-4 py-3">Last</th>
                  <th className="px-4 py-3">PnL</th>
                  <th className="px-4 py-3">Weight</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.positions.map((p) => (
                  <tr key={p.ticker} className="border-b border-line/70 last:border-0">
                    <td className="px-4 py-3 font-medium text-white">{p.ticker}</td>
                    <td className="px-4 py-3 font-mono text-xs">{p.qty}</td>
                    <td className="px-4 py-3 font-mono text-xs">${p.last.toFixed(2)}</td>
                    <td className={`px-4 py-3 font-mono text-xs ${p.pnl >= 0 ? "text-signal" : "text-danger"}`}>
                      {p.pnl >= 0 ? "+" : ""}
                      {p.pnl}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{pct(p.weight)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <SectionTitle title="Risk dashboard" hint="hard gates from Risk Engine" />
          <ul className="space-y-3">
            <RiskRow label="Max position" value={pct(RISK_LIMITS.maxPositionPct)} ok />
            <RiskRow label="Daily loss limit" value={pct(RISK_LIMITS.dailyLossPct)} ok />
            <RiskRow label="Max drawdown" value={pct(RISK_LIMITS.maxDrawdownPct)} ok />
            <RiskRow label="Max sector exposure" value={pct(RISK_LIMITS.maxSectorPct)} ok />
            <RiskRow
              label="Current drawdown"
              value={pct(portfolio.drawdown)}
              ok={portfolio.drawdown < RISK_LIMITS.maxDrawdownPct}
            />
            <li className="border border-line bg-panel/40 px-4 py-3 text-sm text-mist/80">
              Kill switch off · live trading disabled · paper broker only
            </li>
          </ul>
        </section>
      </div>

      <section className="mb-12">
        <SectionTitle title="AI recommendations" hint="explainability panel" />
        <div className="grid gap-4 md:grid-cols-2">
          {recs.map((r) => (
            <article key={r.ticker} className="border border-line bg-panel/40 px-5 py-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-lg text-white">{r.ticker}</h3>
                <span className={`font-mono text-xs uppercase ${badgeClass(r.action)}`}>{r.action}</span>
              </div>
              <p className="mt-2 text-sm text-mist/85">{r.why}</p>
              <div className="mt-3 flex flex-wrap gap-3 font-mono text-[11px] text-mist/55">
                <span>conf {pct(r.confidence)}</span>
                <span>E[r] {pct(r.expectedReturn)}</span>
              </div>
              <div className="mt-3">
                <p className="font-mono text-[10px] uppercase tracking-wider text-mist/40">Risks</p>
                <ul className="mt-1 space-y-1 text-sm text-mist/75">
                  {r.risks.map((risk) => (
                    <li key={risk}>· {risk}</li>
                  ))}
                </ul>
              </div>
            </article>
          ))}
        </div>
      </section>

      <div className="mb-12 grid gap-8 lg:grid-cols-2">
        <section>
          <SectionTitle title="News intelligence" hint="classified · embedded · deduped" />
          {news.length === 0 ? (
            <Empty hint="Start news on :8001 to populate." />
          ) : (
            <ul className="space-y-3">
              {news.map((article) => (
                <li key={article.id} className="border border-line bg-panel/40 px-5 py-4">
                  <div className="flex flex-wrap gap-3 font-mono text-[11px] uppercase tracking-wide">
                    <span className="text-signal">{article.category}</span>
                    <span className={badgeClass(article.risk_level)}>risk:{article.risk_level}</span>
                    <span className={badgeClass(article.sentiment)}>{article.sentiment}</span>
                  </div>
                  <h3 className="mt-2 text-base text-white">{article.title}</h3>
                  <p className="mt-1 line-clamp-2 text-sm text-mist/80">{article.body}</p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <SectionTitle title="Filings & announcements" hint="impact-scored" />
          {announcements.length === 0 ? (
            <Empty hint="Start announcements on :8003 to populate." />
          ) : (
            <ul className="space-y-3">
              {announcements.map((a) => (
                <li key={a.id} className="border border-line bg-panel/40 px-5 py-4">
                  <div className="flex flex-wrap gap-3 font-mono text-[11px] uppercase">
                    <span className="text-signal">{a.company_ticker}</span>
                    <span className="text-mist/50">{a.filing_type}</span>
                    <span className={a.impact_score >= 0 ? "text-signal" : "text-danger"}>
                      impact {a.impact_score >= 0 ? "+" : ""}
                      {a.impact_score.toFixed(2)}
                    </span>
                  </div>
                  <h3 className="mt-2 text-base text-white">{a.title}</h3>
                  {a.summary ? <p className="mt-1 text-sm text-mist/80">{a.summary}</p> : null}
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
    <span className="inline-flex items-center gap-2 rounded border border-line px-3 py-1.5">
      <span className={`h-2 w-2 rounded-full ${ok ? "bg-signal" : "bg-danger"}`} />
      {label}
    </span>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-line bg-panel/50 px-4 py-4">
      <p className="font-mono text-[11px] uppercase tracking-wider text-mist/50">{label}</p>
      <p className="mt-2 text-2xl font-medium text-white">{value}</p>
    </div>
  );
}

function SectionTitle({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-3">
      <h2 className="text-xl font-medium text-white">{title}</h2>
      <span className="font-mono text-xs text-mist/60">{hint}</span>
    </div>
  );
}

function RiskRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <li className="flex items-center justify-between border border-line bg-panel/40 px-4 py-3 text-sm">
      <span className="text-mist/80">{label}</span>
      <span className={`font-mono text-xs ${ok ? "text-signal" : "text-danger"}`}>
        {ok ? "OK" : "WATCH"} · {value}
      </span>
    </li>
  );
}

function Empty({ hint }: { hint: string }) {
  return <p className="border border-line bg-panel/60 p-6 text-sm text-mist/80">{hint}</p>;
}
