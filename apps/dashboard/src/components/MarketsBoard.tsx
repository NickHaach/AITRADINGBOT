"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type BarPoint = { t: string; close: number };
type QuoteTick = { ticker: string; last: number; bid?: number; ask?: number; timestamp: string };
type MarketGroup = "equities" | "forex" | "crypto";
type Timeframe = "1D" | "5D" | "1M";

const MARKET_HTTP =
  typeof window === "undefined"
    ? process.env.NEXT_PUBLIC_MARKET_URL ?? "http://127.0.0.1:8002"
    : "/proxy/market";

const GROUPS: Record<MarketGroup, { label: string; tickers: string[] }> = {
  equities: { label: "Equities", tickers: ["AAPL", "MSFT", "NVDA", "SPY", "QQQ", "XOM", "JPM"] },
  forex: { label: "Forex", tickers: ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"] },
  crypto: { label: "Crypto", tickers: ["BTCUSD", "ETHUSD", "SOLUSD"] },
};

const ALL_TICKERS = [
  ...GROUPS.equities.tickers,
  ...GROUPS.forex.tickers,
  ...GROUPS.crypto.tickers,
];

const TF_LIMIT: Record<Timeframe, number> = { "1D": 24, "5D": 40, "1M": 60 };

const MARKET_WS =
  process.env.NEXT_PUBLIC_MARKET_WS_URL ??
  `${(process.env.NEXT_PUBLIC_MARKET_URL ?? "http://127.0.0.1:8002").replace(/^http/, "ws")}/v1/market/stream?tickers=${ALL_TICKERS.join(",")}`;

function formatPrice(ticker: string, value: number): string {
  if (GROUPS.forex.tickers.includes(ticker)) {
    return ticker.includes("JPY") ? value.toFixed(3) : value.toFixed(5);
  }
  if (GROUPS.crypto.tickers.includes(ticker)) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: value >= 1000 ? 0 : 2,
    }).format(value);
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function displaySymbol(ticker: string, group: MarketGroup): string {
  if (group === "forex" && ticker.length === 6) {
    return `${ticker.slice(0, 3)}/${ticker.slice(3)}`;
  }
  if (group === "crypto" && ticker.endsWith("USD")) {
    return `${ticker.slice(0, -3)}/USD`;
  }
  return ticker;
}

