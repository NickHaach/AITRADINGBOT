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

const MARKET_URL = process.env.NEXT_PUBLIC_MARKET_URL ?? "http://localhost:8002";
const MARKET_WS =
  process.env.NEXT_PUBLIC_MARKET_WS_URL ??
  MARKET_URL.replace(/^http/, "ws") + "/v1/market/stream?tickers=AAPL,NVDA,SPY";

export function MarketChartPanel({ ticker = "AAPL" }: { ticker?: string }) {
  const [bars, setBars] = useState<BarPoint[]>([]);
  const [live, setLive] = useState<QuoteTick | null>(null);
  const [status, setStatus] = useState<"idle" | "live" | "offline">("idle");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${MARKET_URL}/v1/market/${ticker}/bars?limit=40`, {
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
    <section>
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-medium text-white">{ticker} tape</h2>
          <p className="mt-1 font-mono text-xs text-mist/60">
            OHLCV history · live quote stream
          </p>
        </div>
        <div className="text-right font-mono text-xs">
          <p className={status === "live" ? "text-signal" : "text-mist/50"}>
            {status === "live" ? "STREAM LIVE" : status === "offline" ? "STREAM OFF" : "…"}
          </p>
          {lastClose != null ? (
            <p className="mt-1 text-sm text-white">${lastClose.toFixed(2)}</p>
          ) : null}
          {change != null ? (
            <p className={`mt-0.5 ${change >= 0 ? "text-signal" : "text-danger"}`}>
              {change >= 0 ? "+" : ""}
              {(change * 100).toFixed(2)}%
            </p>
          ) : null}
        </div>
      </div>

      <div className="border border-line bg-panel/40 p-3">
        {bars.length === 0 ? (
          <p className="p-8 text-center text-sm text-mist/70">
            Start market data on :8002 to load bars.
          </p>
        ) : (
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={bars} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="tapeFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3d9a6a" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#3d9a6a" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis
                  dataKey="t"
                  tick={{ fill: "rgba(180,190,200,0.5)", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  minTickGap={28}
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fill: "rgba(180,190,200,0.5)", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  width={48}
                />
                <Tooltip
                  contentStyle={{
                    background: "#0f1419",
                    border: "1px solid rgba(255,255,255,0.12)",
                    borderRadius: 0,
                    fontSize: 12,
                  }}
                  labelStyle={{ color: "#9aa3ad" }}
                />
                <Area
                  type="monotone"
                  dataKey="close"
                  stroke="#3d9a6a"
                  fill="url(#tapeFill)"
                  strokeWidth={1.5}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </section>
  );
}
