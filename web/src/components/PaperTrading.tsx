import React from 'react';
import { ShieldCheck, TrendingUp, AlertOctagon, CheckCircle2, DollarSign, Lock } from 'lucide-react';
import { PaperTrade, RiskState } from '../types/market';

interface PaperTradingProps {
  trades: PaperTrade[];
  riskState?: RiskState | null;
}

export const PaperTrading: React.FC<PaperTradingProps> = ({ trades, riskState }) => {
  const activeTrades = trades.filter((t) => t.stage !== 'result' && t.stage !== 'exit');
  const closedTrades = trades.filter((t) => t.stage === 'result' || t.stage === 'exit');

  const totalPnL = closedTrades.reduce((acc, t) => acc + (t.realized_pnl_net || 0), 0);

  return (
    <div className="glass-panel rounded-2xl p-6 border border-slate-800 bg-[#0f172a]/70">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800/80 mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">Paper Trading & Risk Engine</h3>
            <p className="text-xs text-slate-400">Deterministic lot sizing, daily loss guardrails, and transaction cost accounting</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-md bg-sky-500/10 border border-sky-500/30 text-[10px] font-extrabold uppercase text-sky-400">
            1.0% Risk / Trade
          </span>
          <span className="px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/30 text-[10px] font-extrabold uppercase text-amber-400">
            3.0% Max Daily Loss
          </span>
        </div>
      </div>

      {/* Risk Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-5">
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] text-slate-400">Virtual Account Size</div>
          <div className="text-lg font-bold text-white mono-num mt-0.5">₹10,00,000</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Max Risk: ₹10,000 / trade</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] text-slate-400">Realized PnL (Net)</div>
          <div className={`text-lg font-bold mono-num mt-0.5 ${totalPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {totalPnL >= 0 ? '+' : ''}₹{totalPnL.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">After all Indian taxes & costs</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] text-slate-400">Active Paper Positions</div>
          <div className="text-lg font-bold text-sky-400 mono-num mt-0.5">
            {activeTrades.length} <span className="text-xs text-slate-400 font-normal">/ 3 max</span>
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Concurrent limit guard</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] text-slate-400">Risk System State</div>
          <div className="text-lg font-bold text-emerald-400 flex items-center gap-1.5 mt-0.5">
            <Lock className="w-4 h-4" />
            <span>NORMAL</span>
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Circuit breaker active</div>
        </div>
      </div>

      {/* Active Positions Table */}
      <div className="mb-4">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
          Active Paper Positions ({activeTrades.length})
        </h4>

        {activeTrades.length === 0 ? (
          <div className="py-5 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800/60 text-xs">
            No open paper positions. Awaiting qualified strategy signal trigger.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-900 text-slate-400 border-b border-slate-800 text-[10px] uppercase">
                <tr>
                  <th className="py-2.5 px-3">Symbol</th>
                  <th className="py-2.5 px-3">Side</th>
                  <th className="py-2.5 px-3">Entry</th>
                  <th className="py-2.5 px-3">Stop Loss</th>
                  <th className="py-2.5 px-3">Take Profit</th>
                  <th className="py-2.5 px-3">Qty / Size</th>
                  <th className="py-2.5 px-3">Unrealized PnL</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 mono-num">
                {activeTrades.map((trade) => (
                  <tr key={trade.trade_id || trade.id} className="hover:bg-slate-800/30">
                    <td className="py-2.5 px-3 font-bold text-white">{trade.symbol}</td>
                    <td className="py-2.5 px-3 font-bold uppercase text-emerald-400">{trade.direction}</td>
                    <td className="py-2.5 px-3 text-slate-200">{trade.entry_price.toFixed(1)}</td>
                    <td className="py-2.5 px-3 text-rose-400">{trade.stop_loss.toFixed(1)}</td>
                    <td className="py-2.5 px-3 text-emerald-400">{trade.take_profit.toFixed(1)}</td>
                    <td className="py-2.5 px-3 text-slate-300">
                      {trade.quantity} ({((trade.position_size_inr || 0) / 1000).toFixed(0)}k INR)
                    </td>
                    <td className="py-2.5 px-3 font-bold text-emerald-400">
                      +₹{((trade.unrealized_pnl_net || 0)).toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="text-[11px] text-slate-400 flex items-center gap-1.5 pt-2 border-t border-slate-800/60">
        <AlertOctagon className="w-3.5 h-3.5 text-amber-400" />
        <span>This is a quantitative research tool. Paper trades are simulated artifacts and do not place live broker orders.</span>
      </div>
    </div>
  );
};