export function MarketsBoard({ compact = false }: { compact?: boolean }) {
  const [group, setGroup] = useState<MarketGroup>("equities");
  const [selected, setSelected] = useState("AAPL");
  const [tf, setTf] = useState<Timeframe>("5D");
  const [quotes, setQuotes] = useState<Record<string, QuoteTick>>({});
  const [prev, setPrev] = useState<Record<string, number>>({});
  const [flash, setFlash] = useState<Record<string, "up" | "down">>({});
  const [bars, setBars] = useState<BarPoint[]>([]);
  const [status, setStatus] = useState<"idle" | "live" | "offline">("idle");
  const flashTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const groupTickers = GROUPS[group].tickers;

  useEffect(() => {
    if (!groupTickers.includes(selected)) {
      setSelected(groupTickers[0]);
    }
  }, [group, groupTickers, selected]);

  useEffect(() => {
    let cancelled = false;
    setBars([]);
    (async () => {
      try {
        const res = await fetch(
          `${MARKET_HTTP}/v1/market/${selected}/bars?limit=${TF_LIMIT[tf]}`,
          { cache: "no-store" },
        );
        if (!res.ok) return;
        const data = (await res.json()) as Array<{ timestamp: string; close: number }>;
        if (cancelled) return;
        setBars(
          data.map((b) => ({
            t: b.timestamp.slice(5, 16).replace("T", " "),
            close: Number(b.close),
          })),
        );
      } catch {
        /* offline */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selected, tf]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    try {
      ws = new WebSocket(MARKET_WS);
      ws.onopen = () => setStatus("live");
      ws.onclose = () => {
        if (!closed) setStatus("offline");
      };
      ws.onerror = () => setStatus("offline");
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as {
            quotes?: Array<{ ticker: string; last: number; bid: number; ask: number; timestamp: string }>;
          };
          if (!payload.quotes?.length) return;
          setQuotes((current) => {
            const next = { ...current };
            const prior: Record<string, number> = {};
            const flashes: Record<string, "up" | "down"> = {};
            for (const q of payload.quotes!) {
              if (current[q.ticker]?.last != null) {
                prior[q.ticker] = current[q.ticker].last;
                if (q.last > current[q.ticker].last) flashes[q.ticker] = "up";
                else if (q.last < current[q.ticker].last) flashes[q.ticker] = "down";
              }
              next[q.ticker] = {
                ticker: q.ticker,
                last: q.last,
                bid: q.bid,
                ask: q.ask,
                timestamp: q.timestamp,
              };
            }
            if (Object.keys(prior).length) setPrev((p) => ({ ...p, ...prior }));
            if (Object.keys(flashes).length) {
              setFlash((f) => ({ ...f, ...flashes }));
              for (const [t, dir] of Object.entries(flashes)) {
                if (flashTimers.current[t]) clearTimeout(flashTimers.current[t]);
                flashTimers.current[t] = setTimeout(() => {
                  setFlash((f) => {
                    const n = { ...f };
                    if (n[t] === dir) delete n[t];
                    return n;
                  });
                }, 450);
              }
            }
            return next;
          });
        } catch {
          /* ignore */
        }
      };
    } catch {
      setStatus("offline");
    }
    return () => {
      closed = true;
      ws?.close();
      for (const t of Object.values(flashTimers.current)) clearTimeout(t);
    };
  }, []);

  const live = quotes[selected];
  const lastClose = live?.last ?? bars[bars.length - 1]?.close;
  const first = bars[0]?.close;
  const change =
    lastClose != null && first != null && first !== 0 ? (lastClose - first) / first : null;
  const spread =
    live?.bid != null && live?.ask != null ? live.ask - live.bid : null;

  const streamLabel = useMemo(() => {
    if (status === "live") return "Live";
    if (status === "offline") return "Off";
    return "…";
  }, [status]);

  const chartH = compact ? "h-52 md:h-56" : "h-64 md:h-80";

  return (
    <section className="fade-up fade-up-delay-2">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="section-title text-[1.65rem] md:text-[1.75rem]">Markets</h2>
          <p className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-mist/40">
            Watchlist · chart · quote
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <p
            className={`inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] ${
              status === "live" ? "text-gain" : "text-mist/35"
            }`}
          >
            {status === "live" ? <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-gain" /> : null}
            {streamLabel}
          </p>
          <div className="flex border border-line">
            {(Object.keys(GROUPS) as MarketGroup[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setGroup(key)}
                className={`px-3.5 py-2 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors ${
                  group === key ? "bg-signal text-ink" : "text-mist/50 hover:text-ivory"
                }`}
              >
                {GROUPS[key].label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-0 border border-line lg:grid-cols-[minmax(0,0.88fr)_minmax(0,1.42fr)]">
        {/* Watchlist — Thinkorswim / IBKR density */}
        <div className="border-b border-line lg:border-b-0 lg:border-r">
          <div className="grid grid-cols-[1.15fr_1fr_0.85fr_0.7fr] border-b border-line bg-[rgba(5,8,12,0.35)] px-3 py-2.5 font-mono text-[9px] uppercase tracking-[0.14em] text-mist/35 md:px-4">
            <span>Symbol</span>
            <span className="text-right">Last</span>
            <span className="text-right">Bid / Ask</span>
            <span className="text-right">Δ</span>
          </div>
          <ul className="max-h-[22rem] overflow-y-auto md:max-h-[28rem]">
            {groupTickers.map((ticker) => {
              const q = quotes[ticker];
              const last = q?.last;
              const prior = prev[ticker];
              const tickChange =
                last != null && prior != null && prior !== 0 ? (last - prior) / prior : null;
              const active = selected === ticker;
              const flashDir = flash[ticker];
              return (
                <li key={ticker}>
                  <button
                    type="button"
                    onClick={() => setSelected(ticker)}
                    className={`grid w-full grid-cols-[1.15fr_1fr_0.85fr_0.7fr] items-center px-3 py-2.5 text-left transition-colors md:px-4 ${
                      active ? "bg-signal/10" : "hover:bg-ivory/[0.025]"
                    } border-b border-line/35 last:border-0 ${
                      flashDir === "up" ? "quote-flash-up" : flashDir === "down" ? "quote-flash-down" : ""
                    }`}
                  >
                    <span
                      className={`text-[13px] tracking-tight ${active ? "text-ivory" : "text-mist/75"}`}
                    >
                      {displaySymbol(ticker, group)}
                    </span>
                    <span className="text-right font-mono text-[11px] tabular-nums text-ivory/90">
                      {last != null ? formatPrice(ticker, last) : "—"}
                    </span>
                    <span className="text-right font-mono text-[10px] tabular-nums text-mist/45">
                      {q?.bid != null && q?.ask != null
                        ? `${formatPrice(ticker, q.bid).replace("$", "")} / ${formatPrice(ticker, q.ask).replace("$", "")}`
                        : "—"}
                    </span>
                    <span
                      className={`text-right font-mono text-[11px] tabular-nums ${
                        tickChange == null
                          ? "text-mist/30"
                          : tickChange >= 0
                            ? "text-gain"
                            : "text-danger"
                      }`}
                    >
                      {tickChange == null
                        ? "—"
                        : `${tickChange >= 0 ? "+" : ""}${(tickChange * 100).toFixed(2)}%`}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Chart pane — TradingView-inspired header */}
        <div className="bg-[rgba(5,8,12,0.4)]">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line px-4 py-4 md:px-5">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-display text-[1.65rem] tracking-tight text-ivory md:text-2xl">
                  {displaySymbol(selected, group)}
                </h3>
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/35">
                  {GROUPS[group].label}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-mist/40">
                {live?.bid != null ? (
                  <span>
                    Bid <span className="text-gain/90">{formatPrice(selected, live.bid)}</span>
                  </span>
                ) : null}
                {live?.ask != null ? (
                  <span>
                    Ask <span className="text-danger/90">{formatPrice(selected, live.ask)}</span>
                  </span>
                ) : null}
                {spread != null ? (
                  <span>
                    Spr <span className="text-mist/70">{spread.toFixed(group === "forex" ? 5 : 2)}</span>
                  </span>
                ) : null}
              </div>
            </div>
            <div className="text-right">
              {lastClose != null ? (
                <p
                  className={`font-display text-3xl font-medium tabular-nums tracking-tight text-ivory md:text-[2.35rem] ${
                    flash[selected] === "up"
                      ? "quote-flash-up"
                      : flash[selected] === "down"
                        ? "quote-flash-down"
                        : ""
                  }`}
                >
                  {formatPrice(selected, lastClose)}
                </p>
              ) : null}
              {change != null ? (
                <p
                  className={`mt-1 font-mono text-xs tabular-nums ${
                    change >= 0 ? "text-gain" : "text-danger"
                  }`}
                >
                  {change >= 0 ? "+" : ""}
                  {(change * 100).toFixed(2)}% · {tf}
                </p>
              ) : null}
            </div>
          </div>

          <div className="flex items-center gap-1 border-b border-line px-3 py-2 md:px-4">
            {(Object.keys(TF_LIMIT) as Timeframe[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setTf(key)}
                className={`px-2.5 py-1 font-mono text-[10px] tracking-[0.12em] transition-colors ${
                  tf === key
                    ? "bg-signal/15 text-signal"
                    : "text-mist/40 hover:text-mist/70"
                }`}
              >
                {key}
              </button>
            ))}
          </div>

          <div className="p-1 md:p-2">
            {bars.length === 0 ? (
              <p className="px-4 py-16 text-center text-sm text-mist/45">
                Waiting for market data on :8002
              </p>
            ) : (
              <div className={`w-full ${chartH}`}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={bars} margin={{ top: 12, right: 10, left: 0, bottom: 4 }}>
                    <defs>
                      <linearGradient id="marketsFill" x1="0" y1="0" x2="0" y2="1">
                        <stop
                          offset="0%"
                          stopColor={change != null && change < 0 ? "#d47878" : "#6eb8c9"}
                          stopOpacity={0.28}
                        />
                        <stop
                          offset="100%"
                          stopColor={change != null && change < 0 ? "#d47878" : "#6eb8c9"}
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(148,174,196,0.07)" vertical={false} />
                    <XAxis
                      dataKey="t"
                      tick={{ fill: "rgba(154,173,184,0.45)", fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                      minTickGap={40}
                    />
                    <YAxis
                      domain={["auto", "auto"]}
                      tick={{ fill: "rgba(154,173,184,0.45)", fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                      width={54}
                      tickFormatter={(v: number) =>
                        group === "forex"
                          ? Number(v).toFixed(4)
                          : Number(v).toFixed(group === "crypto" ? 0 : 1)
                      }
                    />
                    <Tooltip
                      contentStyle={{
                        background: "rgba(7, 11, 16, 0.96)",
                        border: "1px solid rgba(148,174,196,0.16)",
                        borderRadius: 0,
                        fontSize: 12,
                        backdropFilter: "blur(10px)",
                      }}
                      labelStyle={{ color: "#9aadb8" }}
                      itemStyle={{ color: "#6eb8c9" }}
                      formatter={(value: number) => [formatPrice(selected, value), "Last"]}
                    />
                    <Area
                      type="monotone"
                      dataKey="close"
                      stroke={change != null && change < 0 ? "#d47878" : "#6eb8c9"}
                      fill="url(#marketsFill)"
                      strokeWidth={1.5}
                      isAnimationActive
                      animationDuration={600}
                      animationEasing="ease-out"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
