import React from 'react';
import { Layers } from 'lucide-react';
import { RegimeAssessment, MarketSnapshot } from '../types/market';

interface RegimeTechnicalProps {
  regime: RegimeAssessment | null;
  snapshot: MarketSnapshot | null;
  symbol: string;
}

export const RegimeTechnical: React.FC<RegimeTechnicalProps> = ({ regime, snapshot, symbol }) => {
  if (!regime) {
    return (
      <div className="glass-panel rounded-2xl p-6 border border-slate-800 bg-[#0f172a]/70 flex flex-col items-center justify-center text-center min-h-[220px]">
        <Layers className="w-8 h-8 text-sky-400/60 mb-2" />
        <h3 className="text-sm font-semibold text-slate-200">Awaiting regime classification</h3>
        <p className="text-xs text-slate-400 mt-1 max-w-md">
          Run the backend agent to compute live market structure and regime for {symbol}.
        </p>
      </div>
    );
  }

  const currentRegime = regime.regime;
  const confidence = Math.round((regime.confidence || 0) * 100);

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
  const spotPrice = quote?.last_price;

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

      <div className={`p-4 rounded-xl border ${currentCfg.bg} ${currentCfg.border} mb-5`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className={`text-base font-extrabold tracking-wide ${currentCfg.text}`}>
              {currentCfg.label}
            </div>
            <p className="text-xs text-slate-300 mt-0.5">{currentCfg.desc}</p>
          </div>
          {regime.driver && (
            <div className="text-[11px] text-slate-300 bg-slate-900/60 px-3 py-1.5 rounded-lg border border-slate-800/80 font-mono">
              {regime.driver}
            </div>
          )}
        </div>
      </div>

      {spotPrice != null && (
        <div className="text-xs text-slate-400">
          Spot reference: <span className="mono-num text-slate-200 font-semibold">{spotPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
        </div>
      )}
    </div>
  );
};
