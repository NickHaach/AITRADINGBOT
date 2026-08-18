"use client";

import { useEffect, useState } from "react";

type QuoteTick = { ticker: string; last: number; bid?: number; ask?: number };

const TAPE_TICKERS = [
  "SPY",
  "QQQ",
  "AAPL",
  "MSFT",
  "NVDA",
  "JPM",
  "XOM",
  "EURUSD",
  "GBPUSD",
  "BTCUSD",
  "ETHUSD",
];

const MARKET_WS =
  process.env.NEXT_PUBLIC_MARKET_WS_URL ??
  `${(process.env.NEXT_PUBLIC_MARKET_URL ?? "http://127.0.0.1:8002").replace(/^http/, "ws")}/v1/market/stream?tickers=${TAPE_TICKERS.join(",")}`;

function formatTapePrice(ticker: string, value: number): string {
  if (ticker.includes("USD") && ticker.length === 6 && !ticker.startsWith("BTC") && !ticker.startsWith("ETH") && !ticker.startsWith("SOL")) {
    return ticker.includes("JPY") ? value.toFixed(3) : value.toFixed(4);
  }
  if (ticker.endsWith("USD") && (ticker.startsWith("BTC") || ticker.startsWith("ETH") || ticker.startsWith("SOL"))) {
    return value >= 1000 ? value.toFixed(0) : value.toFixed(2);
  }
  return value.toFixed(2);
}

function displaySym(ticker: string): string {
  if (ticker.length === 6 && !["BTCUSD", "ETHUSD", "SOLUSD"].includes(ticker)) {
    return `${ticker.slice(0, 3)}/${ticker.slice(3)}`;
  }
  if (ticker.endsWith("USD") && ticker.length > 3) return `${ticker.slice(0, -3)}`;
  return ticker;
}

export function TickerTape() {
  const [quotes, setQuotes] = useState<Record<string, QuoteTick>>({});
  const [prev, setPrev] = useState<Record<string, number>>({});
  const [live, setLive] = useState(false);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    try {
      ws = new WebSocket(MARKET_WS);
      ws.onopen = () => setLive(true);
      ws.onclose = () => {
        if (!closed) setLive(false);
      };
      ws.onerror = () => setLive(false);
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as {
            quotes?: Array<{ ticker: string; last: number; bid: number; ask: number }>;
          };
          if (!payload.quotes?.length) return;
          setQuotes((current) => {
            const next = { ...current };
            const prior: Record<string, number> = {};
            for (const q of payload.quotes!) {
              if (current[q.ticker]?.last != null) prior[q.ticker] = current[q.ticker].last;
              next[q.ticker] = q;
            }
            if (Object.keys(prior).length) setPrev((p) => ({ ...p, ...prior }));
            return next;
          });
        } catch {
          /* ignore */
        }
      };
    } catch {
      setLive(false);
    }
    return () => {
      closed = true;
      ws?.close();
    };
  }, []);

  const items = TAPE_TICKERS.map((ticker) => {
    const q = quotes[ticker];
    const last = q?.last;
    const prior = prev[ticker];
    const chg = last != null && prior != null && prior !== 0 ? (last - prior) / prior : null;
    return { ticker, last, chg };
  });

  const doubled = [...items, ...items];

  return (
    <div className="ticker-tape" aria-label="Live market tape">
      <div className="ticker-tape-rail">
        <span className={`ticker-live ${live ? "is-live" : ""}`}>
          <span className="pulse-dot h-1 w-1 rounded-full bg-current" />
          {live ? "LIVE" : "TAPE"}
        </span>
        <div className="ticker-track">
          <div className="ticker-scroll">
            {doubled.map((item, i) => (
              <span key={`${item.ticker}-${i}`} className="ticker-item">
                <span className="ticker-sym">{displaySym(item.ticker)}</span>
                <span className="ticker-px">
                  {item.last != null ? formatTapePrice(item.ticker, item.last) : "—"}
                </span>
                <span
                  className={
                    item.chg == null
                      ? "ticker-chg muted"
                      : item.chg >= 0
                        ? "ticker-chg up"
                        : "ticker-chg down"
                  }
                >
                  {item.chg == null
                    ? "·"
                    : `${item.chg >= 0 ? "+" : ""}${(item.chg * 100).toFixed(2)}%`}
                </span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
