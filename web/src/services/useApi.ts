/**
 * React hooks for live API data updates.
 */

import { useState, useEffect } from 'react';
import {
  getSignals,
  getTradeBrief,
  getMarketQuote,
  getPaperTrades,
  getRegime,
  askTraderQuestion,
  checkHealth,
  ApiSignal,
  ApiBrief,
  ApiQuote,
  ApiPaperTrade,
  ApiRegime,
  ApiAnswer,
  ApiSystemStatus,
  getSystemStatus,
} from './apiService';

const POLL_INTERVAL = 5000; // 5 seconds

/**
 * Hook to fetch signals periodically.
 */
export function useSignals() {
  const [signals, setSignals] = useState<ApiSignal[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      const data = await getSignals();
      setSignals(data);
      setLoading(false);
    };

    fetch();
    const interval = setInterval(fetch, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  return { signals, loading };
}

/**
 * Hook to fetch trade brief for a symbol.
 */
export function useTradeBrief(symbol: string) {
  const [brief, setBrief] = useState<ApiBrief | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      const data = await getTradeBrief(symbol);
      setBrief(data);
      setLoading(false);
    };

    fetch();
    const interval = setInterval(fetch, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [symbol]);

  return { brief, loading };
}

/**
 * Hook to fetch market quote for a symbol.
 */
export function useMarketQuote(symbol: string) {
  const [quote, setQuote] = useState<ApiQuote | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      const data = await getMarketQuote(symbol);
      setQuote(data);
      setLoading(false);
    };

    fetch();
    const interval = setInterval(fetch, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [symbol]);

  return { quote, loading };
}

/**
 * Hook to fetch paper trading positions.
 */
export function usePaperTrades() {
  const [trades, setTrades] = useState<ApiPaperTrade[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      const data = await getPaperTrades();
      setTrades(data);
      setLoading(false);
    };

    fetch();
    const interval = setInterval(fetch, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  return { trades, loading };
}

/**
 * Hook to fetch market regime.
 */
export function useRegime(symbol: string) {
  const [regime, setRegime] = useState<ApiRegime | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      const data = await getRegime(symbol);
      setRegime(data);
      setLoading(false);
    };

    fetch();
    const interval = setInterval(fetch, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [symbol]);

  return { regime, loading };
}

/**
 * Hook to ask a question to Gemini.
 */
export function useAskQuestion() {
  const [loading, setLoading] = useState(false);

  const ask = async (question: string): Promise<ApiAnswer | null> => {
    setLoading(true);
    try {
      const answer = await askTraderQuestion(question);
      setLoading(false);
      return answer;
    } catch (e) {
      console.error('Error asking question:', e);
      setLoading(false);
      return null;
    }
  };

  return { ask, loading };
}

/**
 * Hook to check API health and system status.
 */
export function useApiHealth() {
  const [healthy, setHealthy] = useState(false);
  const [system, setSystem] = useState<ApiSystemStatus>({
    ok: false,
    backend: 'unhealthy',
    api: 'unhealthy',
    ai_ready: false,
    market: 'india',
    provider: 'indstocks',
    market_open: false,
    message: 'checking health...',
  });

  useEffect(() => {
    const check = async () => {
      const ok = await checkHealth();
      const status = await getSystemStatus();
      setHealthy(ok && status.ok);
      setSystem(status);
    };

    check();
    const interval = setInterval(check, 10000); // Check every 10 seconds
    return () => clearInterval(interval);
  }, []);

  return { healthy, system };
}
