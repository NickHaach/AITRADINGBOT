const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const NEWS_URL = process.env.NEXT_PUBLIC_NEWS_URL ?? "http://localhost:8001";
const MARKET_URL = process.env.NEXT_PUBLIC_MARKET_URL ?? "http://localhost:8002";
const ANN_URL = process.env.NEXT_PUBLIC_ANN_URL ?? "http://localhost:8003";
/** Direct portfolio health check; book/recs go through gateway when authenticated. */
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
  sources?: string[];
  newsExcerpt?: string;
  socialExcerpt?: string;
};

export type IntelligenceSummary = {
  as_of?: string;
  sources_used?: string[];
  tickers_with_news?: string[];
  tickers_with_social?: string[];
  tickers_with_filings?: string[];
  headline_count?: number;
  social_count?: number;
  macro_tickers?: string[];
  geo_tickers?: string[];
  sample_headlines?: { source?: string; title?: string; tickers?: string[] }[];
  sample_social?: { ticker?: string; text?: string; source?: string }[];
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

function mapPortfolio(data: Record<string, unknown>, source: "live" | "demo"): LivePortfolio {
  return {
    cash: Number(data.cash ?? 0),
    equity: Number(data.equity ?? 0),
    drawdown: Number(data.drawdown ?? 0),
    totalPnl: data.totalPnl != null ? Number(data.totalPnl) : undefined,
    asOf: (data.asOf as string | null) ?? null,
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
    source,
  };
}

/** Unauthenticated server fetch — demo fallback. Prefer fetchPortfolioAuthed after login. */
export async function fetchPortfolio(): Promise<LivePortfolio> {
  try {
    const res = await fetch(`${PORTFOLIO_URL}/v1/portfolio`, { cache: "no-store" });
    if (!res.ok) return { ...demoPortfolio(), source: "demo" };
    return mapPortfolio(await res.json(), "live");
  } catch {
    return { ...demoPortfolio(), source: "demo" };
  }
}

export async function fetchPortfolioAuthed(_token?: string | null): Promise<LivePortfolio> {
  try {
    const res = await authFetch("/v1/portfolio");
    if (!res.ok) return { ...demoPortfolio(), source: "demo" };
    return mapPortfolio(await res.json(), "live");
  } catch {
    return { ...demoPortfolio(), source: "demo" };
  }
}

export async function fetchRecommendationsAuthed(_token?: string | null): Promise<DemoRecommendation[]> {
  try {
    const res = await authFetch("/v1/portfolio/recommendations");
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export async function fetchBrokerStatus(): Promise<BrokerStatus> {
  try {
    const res = await authFetch("/v1/portfolio/broker");
    if (!res.ok) {
      return {
        broker: "unknown",
        connected: false,
        mode: "local_paper",
        has_alpaca_keys: false,
        live_trading_armed: false,
        live_connect_allowed: false,
        account_ok: false,
        docs: [],
        setup_url: "https://app.alpaca.markets/paper/dashboard/overview",
      };
    }
    return res.json();
  } catch {
    return {
      broker: "unknown",
      connected: false,
      mode: "local_paper",
      has_alpaca_keys: false,
      live_trading_armed: false,
      live_connect_allowed: false,
      account_ok: false,
      docs: [],
      setup_url: "https://app.alpaca.markets/paper/dashboard/overview",
    };
  }
}

export type BrokerStatus = {
  broker: string;
  connected: boolean;
  mode: string;
  has_alpaca_keys: boolean;
  live_trading_armed: boolean;
  live_connect_allowed?: boolean;
  account_ok?: boolean;
  base_url?: string | null;
  execution_mode?: string;
  enable_live_trading?: boolean;
  connected_via?: string;
  error?: string;
  account?: {
    cash?: string;
    equity?: string;
    status?: string;
    paper?: boolean;
  };
  docs: string[];
  setup_url: string;
};

export async function connectAlpacaBroker(input: {
  api_key: string;
  secret_key: string;
  paper?: boolean;
}): Promise<BrokerStatus> {
  const res = await authFetch("/v1/portfolio/broker/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      api_key: input.api_key,
      secret_key: input.secret_key,
      paper: input.paper ?? true,
    }),
  });
  if (!res.ok) {
    let message = "Broker connect failed";
    try {
      const payload = await res.json();
      if (typeof payload?.detail === "string") message = payload.detail;
      else if (payload?.detail) message = JSON.stringify(payload.detail);
    } catch {
      const detail = await res.text();
      if (detail) message = detail;
    }
    throw new Error(message);
  }
  return res.json();
}

