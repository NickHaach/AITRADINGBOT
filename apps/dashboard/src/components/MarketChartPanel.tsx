"use client";

import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type BarPoint = {
  t: string;
  close: number;
};

type QuoteTick = {
  ticker: string;
  last: number;
  timestamp: string;
};

/** Same-origin proxy for REST (avoids CORS). WS stays direct to market service. */
const MARKET_HTTP =
  typeof window === "undefined"
    ? process.env.NEXT_PUBLIC_MARKET_URL ?? "http://127.0.0.1:8002"
    : "/proxy/market";
const MARKET_WS =
  process.env.NEXT_PUBLIC_MARKET_WS_URL ??
  `${(process.env.NEXT_PUBLIC_MARKET_URL ?? "http://127.0.0.1:8002").replace(/^http/, "ws")}/v1/market/stream?tickers=AAPL,NVDA,SPY`;

export function MarketChartPanel({ ticker = "AAPL" }: { ticker?: string }) {
  const [bars, setBars] = useState<BarPoint[]>([]);
  const [live, setLive] = useState<QuoteTick | null>(null);
  const [status, setStatus] = useState<"idle" | "live" | "offline">("idle");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${MARKET_HTTP}/v1/market/${ticker}/bars?limit=40`, {
          cache: "no-store",
        });
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
        /* market service offline */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ticker]);

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
            quotes?: Array<{ ticker: string; last: number; timestamp: string }>;
          };
          const match = payload.quotes?.find((q) => q.ticker === ticker);
          if (match) {
            setLive({ ticker: match.ticker, last: match.last, timestamp: match.timestamp });
          }
        } catch {
          /* ignore malformed frames */
        }
      };
    } catch {
      setStatus("offline");
    }
    return () => {
      closed = true;
      ws?.close();
    };
  }, [ticker]);

  const lastClose = live?.last ?? bars[bars.length - 1]?.close;
  const first = bars[0]?.close;
  const change =
    lastClose != null && first != null && first !== 0 ? (lastClose - first) / first : null;

  return (
    <section className="fade-up fade-up-delay-2">
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-xl font-medium tracking-tight text-white md:text-[1.35rem]">{ticker}</h2>
          <p className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-mist/40">
            Tape · live stream
          </p>
        </div>
        <div className="text-right">
          <p
            className={`inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.16em] ${
              status === "live" ? "text-signal" : "text-mist/35"
            }`}
          >
            {status === "live" ? <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-signal" /> : null}
            {status === "live" ? "Live" : status === "offline" ? "Off" : "…"}
          </p>
          {lastClose != null ? (
            <p className="mt-1.5 text-2xl font-medium tabular-nums tracking-tight text-white">
              ${lastClose.toFixed(2)}
            </p>
          ) : null}
          {change != null ? (
            <p
              className={`mt-0.5 font-mono text-xs tabular-nums ${
                change >= 0 ? "text-signal" : "text-danger"
              }`}
            >
              {change >= 0 ? "+" : ""}
              {(change * 100).toFixed(2)}%
            </p>
          ) : null}
        </div>
      </div>

      <div className="border border-line bg-[rgba(7,11,9,0.45)] p-1 md:p-2">
        {bars.length === 0 ? (
          <p className="px-4 py-16 text-center text-sm text-mist/45">Waiting for market data on :8002</p>
        ) : (
          <div className="h-64 w-full md:h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={bars} margin={{ top: 12, right: 10, left: 0, bottom: 4 }}>
                <defs>
                  <linearGradient id="tapeFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3dcf91" stopOpacity={0.32} />
                    <stop offset="100%" stopColor="#3dcf91" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(157,181,168,0.05)" vertical={false} />
                <XAxis
                  dataKey="t"
                  tick={{ fill: "rgba(157,181,168,0.35)", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  minTickGap={40}
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fill: "rgba(157,181,168,0.35)", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  width={46}
                />
                <Tooltip
                  contentStyle={{
                    background: "rgba(7, 11, 9, 0.96)",
                    border: "1px solid rgba(157,181,168,0.14)",
                    borderRadius: 0,
                    fontSize: 12,
                    backdropFilter: "blur(10px)",
                  }}
                  labelStyle={{ color: "#9db5a8" }}
                  itemStyle={{ color: "#3dcf91" }}
                />
                <Area
                  type="monotone"
                  dataKey="close"
                  stroke="#3dcf91"
                  fill="url(#tapeFill)"
                  strokeWidth={1.7}
                  isAnimationActive
                  animationDuration={800}
                  animationEasing="ease-out"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </section>
  );
}
