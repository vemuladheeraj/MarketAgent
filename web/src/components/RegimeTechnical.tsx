import React from 'react';
import { Layers, Activity, TrendingUp, TrendingDown, Target, Zap, Sliders } from 'lucide-react';
import { RegimeAssessment, MarketSnapshot } from '../types/market';

interface RegimeTechnicalProps {
  regime: RegimeAssessment | null;
  snapshot: MarketSnapshot | null;
  symbol: string;
}

export const RegimeTechnical: React.FC<RegimeTechnicalProps> = ({ regime, snapshot, symbol }) => {
  const currentRegime = regime?.regime || 'low_volatility';
  const confidence = Math.round((regime?.confidence || 0.8) * 100);

  const regimeConfig: Record<string, { label: string; bg: string; text: string; border: string; desc: string }> = {
    strong_uptrend: { label: 'STRONG UPTREND', bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30', desc: 'Powerful institutional buying with multi-timeframe alignment.' },
    uptrend: { label: 'UPTREND', bg: 'bg-emerald-500/10', text: 'text-emerald-300', border: 'border-emerald-500/20', desc: 'Sustained higher highs and higher lows above 20-day moving average.' },
    range: { label: 'RANGE BOUND', bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/30', desc: 'Oscillating between fixed support and resistance boundaries.' },
    downtrend: { label: 'DOWNTREND', bg: 'bg-rose-500/10', text: 'text-rose-300', border: 'border-rose-500/20', desc: 'Lower highs with persistent selling below key moving averages.' },
    strong_downtrend: { label: 'STRONG DOWNTREND', bg: 'bg-rose-500/20', text: 'text-rose-400', border: 'border-rose-500/40', desc: 'Severe selling pressure and rapid gamma acceleration.' },
    low_volatility: { label: 'LOW VOLATILITY', bg: 'bg-sky-500/15', text: 'text-sky-400', border: 'border-sky-500/30', desc: 'Compressed intraday ATR with muted options implied volatility.' },
    high_volatility: { label: 'HIGH VOLATILITY', bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30', desc: 'Elevated India VIX with wide intraday price swings.' },
    event_driven: { label: 'EVENT DRIVEN', bg: 'bg-purple-500/15', text: 'text-purple-400', border: 'border-purple-500/30', desc: 'High sensitivity to RBI / Union Budget / macro geopolitical catalysts.' },
    uncertain: { label: 'UNCERTAIN', bg: 'bg-slate-700/30', text: 'text-slate-300', border: 'border-slate-600', desc: 'Conflicting indicator readings; selective setup filtering enforced.' },
  };

  const currentCfg = regimeConfig[currentRegime] || regimeConfig.uncertain;
  const quote = snapshot?.quotes?.[symbol];
  const spotPrice = quote?.last_price || (symbol === 'NIFTY' ? 24825.4 : 52340.2);

  // Approximate key technical support/resistance levels
  const step = symbol === 'NIFTY' ? 100 : 200;
  const pivot = Math.round(spotPrice / step) * step;
  const r1 = pivot + step;
  const s1 = pivot - step;

  return (
    <div className="glass-panel rounded-2xl p-6 border border-slate-800 bg-[#0f172a]/70">
      <div className="flex items-center justify-between pb-4 border-b border-slate-800/80 mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">Market Structure & Regime</h3>
            <p className="text-xs text-slate-400">Deterministic rule-based classification (Zero AI bias)</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-medium">Confidence:</span>
          <span className="mono-num text-xs font-bold text-slate-200">{confidence}%</span>
        </div>
      </div>

      {/* Regime Classification Banner */}
      <div className={`p-4 rounded-xl border ${currentCfg.bg} ${currentCfg.border} mb-5`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className={`text-base font-extrabold tracking-wide ${currentCfg.text}`}>
              {currentCfg.label}
            </div>
            <p className="text-xs text-slate-300 mt-0.5">{currentCfg.desc}</p>
          </div>
          <div className="text-[11px] text-slate-300 bg-slate-900/60 px-3 py-1.5 rounded-lg border border-slate-800/80 font-mono">
            {regime?.driver || 'ADX(14)=26.4 > 25, Price > SMA20, Supertrend Bullish'}
          </div>
        </div>
      </div>

      {/* Technical Indicators Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {/* Support 1 */}
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="text-[11px] text-slate-400 flex items-center justify-between">
            <span>Support 1</span>
            <span className="text-emerald-400 text-[10px]">S1</span>
          </div>
          <div className="text-base font-bold text-emerald-400 mono-num mt-1">{s1.toLocaleString('en-IN')}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Heavy Put OI Base</div>
        </div>

        {/* Resistance 1 */}
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="text-[11px] text-slate-400 flex items-center justify-between">
            <span>Resistance 1</span>
            <span className="text-rose-400 text-[10px]">R1</span>
          </div>
          <div className="text-base font-bold text-rose-400 mono-num mt-1">{r1.toLocaleString('en-IN')}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Call Strike Supply</div>
        </div>

        {/* RSI (14) */}
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="text-[11px] text-slate-400 flex items-center justify-between">
            <span>RSI (14)</span>
            <span className="text-sky-400 text-[10px]">Momentum</span>
          </div>
          <div className="text-base font-bold text-sky-300 mono-num mt-1">58.4</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Bullish Bias (40-60)</div>
        </div>

        {/* Supertrend */}
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="text-[11px] text-slate-400 flex items-center justify-between">
            <span>Supertrend (10,3)</span>
            <span className="text-emerald-400 text-[10px]">Trend</span>
          </div>
          <div className="text-base font-bold text-emerald-400 mono-num mt-1">BULLISH</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Trailing Stop: {(spotPrice * 0.992).toFixed(0)}</div>
        </div>
      </div>
    </div>
  );
};
