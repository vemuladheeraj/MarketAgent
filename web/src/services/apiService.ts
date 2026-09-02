/**
 * REST API service for the MarketAgent backend.
 * Provides methods to fetch data from /api/* endpoints.
 */

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000';

export interface ApiSignal {
  symbol: string;
  strategy: string;
  direction: string;
  entry: number;
  stop_loss: number;
  targets: number[];
  score: number;
  classification: string;
  accepted: boolean;
  timestamp: string;
}

export interface ApiQuote {
  symbol: string;
  last_price: number | null;
  bid: number | null;
  ask: number | null;
  bid_size: number | null;
  ask_size: number | null;
  volume: number | null;
  timestamp: string;
}

export interface ApiContract {
  tradingsymbol: string;
  strike: number;
  option_type: string;
  last_price: number | null;
  bid: number | null;
  ask: number | null;
  delta: number | null;
  iv: number | null;
  open_interest: number;
  spread_pct: number | null;
}

export interface ApiBrief {
  symbol: string;
  action: string; // "BUY" | "SELL" | "WAIT"
  strategy: string;
  direction: string | null;
  entry: number | null;
  stop_loss: number | null;
  targets: number[];
  contract: ApiContract | null;
  risk_reward: number | null;
  lots: number | null;
  probability: number | null;
  score: number | null;
  regime: string;
  rationale: string[];
  warnings: string[];
  waiting_reason: string | null;
  risk_amount?: number | null;
  target_amount?: number | null;
  generated_at: string;
  valid_until: string;
}

export interface ApiPaperTrade {
  position_id: string;
  symbol: string;
  entry_price: number;
  entry_time: string;
  quantity: number;
  direction: string;
  strategy: string;
  stop_loss: number;
  targets: number[];
  current_price: number | null;
  stage: string;
  pnl: number | null;
  pnl_pct: number | null;
}

export interface ApiRegime {
  symbol: string;
  regime: string;
  confidence: number;
  reasons: string[];
  timestamp: string;
}

export interface ApiAnswer {
  question: string;
  answer: string;
}

export interface ApiRuntimeConfig {
  market: string;
  provider: string;
  available_markets: string[];
  available_providers: string[];
}

export interface ApiSystemStatus {
  ok: boolean;
  backend: string;
  api: string;
  ai_ready: boolean;
  market: string;
  provider: string;
  market_open: boolean;
  message: string;
}

/**
 * Check if the API is reachable.
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { method: 'GET' });
    return res.ok;
  } catch (e) {
    console.warn('API health check failed:', e);
    return false;
  }
}

/**
 * Read the current runtime health and market status.
 */
export async function getSystemStatus(): Promise<ApiSystemStatus> {
  try {
    const res = await fetch(`${API_BASE}/api/system-status`);
    if (!res.ok) {
      return {
        ok: false,
        backend: 'unhealthy',
        api: 'unhealthy',
        ai_ready: false,
        market: 'india',
        provider: 'indstocks',
        market_open: false,
        message: 'system unavailable',
      };
    }
    return (await res.json()) as ApiSystemStatus;
  } catch (e) {
    return {
      ok: false,
      backend: 'unhealthy',
      api: 'unhealthy',
      ai_ready: false,
      market: 'india',
      provider: 'indstocks',
      market_open: false,
      message: `system error: ${String(e)}`,
    };
  }
}

/**
 * Read the active runtime configuration from the backend.
 */
export async function getRuntimeConfig(): Promise<ApiRuntimeConfig> {
  try {
    const res = await fetch(`${API_BASE}/api/config`);
    if (!res.ok) {
      return {
        market: 'india',
        provider: 'indstocks',
        available_markets: ['india', 'us', 'both'],
        available_providers: ['indstocks', 'nse', 'us_markets'],
      };
    }
    return (await res.json()) as ApiRuntimeConfig;
  } catch (e) {
    console.warn('Failed to fetch runtime config:', e);
    return {
      market: 'india',
      provider: 'indstocks',
      available_markets: ['india', 'us', 'both'],
      available_providers: ['indstocks', 'nse', 'us_markets'],
    };
  }
}

/**
 * Change the active market/provider selection at runtime.
 */
export async function setRuntimeConfig(config: { market: string; provider: string }): Promise<{ ok: boolean; error?: string; market?: string; provider?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!res.ok) {
      return { ok: false, error: 'Failed to update runtime config' };
    }
    return (await res.json()) as { ok: boolean; error?: string; market?: string; provider?: string };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

/**
 * Get recent signals.
 */
export async function getSignals(): Promise<ApiSignal[]> {
  try {
    const res = await fetch(`${API_BASE}/api/signals`);
    if (!res.ok) return [];
    return (await res.json()) as ApiSignal[];
  } catch (e) {
    console.warn('Failed to fetch signals:', e);
    return [];
  }
}

/**
 * Get current market quote for a symbol.
 */
export async function getMarketQuote(symbol: string): Promise<ApiQuote | null> {
  try {
    const res = await fetch(`${API_BASE}/api/market/${encodeURIComponent(symbol)}`);
    if (!res.ok) return null;
    return (await res.json()) as ApiQuote;
  } catch (e) {
    console.warn(`Failed to fetch quote for ${symbol}:`, e);
    return null;
  }
}

/**
 * Get current trade brief for a symbol.
 */
export async function getTradeBrief(symbol: string): Promise<ApiBrief | null> {
  try {
    const res = await fetch(`${API_BASE}/api/brief/${encodeURIComponent(symbol)}`);
    if (!res.ok) return null;
    return (await res.json()) as ApiBrief;
  } catch (e) {
    console.warn(`Failed to fetch brief for ${symbol}:`, e);
    return null;
  }
}

/**
 * Get all paper trading positions.
 */
export async function getPaperTrades(): Promise<ApiPaperTrade[]> {
  try {
    const res = await fetch(`${API_BASE}/api/paper-trades`);
    if (!res.ok) return [];
    return (await res.json()) as ApiPaperTrade[];
  } catch (e) {
    console.warn('Failed to fetch paper trades:', e);
    return [];
  }
}

/**
 * Answer a trader question using Gemini AI.
 */
export async function askTraderQuestion(question: string): Promise<ApiAnswer> {
  try {
    const res = await fetch(`${API_BASE}/api/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) {
      return { question, answer: 'Error: Unable to process question.' };
    }
    return (await res.json()) as ApiAnswer;
  } catch (e) {
    console.warn('Failed to ask question:', e);
    return { question, answer: `Error: ${String(e)}` };
  }
}

/**
 * Get market regime for a symbol.
 */
export async function getRegime(symbol: string): Promise<ApiRegime | null> {
  try {
    const res = await fetch(`${API_BASE}/api/regime/${encodeURIComponent(symbol)}`);
    if (!res.ok) return null;
    return (await res.json()) as ApiRegime;
  } catch (e) {
    console.warn(`Failed to fetch regime for ${symbol}:`, e);
    return null;
  }
}

/**
 * Set up polling for live data.
 */
export function startPolling(interval: number = 5000) {
  return setInterval(() => {
    // Consumers will call the individual fetch functions as needed
  }, interval);
}

/**
 * Stop polling.
 */
export function stopPolling(intervalId: number) {
  clearInterval(intervalId);
}
