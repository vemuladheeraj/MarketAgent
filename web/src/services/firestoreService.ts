import {
  collection,
  onSnapshot,
  query,
  orderBy,
  limit,
  DocumentData,
} from 'firebase/firestore';
import { db } from '../config/firebase';
import {
  MarketSnapshot,
  GeminiAnalysis,
  RegimeAssessment,
  Signal,
  PaperTrade,
  RiskState,
  SystemEvent,
} from '../types/market';

// --------------------------------------------------------------------------
// Real-time Firestore Listeners
// --------------------------------------------------------------------------

export function subscribeLatestSnapshot(
  callback: (data: MarketSnapshot | null) => void,
  onError?: (error: Error) => void
) {
  try {
    const coll = collection(db, 'marketSnapshots');
    return onSnapshot(
      coll,
      (snap) => {
        if (snap.empty) {
          callback(null);
          return;
        }
        // Pick latest by timestamp or doc ID
        const docs = snap.docs.map((d) => ({
          id: d.id,
          ...d.data(),
        })) as MarketSnapshot[];
        docs.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
        callback(docs[0] || null);
      },
      (err) => {
        console.warn('Firestore snapshot subscription error:', err);
        onError?.(err);
      }
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}

export function subscribeGeminiAnalyses(
  symbol: string,
  callback: (data: GeminiAnalysis | null) => void,
  onError?: (error: Error) => void
) {
  try {
    const coll = collection(db, 'geminiAnalyses');
    return onSnapshot(
      coll,
      (snap) => {
        if (snap.empty) {
          callback(null);
          return;
        }
        const docs = snap.docs
          .map((d) => ({ id: d.id, ...d.data() } as GeminiAnalysis))
          .filter((a) => !symbol || a.symbol?.toUpperCase() === symbol.toUpperCase());
        docs.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
        callback(docs[0] || null);
      },
      (err) => onError?.(err)
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}

export function subscribeRegimes(
  symbol: string,
  callback: (data: RegimeAssessment | null) => void,
  onError?: (error: Error) => void
) {
  try {
    const coll = collection(db, 'marketRegimes');
    return onSnapshot(
      coll,
      (snap) => {
        if (snap.empty) {
          callback(null);
          return;
        }
        const docs = snap.docs
          .map((d) => ({ id: d.id, ...d.data() } as RegimeAssessment))
          .filter((a) => !symbol || a.symbol?.toUpperCase() === symbol.toUpperCase());
        docs.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
        callback(docs[0] || null);
      },
      (err) => onError?.(err)
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}

export function subscribeSignals(
  callback: (signals: Signal[]) => void,
  onError?: (error: Error) => void
) {
  try {
    const coll = collection(db, 'signals');
    return onSnapshot(
      coll,
      (snap) => {
        const docs = snap.docs.map((d) => ({ id: d.id, ...d.data() } as Signal));
        docs.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
        callback(docs);
      },
      (err) => onError?.(err)
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}

export function subscribePaperTrades(
  callback: (trades: PaperTrade[]) => void,
  onError?: (error: Error) => void
) {
  try {
    const coll = collection(db, 'paperTrades');
    return onSnapshot(
      coll,
      (snap) => {
        const docs = snap.docs.map((d) => ({ id: d.id, ...d.data() } as PaperTrade));
        docs.sort((a, b) => (b.entry_time || '').localeCompare(a.entry_time || ''));
        callback(docs);
      },
      (err) => onError?.(err)
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}

export function subscribeSystemEvents(
  callback: (events: SystemEvent[]) => void,
  onError?: (error: Error) => void
) {
  try {
    const coll = collection(db, 'systemEvents');
    return onSnapshot(
      coll,
      (snap) => {
        const docs = snap.docs.map((d) => ({ id: d.id, ...d.data() } as SystemEvent));
        docs.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
        callback(docs.slice(0, 30));
      },
      (err) => onError?.(err)
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}

// --------------------------------------------------------------------------
// High-Quality Fallback Demo Data for Instant Exploration
// --------------------------------------------------------------------------

export const DEMO_SNAPSHOT: MarketSnapshot = {
  id: 'demo_snap',
  timestamp: new Date().toISOString(),
  quotes: {
    NIFTY: {
      symbol: 'NIFTY',
      timestamp: new Date().toISOString(),
      last_price: 24825.40,
      open: 24760.00,
      high: 24890.15,
      low: 24740.30,
      previous_close: 24750.80,
      bid: 24825.35,
      ask: 24825.45,
      volume: 18450000,
    },
    BANKNIFTY: {
      symbol: 'BANKNIFTY',
      timestamp: new Date().toISOString(),
      last_price: 52340.20,
      open: 52100.00,
      high: 52450.80,
      low: 52020.00,
      previous_close: 52050.00,
      bid: 52340.00,
      ask: 52340.50,
      volume: 8750000,
    },
  },
  option_chains: {
    NIFTY: {
      underlying_symbol: 'NIFTY',
      timestamp: new Date().toISOString(),
      spot_price: 24825.40,
      expiry_date: new Date(Date.now() + 3 * 86400000).toISOString(),
      entries: [
        { strike: 24600, option_type: 'call', open_interest: 85400, change_in_oi: -12000, last_price: 255.0, bid: 254.0, ask: 256.0, iv: 0.132, moneyness: 'itm' },
        { strike: 24600, option_type: 'put', open_interest: 145000, change_in_oi: 24000, last_price: 28.5, bid: 28.0, ask: 29.0, iv: 0.141, moneyness: 'otm' },
        { strike: 24700, option_type: 'call', open_interest: 112000, change_in_oi: -5000, last_price: 172.0, bid: 171.5, ask: 172.5, iv: 0.128, moneyness: 'itm' },
        { strike: 24700, option_type: 'put', open_interest: 198000, change_in_oi: 42000, last_price: 45.0, bid: 44.5, ask: 45.5, iv: 0.138, moneyness: 'otm' },
        { strike: 24800, option_type: 'call', open_interest: 185000, change_in_oi: 15000, last_price: 104.0, bid: 103.5, ask: 104.5, iv: 0.125, moneyness: 'itm' },
        { strike: 24800, option_type: 'put', open_interest: 215000, change_in_oi: 38000, last_price: 78.0, bid: 77.5, ask: 78.5, iv: 0.134, moneyness: 'otm' },
        { strike: 24900, option_type: 'call', open_interest: 245000, change_in_oi: 56000, last_price: 52.0, bid: 51.5, ask: 52.5, iv: 0.122, moneyness: 'otm' },
        { strike: 24900, option_type: 'put', open_interest: 82000, change_in_oi: -9000, last_price: 126.0, bid: 125.0, ask: 127.0, iv: 0.131, moneyness: 'itm' },
        { strike: 25000, option_type: 'call', open_interest: 320000, change_in_oi: 78000, last_price: 22.0, bid: 21.5, ask: 22.5, iv: 0.120, moneyness: 'otm' },
        { strike: 25000, option_type: 'put', open_interest: 45000, change_in_oi: -15000, last_price: 195.0, bid: 194.0, ask: 196.0, iv: 0.130, moneyness: 'itm' },
      ],
    },
  },
  breadth: {
    timestamp: new Date().toISOString(),
    advancers: 34,
    decliners: 16,
    unchanged: 0,
    advance_decline_ratio: 2.125,
  },
  vix: 13.82,
  fii_net_buy: 1420.5,
  dii_net_buy: 980.2,
};

export const DEMO_GEMINI: GeminiAnalysis = {
  id: 'demo_gemini',
  symbol: 'NIFTY',
  timestamp: new Date().toISOString(),
  market_bias: 'BULLISH',
  confidence: 0.82,
  summary: 'NIFTY is sustaining above the 24,800 psychological barrier with strong call unwinding and heavy put buildup at 24,700-24,800. Breadth is positive (34 Advances / 16 Declines) and India VIX remains subdued near 13.82.',
  key_factors: [
    'Price holding firm above 20-EMA (24,720) with positive relative momentum',
    'Massive Put OI addition (+38k) at 24,800 strike creating firm intraday cushion',
    'India VIX cooled to 13.82 (-2.4%), reducing tail-risk premium',
  ],
  supporting_factors: [
    'Advance/Decline ratio of 2.12 confirms broad-market participation',
    'FIIs turned net buyers (+1,420 Cr INR) in cash equity segment',
  ],
  conflicting_factors: [
    '25,000 Call strike holds massive 3.2L OI resistance ceiling',
  ],
  risks: [
    'Potential intraday consolidation if index fails to break through 24,900 resistance with heavy volume',
  ],
  signal_interpretation: 'Bullish continuation setup active above 24,800 with 1:2.1 risk-reward profile toward 24,950 target.',
  explanation: 'Synthesized with Google Gemini 2.5 Flash from verified quantitative indicators, market breadth, and derivatives OI structure.',
  contradictions: [],
};

export const DEMO_REGIME: RegimeAssessment = {
  id: 'demo_regime',
  symbol: 'NIFTY',
  timestamp: new Date().toISOString(),
  regime: 'uptrend',
  confidence: 0.85,
  trend_score: 1.0,
  volatility_score: 0.28,
  breadth_score: 0.75,
  driver: 'ADX(14)=26.4 > 25, Price > SMA20 > SMA50, Supertrend Green',
};

export const DEMO_SIGNALS: Signal[] = [
  {
    id: 'sig_1',
    signal_id: 'sig_orb_nifty_01',
    symbol: 'NIFTY',
    timestamp: new Date().toISOString(),
    strategy_name: 'Opening Range Breakout',
    score: 84.5,
    accepted: true,
    classification: 'high_quality',
    candidate: {
      strategy_name: 'Opening Range Breakout',
      symbol: 'NIFTY',
      direction: 'long',
      entry_price: 24820.0,
      stop_loss: 24760.0,
      target_1: 24910.0,
      target_2: 24980.0,
      invalidation_level: 24740.0,
      risk_reward_ratio: 2.15,
      gross_expected_value: 1.08,
      net_expected_value: 0.94,
      explanation: 'High of first 15-min candle broken with volume confirmation and ADX > 25.',
    },
  },
  {
    id: 'sig_2',
    signal_id: 'sig_vwap_bnifty_02',
    symbol: 'BANKNIFTY',
    timestamp: new Date().toISOString(),
    strategy_name: 'VWAP Momentum',
    score: 76.0,
    accepted: true,
    classification: 'valid',
    candidate: {
      strategy_name: 'VWAP Momentum',
      symbol: 'BANKNIFTY',
      direction: 'long',
      entry_price: 52320.0,
      stop_loss: 52180.0,
      target_1: 52580.0,
      target_2: 52750.0,
      invalidation_level: 52120.0,
      risk_reward_ratio: 1.86,
      gross_expected_value: 0.93,
      net_expected_value: 0.78,
      explanation: 'Sustained pullback above intraday VWAP with bullish candle close.',
    },
  },
];
