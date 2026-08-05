const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const NEWS_URL = process.env.NEXT_PUBLIC_NEWS_URL ?? "http://localhost:8001";
const MARKET_URL = process.env.NEXT_PUBLIC_MARKET_URL ?? "http://localhost:8002";
const ANN_URL = process.env.NEXT_PUBLIC_ANN_URL ?? "http://localhost:8003";
const PORTFOLIO_URL = process.env.NEXT_PUBLIC_PORTFOLIO_URL ?? "http://localhost:8008";

export type NewsArticle = {
  id: string;
  source: string;
  title: string;
  body: string;
  category: string;
  companies: string[];
  sectors: string[];
  risk_level: string;
  sentiment: string;
  sentiment_score: number;
  confidence: number;
  urgency: string;
  published_at: string;
};

export type MarketFeatures = {
  ticker: string;
  last_price: number;
  returns_5d: number;
  volatility_20d: number;
  liquidity_score: number;
  trend_strength: number;
  confidence?: number;
};

export type Announcement = {
  id: string;
  company_ticker: string;
  filing_type: string;
  title: string;
  summary: string | null;
  impact_score: number;
  filed_at: string;
};

export type DemoPosition = {
  ticker: string;
  qty: number;
  avgCost: number;
  last: number;
  pnl: number;
  weight: number;
};

export type DemoRecommendation = {
  ticker: string;
  action: string;
  confidence: number;
  expectedReturn: number;
  why: string;
  risks: string[];
};

async function safeJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(url, { next: { revalidate: 30 } });
    if (!res.ok) return fallback;
    return res.json();
  } catch {
    return fallback;
  }
}

export async function fetchNews(limit = 20): Promise<NewsArticle[]> {
  return safeJson(`${NEWS_URL}/v1/news?limit=${limit}`, []);
}

export async function fetchHealth(): Promise<{
  api: boolean;
  news: boolean;
  market: boolean;
  announcements: boolean;
  portfolio: boolean;
}> {
  const check = async (url: string) => {
    try {
      const res = await fetch(`${url}/health`, { cache: "no-store" });
      return res.ok;
    } catch {
      return false;
    }
  };
  const [api, news, market, announcements, portfolio] = await Promise.all([
    check(API_URL),
    check(NEWS_URL),
    check(MARKET_URL),
    check(ANN_URL),
    check(PORTFOLIO_URL),
  ]);
  return { api, news, market, announcements, portfolio };
}

export async function fetchMarketTickers(): Promise<string[]> {
  return safeJson(`${MARKET_URL}/v1/market/tickers`, []);
}

export async function fetchFeatures(ticker: string): Promise<MarketFeatures | null> {
  return safeJson(`${MARKET_URL}/v1/market/${ticker}/features`, null);
}

export async function fetchAnnouncements(limit = 8): Promise<Announcement[]> {
  return safeJson(`${ANN_URL}/v1/announcements?limit=${limit}`, []);
}

export type LivePortfolio = {
  cash: number;
  equity: number;
  positions: DemoPosition[];
  drawdown: number;
  totalPnl?: number;
  asOf?: string | null;
  source: "live" | "demo";
};

export async function fetchPortfolio(): Promise<LivePortfolio> {
  try {
    const res = await fetch(`${PORTFOLIO_URL}/v1/portfolio`, { cache: "no-store" });
    if (!res.ok) return { ...demoPortfolio(), source: "demo" };
    const data = await res.json();
    return {
      cash: Number(data.cash ?? 0),
      equity: Number(data.equity ?? 0),
      drawdown: Number(data.drawdown ?? 0),
      totalPnl: data.totalPnl != null ? Number(data.totalPnl) : undefined,
      asOf: data.asOf ?? null,
      positions: Array.isArray(data.positions)
        ? data.positions.map((p: Record<string, unknown>) => ({
            ticker: String(p.ticker),
            qty: Number(p.qty ?? 0),
            avgCost: Number(p.avgCost ?? 0),
            last: Number(p.last ?? 0),
            pnl: Number(p.pnl ?? 0),
            weight: Number(p.weight ?? 0),
          }))
        : [],
      source: "live",
    };
  } catch {
    return { ...demoPortfolio(), source: "demo" };
  }
}

export async function fetchRecommendations(): Promise<DemoRecommendation[]> {
  const live = await safeJson<DemoRecommendation[]>(
    `${PORTFOLIO_URL}/v1/portfolio/recommendations`,
    [],
  );
  return live.length > 0 ? live : demoRecommendations();
}

/** Demo portfolio used when live portfolio API is not yet exposed. */
export function demoPortfolio(): {
  cash: number;
  equity: number;
  positions: DemoPosition[];
  drawdown: number;
} {
  const positions: DemoPosition[] = [
    { ticker: "NVDA", qty: 40, avgCost: 110, last: 120, pnl: 400, weight: 0.18 },
    { ticker: "AAPL", qty: 50, avgCost: 185, last: 190, pnl: 250, weight: 0.16 },
    { ticker: "MSFT", qty: 20, avgCost: 410, last: 420, pnl: 200, weight: 0.14 },
    { ticker: "JPM", qty: 30, avgCost: 190, last: 195, pnl: 150, weight: 0.1 },
  ];
  return { cash: 42000, equity: 100000, positions, drawdown: 0.028 };
}

export function demoRecommendations(): DemoRecommendation[] {
  return [
    {
      ticker: "NVDA",
      action: "BUY",
      confidence: 0.72,
      expectedReturn: 0.038,
      why: "Positive earnings impact + constructive 5d momentum and AI demand sentiment.",
      risks: ["High realized vol", "Sector concentration"],
    },
    {
      ticker: "XOM",
      action: "HOLD",
      confidence: 0.54,
      expectedReturn: -0.004,
      why: "Mixed energy news; geopolitical oil premium offset by weak demand language.",
      risks: ["Headline risk from OPEC", "Macro growth scare"],
    },
  ];
}

export const RISK_LIMITS = {
  maxPositionPct: 0.05,
  dailyLossPct: 0.02,
  maxDrawdownPct: 0.15,
  maxSectorPct: 0.25,
};
