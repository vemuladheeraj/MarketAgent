import React from 'react';
import { Target, CheckCircle, XCircle, ArrowUpRight, ArrowDownRight, Award, ShieldAlert } from 'lucide-react';
import { Signal, SignalClassificationType } from '../types/market';

interface SignalsTableProps {
  signals: Signal[];
  selectedSymbol: string;
}

export const SignalsTable: React.FC<SignalsTableProps> = ({ signals, selectedSymbol }) => {
  const filtered = signals.filter(
    (s) => !selectedSymbol || s.symbol?.toUpperCase() === selectedSymbol.toUpperCase()
  );

  const getClassificationBadge = (classification: SignalClassificationType, score: number) => {
    const config: Record<string, { label: string; bg: string; text: string; border: string }> = {
      exceptional: { label: 'EXCEPTIONAL', bg: 'bg-emerald-500/20', text: 'text-emerald-300', border: 'border-emerald-500/40' },
      high_quality: { label: 'HIGH QUALITY', bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30' },
      valid: { label: 'VALID', bg: 'bg-sky-500/15', text: 'text-sky-400', border: 'border-sky-500/30' },
      watch: { label: 'WATCH', bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/30' },
      weak: { label: 'WEAK', bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30' },
      no_trade: { label: 'NO TRADE', bg: 'bg-slate-700/30', text: 'text-slate-400', border: 'border-slate-700' },
    };

    const cfg = config[classification] || config.no_trade;
    return (
      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-extrabold border uppercase ${cfg.bg} ${cfg.text} ${cfg.border}`}>
        <Award className="w-3 h-3" />
        {cfg.label} ({score.toFixed(1)})
      </span>
    );
  };

  return (
    <div className="glass-panel rounded-2xl p-6 border border-slate-800 bg-[#0f172a]/70">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-slate-800/80 mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <Target className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">Quantitative Strategy Signals</h3>
            <p className="text-xs text-slate-400">Deterministic scoring & pre-cost expected value evaluation</p>
          </div>
        </div>

        <div className="text-xs text-slate-400">
          Min Acceptance Score: <strong className="text-sky-400 mono-num font-bold">70.0 / 100</strong>
        </div>
      </div>

      {/* Signals List / Table */}
      {filtered.length === 0 ? (
        <div className="py-8 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800/60 text-xs">
          <ShieldAlert className="w-6 h-6 text-slate-500 mx-auto mb-1.5" />
          No tradable strategy signals for {selectedSymbol} in current regime. Engine is in protective NO_TRADE state.
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((sig) => {
            const isLong = sig.candidate?.direction === 'long';
            return (
              <div
                key={sig.signal_id || sig.id}
                className={`p-4 rounded-xl border transition-all ${
                  sig.accepted
                    ? 'bg-slate-900/80 border-slate-700/80 hover:border-sky-500/40'
                    : 'bg-slate-900/40 border-slate-800/60 opacity-80'
                }`}
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                  {/* Strategy Info */}
                  <div className="flex items-start gap-3">
                    <div
                      className={`p-2 rounded-lg mt-0.5 ${
                        isLong ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                      }`}
                    >
                      {isLong ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-white tracking-tight">
                          {sig.strategy_name}
                        </span>
                        <span
                          className={`text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded ${
                            isLong ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                          }`}
                        >
                          {sig.candidate?.direction?.toUpperCase() || 'LONG'}
                        </span>
                        <span className="text-xs font-semibold text-slate-300">
                          {sig.symbol}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1">
                        {sig.candidate?.explanation || 'Evaluated setup'}
                      </p>
                    </div>
                  </div>

                  {/* Classification Badge & Acceptance */}
                  <div className="flex items-center gap-3 self-start lg:self-auto">
                    {getClassificationBadge(sig.classification, sig.score)}
                    <span
                      className={`flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-md ${
                        sig.accepted
                          ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-800'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {sig.accepted ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                      {sig.accepted ? 'ACCEPTED' : 'FILTERED'}
                    </span>
                  </div>
                </div>

                {/* Quantitative Levels Grid */}
                {sig.candidate && (
                  <div className="grid grid-cols-2 sm:grid-cols-6 gap-2 mt-3 pt-3 border-t border-slate-800/80 text-[11px] mono-num">
                    <div className="p-2 rounded bg-slate-950/60 border border-slate-800/60">
                      <div className="text-slate-400 text-[10px]">Entry Price</div>
                      <div className="font-bold text-slate-200 mt-0.5">{sig.candidate.entry_price.toFixed(1)}</div>
                    </div>
                    <div className="p-2 rounded bg-slate-950/60 border border-slate-800/60">
                      <div className="text-rose-400 text-[10px]">Stop Loss</div>
                      <div className="font-bold text-rose-300 mt-0.5">{sig.candidate.stop_loss.toFixed(1)}</div>
                    </div>
                    <div className="p-2 rounded bg-slate-950/60 border border-slate-800/60">
                      <div className="text-emerald-400 text-[10px]">Target 1</div>
                      <div className="font-bold text-emerald-300 mt-0.5">{sig.candidate.target_1.toFixed(1)}</div>
                    </div>
                    <div className="p-2 rounded bg-slate-950/60 border border-slate-800/60">
                      <div className="text-emerald-400 text-[10px]">Target 2</div>
                      <div className="font-bold text-emerald-300 mt-0.5">{sig.candidate.target_2.toFixed(1)}</div>
                    </div>
                    <div className="p-2 rounded bg-slate-950/60 border border-slate-800/60">
                      <div className="text-sky-400 text-[10px]">Reward:Risk</div>
                      <div className="font-bold text-sky-300 mt-0.5">1:{sig.candidate.risk_reward_ratio?.toFixed(2) || '2.0'}</div>
                    </div>
                    <div className="p-2 rounded bg-slate-950/60 border border-slate-800/60">
                      <div className="text-slate-400 text-[10px]">Net EV</div>
                      <div className="font-bold text-slate-200 mt-0.5">+{sig.candidate.net_expected_value?.toFixed(2) || '0.8'}R</div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
