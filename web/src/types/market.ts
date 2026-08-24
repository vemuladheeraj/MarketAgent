export type MarketRegimeType =
  | 'strong_uptrend'
  | 'uptrend'
  | 'range'
  | 'downtrend'
  | 'strong_downtrend'
  | 'high_volatility'
  | 'low_volatility'
  | 'event_driven'
  | 'uncertain';

export type MarketBiasType = 'BULLISH' | 'BEARISH' | 'NEUTRAL' | 'UNCERTAIN';

export type SignalClassificationType =
  | 'exceptional'
  | 'high_quality'
  | 'valid'
  | 'watch'
  | 'weak'
  | 'no_trade';

export interface Quote {
  symbol: string;
  timestamp: string;
  bid: number;
  ask: number;
  last_price: number;
  open: number;
  high: number;
  low: number;
  previous_close: number;
  volume: number;
}

export interface OptionEntry {
  strike: number;
  option_type: 'call' | 'put';
  open_interest: number;
  change_in_oi: number;
  last_price: number;
  bid: number;
  ask: number;
  iv: number;
  moneyness?: 'itm' | 'atm' | 'otm';
  position_build?: string;
}

export interface OptionChainSnapshot {
  underlying_symbol: string;
  timestamp: string;
  spot_price: number;
  expiry_date: string;
  entries: OptionEntry[];
}

export interface BreadthSnapshot {
  timestamp: string;
  advancers: number;
  decliners: number;
  unchanged: number;
  advance_decline_ratio?: number;
}

export interface MarketSnapshot {
  id?: string;
  timestamp: string;
  quotes: Record<string, Quote>;
  option_chains: Record<string, OptionChainSnapshot>;
  breadth?: BreadthSnapshot;
  vix?: number;
  fii_net_buy?: number;
  dii_net_buy?: number;
  meta?: Record<string, any>;
}

export interface Contradiction {
  factor_a: string;
  factor_b: string;
  description: string;
  severity: string;
}

export interface GeminiAnalysis {
  id?: string;
  symbol: string;
  timestamp: string;
  summary: string;
  market_bias: MarketBiasType;
  key_factors: string[];
  supporting_factors: string[];
  conflicting_factors: string[];
  risks: string[];
  signal_interpretation: string;
  confidence: number;
  explanation: string;
  contradictions: Contradiction[];
  grounded_data_summary?: Record<string, any>;
}

export interface RegimeAssessment {
  id?: string;
  symbol: string;
  timestamp: string;
  regime: MarketRegimeType;
  confidence: number;
  trend_score: number;
  volatility_score?: number;
  breadth_score?: number;
  driver?: string;
}

export interface CandidateSetup {
  strategy_name: string;
  symbol: string;
  direction: 'long' | 'short';
  entry_price: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  invalidation_level: number;
  risk_reward_ratio: number;
  gross_expected_value: number;
  net_expected_value: number;
  explanation: string;
}

export interface Signal {
  id?: string;
  signal_id: string;
  symbol: string;
  timestamp: string;
  strategy_name: string;
  candidate: CandidateSetup;
  score: number;
  accepted: boolean;
  classification: SignalClassificationType;
  rejection_reason?: string;
}

export interface PaperTrade {
  id?: string;
  trade_id: string;
  signal_id: string;
  symbol: string;
  direction: 'long' | 'short';
  entry_time: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  trailing_stop?: number;
  quantity: number;
  position_size_inr: number;
  stage: 'signal' | 'paper_entry' | 'monitor' | 'exit' | 'result';
  current_price?: number;
  unrealized_pnl_net?: number;
  exit_price?: number;
  exit_time?: string;
  exit_reason?: string;
  realized_pnl_net?: number;
}

export interface RiskState {
  id?: string;
  account_size: number;
  realized_pnl_today: number;
  daily_loss_limit_hit: boolean;
  open_paper_trades_count: number;
  max_trades_today_hit: boolean;
  cooldown_until?: string;
  emergency_halt: boolean;
}

export interface SystemEvent {
  id?: string;
  event_type: string;
  timestamp: string;
  message: string;
  details?: Record<string, any>;
}