export async function disconnectAlpacaBroker(): Promise<BrokerStatus> {
  const res = await authFetch("/v1/portfolio/broker/disconnect", { method: "POST" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Disconnect failed");
  }
  return res.json();
}

export type CycleResult = {
  approved_trades?: number;
  rejected_trades?: number;
  closed_outcomes?: number;
  open_lots?: number;
  equity?: number;
  cash?: number;
  signals?: number;
  intelligence?: IntelligenceSummary;
  cycle_id?: string;
};

export type BlotterEvent = {
  type: string;
  at?: string;
  cycle_id?: string;
  ticker?: string;
  side?: string;
  qty?: string;
  price?: string;
  reasons?: string[];
  pnl?: number;
  approved_trades?: number;
  rejected_trades?: number;
  closed_outcomes?: number;
  sources?: string[];
  headline_count?: number;
  social_count?: number;
  correct_direction?: boolean;
  actual_return?: number;
  predicted_return?: number;
};

export type BlotterResponse = {
  events: BlotterEvent[];
  cycles: Record<string, unknown>[];
};

export type JournalEntry = {
  id: string;
  ticker: string;
  action: string;
  predictedReturn: number;
  actualReturn: number;
  correctDirection: boolean;
  pnl: number;
  confidence: number;
  holdingDays: number;
  closedAt?: string | null;
  sources: string[];
  newsExcerpt?: string;
  socialExcerpt?: string;
  thesis?: string;
  modelVersions?: string[];
};

export type JournalResponse = {
  entries: JournalEntry[];
  stats: {
    sampleSize: number;
    directionAccuracy: number | null;
    avgPredictedReturn: number | null;
    avgActualReturn: number | null;
    avgPnl: number | null;
  };
  calibration: {
    temperature: number;
    updated?: boolean;
    sampleSize?: number;
  };
  openLots: number;
};

export type AutopilotStatus = {
  enabled: boolean;
  interval_minutes: number;
  quiet_start_hour: number;
  quiet_end_hour: number;
  kill_switch: boolean;
  tickers?: string | null;
  in_quiet_hours: boolean;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_error?: string | null;
  last_result?: Record<string, unknown> | null;
  runs: number;
};

export async function runPortfolioCycle(tickers?: string): Promise<CycleResult> {
  const qs = tickers ? `?tickers=${encodeURIComponent(tickers)}` : "";
  // Intel gather (RSS/Reddit/local) can take >8s — use a longer timeout.
  const res = await fetchWithTimeout(
    `${API_URL}/v1/portfolio/run${qs}`,
    { method: "POST", credentials: "include", cache: "no-store" },
    45000,
  );
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Cycle failed");
  }
  return res.json();
}

export async function fetchBlotter(limit = 80): Promise<BlotterResponse> {
  const res = await authFetch(`/v1/portfolio/blotter?limit=${limit}`);
  if (!res.ok) return { events: [], cycles: [] };
  return res.json();
}

export async function fetchJournal(limit = 50): Promise<JournalResponse> {
  const res = await authFetch(`/v1/portfolio/journal?limit=${limit}`);
  if (!res.ok) {
    return {
      entries: [],
      stats: {
        sampleSize: 0,
        directionAccuracy: null,
        avgPredictedReturn: null,
        avgActualReturn: null,
        avgPnl: null,
      },
      calibration: { temperature: 1.2 },
      openLots: 0,
    };
  }
  return res.json();
}

export async function fetchAutopilot(): Promise<AutopilotStatus | null> {
  const res = await authFetch("/v1/portfolio/autopilot");
  if (!res.ok) return null;
  return res.json();
}

export async function updateAutopilot(body: Partial<AutopilotStatus> & {
  enabled: boolean;
  interval_minutes: number;
  quiet_start_hour: number;
  quiet_end_hour: number;
  kill_switch: boolean;
}): Promise<AutopilotStatus> {
  const res = await authFetch("/v1/portfolio/autopilot", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Autopilot update failed");
  }
  return res.json();
}

export async function startAutopilot(): Promise<AutopilotStatus> {
  const res = await authFetch("/v1/portfolio/autopilot/start", { method: "POST" });
  if (!res.ok) throw new Error("Failed to start autopilot");
  return res.json();
}

export async function stopAutopilot(): Promise<AutopilotStatus> {
  const res = await authFetch("/v1/portfolio/autopilot/stop", { method: "POST" });
  if (!res.ok) throw new Error("Failed to stop autopilot");
  return res.json();
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  ms = 8000,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("API not reachable — is the gateway running on :8000?");
    }
    throw new Error("API not reachable — is the gateway running on :8000?");
  } finally {
    clearTimeout(timer);
  }
}

export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return fetchWithTimeout(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    cache: "no-store",
    headers: init.headers,
  });
}

export async function sessionLogin(email: string, password: string): Promise<{
  id: string;
  email: string;
  full_name: string;
  role: string;
}> {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);
  let res: Response;
  try {
    res = await fetchWithTimeout(`${API_URL}/v1/auth/session/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
      credentials: "include",
    });
  } catch (err) {
    throw err instanceof Error ? err : new Error("Sign-in failed");
  }
  if (!res.ok) throw new Error("Invalid credentials");
  return res.json();
}

export async function sessionLogout(): Promise<void> {
  try {
    await fetchWithTimeout(`${API_URL}/v1/auth/session/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    /* ignore offline logout */
  }
}

export async function fetchMe(): Promise<{
  id: string;
  email: string;
  full_name: string;
  role: string;
} | null> {
  try {
    const res = await authFetch("/v1/me");
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/** @deprecated Prefer sessionLogin — kept for API clients */
export async function loginRequest(
  email: string,
  password: string,
): Promise<{ access_token: string; refresh_token: string }> {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);
  const res = await fetch(`${API_URL}/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    throw new Error("Invalid credentials");
  }
  return res.json();
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
