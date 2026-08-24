import React, { useState } from 'react';
import { Target, TrendingUp, BarChart3, Filter, ArrowUp, ArrowDown } from 'lucide-react';
import { OptionChainSnapshot, OptionEntry } from '../types/market';

interface OptionsAnalyticsProps {
  chain: OptionChainSnapshot | null;
  symbol: string;
}

export const OptionsAnalytics: React.FC<OptionsAnalyticsProps> = ({ chain, symbol }) => {
  const [filterMoneyness, setFilterMoneyness] = useState<'all' | 'near'>('near');

  const spot = chain?.spot_price || (symbol === 'NIFTY' ? 24825.4 : 52340.2);
  const entries = chain?.entries || [];

  // Group by strike
  const strikesMap = new Map<number, { strike: number; call?: OptionEntry; put?: OptionEntry }>();
  entries.forEach((e) => {
    const existing = strikesMap.get(e.strike) || { strike: e.strike };
    if (e.option_type === 'call') existing.call = e;
    if (e.option_type === 'put') existing.put = e;
    strikesMap.set(e.strike, existing);
  });

  const sortedStrikes = Array.from(strikesMap.values()).sort((a, b) => a.strike - b.strike);

  // Calculate totals
  let totalCallOi = 0;
  let totalPutOi = 0;
  let maxCallOi = 0;
  let maxCallStrike = 0;
  let maxPutOi = 0;
  let maxPutStrike = 0;

  sortedStrikes.forEach((row) => {
    const cOi = row.call?.open_interest || 0;
    const pOi = row.put?.open_interest || 0;
    totalCallOi += cOi;
    totalPutOi += pOi;

    if (cOi > maxCallOi) {
      maxCallOi = cOi;
      maxCallStrike = row.strike;
    }
    if (pOi > maxPutOi) {
      maxPutOi = pOi;
      maxPutStrike = row.strike;
    }
  });

  const pcr = totalCallOi > 0 ? totalPutOi / totalCallOi : 1.15;
  const pcrSentiment = pcr > 1.2 ? 'Bullish Support' : pcr < 0.8 ? 'Bearish Resistance' : 'Neutral Balance';

  // Filter strikes if near
  const displayStrikes = filterMoneyness === 'near'
    ? sortedStrikes.filter((s) => Math.abs(s.strike - spot) <= (symbol === 'NIFTY' ? 300 : 700))
    : sortedStrikes;

  return (
    <div className="glass-panel rounded-2xl p-6 border border-slate-800 bg-[#0f172a]/70">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800/80 mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <BarChart3 className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">Options Chain & Open Interest (OI) Analysis</h3>
            <p className="text-xs text-slate-400">Derivatives structure, PCR sentiment, and strike-level buildup</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setFilterMoneyness(filterMoneyness === 'near' ? 'all' : 'near')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-300 hover:text-white"
          >
            <Filter className="w-3.5 h-3.5 text-sky-400" />
            {filterMoneyness === 'near' ? 'Showing Near ATM (±300)' : 'Showing All Strikes'}
          </button>
        </div>
      </div>

      {/* PCR & Max OI Summary Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
        {/* PCR */}
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between">
          <div>
            <div className="text-[11px] text-slate-400 font-medium">Put-Call Ratio (PCR)</div>
            <div className="text-xl font-extrabold text-white mono-num mt-0.5">{pcr.toFixed(2)}</div>
          </div>
          <span className={`px-2.5 py-1 rounded-lg text-xs font-bold ${
            pcr > 1.0 ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
          }`}>
            {pcrSentiment}
          </span>
        </div>

        {/* Call Resistance Strike */}
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between">
          <div>
            <div className="text-[11px] text-rose-400 font-medium">Call Resistance (Max Call OI)</div>
            <div className="text-xl font-extrabold text-rose-400 mono-num mt-0.5">
              {(maxCallStrike || 25000).toLocaleString('en-IN')}
            </div>
          </div>
          <div className="text-right text-[11px] text-slate-400 mono-num">
            <div>{(maxCallOi / 100000).toFixed(1)}L OI</div>
            <div className="text-rose-400">Ceiling Barrier</div>
          </div>
        </div>

        {/* Put Support Strike */}
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between">
          <div>
            <div className="text-[11px] text-emerald-400 font-medium">Put Support (Max Put OI)</div>
            <div className="text-xl font-extrabold text-emerald-400 mono-num mt-0.5">
              {(maxPutStrike || 24700).toLocaleString('en-IN')}
            </div>
          </div>
          <div className="text-right text-[11px] text-slate-400 mono-num">
            <div>{(maxPutOi / 100000).toFixed(1)}L OI</div>
            <div className="text-emerald-400">Floor Cushion</div>
          </div>
        </div>
      </div>

      {/* Option Chain Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-[#090e1c]/80">
        <table className="w-full text-xs text-left border-collapse">
          <thead>
            <tr className="bg-slate-900/90 text-slate-400 border-b border-slate-800 uppercase tracking-wider text-[10px]">
              <th colSpan={4} className="py-2 px-3 text-center text-rose-400/90 border-r border-slate-800">
                CALLS (CE)
              </th>
              <th className="py-2 px-4 text-center text-sky-400 font-bold bg-slate-800/80">
                STRIKE
              </th>
              <th colSpan={4} className="py-2 px-3 text-center text-emerald-400/90 border-l border-slate-800">
                PUTS (PE)
              </th>
            </tr>
            <tr className="text-slate-400 border-b border-slate-800/80 text-[10px] mono-num">
              <th className="py-2 px-3 text-right">OI</th>
              <th className="py-2 px-2 text-right">Chg OI</th>
              <th className="py-2 px-2 text-right">IV</th>
              <th className="py-2 px-3 text-right border-r border-slate-800">LTP</th>
              <th className="py-2 px-4 text-center bg-slate-800/40 text-slate-200">Price</th>
              <th className="py-2 px-3 text-left border-l border-slate-800">LTP</th>
              <th className="py-2 px-2 text-left">IV</th>
              <th className="py-2 px-2 text-left">Chg OI</th>
              <th className="py-2 px-3 text-left">OI</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50 mono-num">
            {displayStrikes.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-6 text-center text-slate-400 italic">
                  No option chain strikes available. Direct option chain scraper is offline.
                </td>
              </tr>
            ) : (
              displayStrikes.map((row) => {
                const isAtm = Math.abs(row.strike - spot) < (symbol === 'NIFTY' ? 50 : 100);
                const ceOi = row.call?.open_interest || 0;
                const peOi = row.put?.open_interest || 0;
                const ceChg = row.call?.change_in_oi || 0;
                const peChg = row.put?.change_in_oi || 0;

                return (
                  <tr
                    key={row.strike}
                    className={`transition-colors hover:bg-slate-800/40 ${
                      isAtm ? 'bg-sky-500/10 font-bold' : ''
                    }`}
                  >
                    {/* Call OI */}
                    <td className="py-2 px-3 text-right text-slate-300">
                      {ceOi > 0 ? (ceOi / 1000).toFixed(0) + 'k' : '-'}
                    </td>
                    {/* Call Chg OI */}
                    <td className={`py-2 px-2 text-right text-[11px] ${ceChg >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {ceChg !== 0 ? (ceChg > 0 ? '+' : '') + (ceChg / 1000).toFixed(0) + 'k' : '-'}
                    </td>
                    {/* Call IV */}
                    <td className="py-2 px-2 text-right text-slate-400 text-[11px]">
                      {row.call?.iv ? (row.call.iv * 100).toFixed(1) + '%' : '-'}
                    </td>
                    {/* Call LTP */}
                    <td className="py-2 px-3 text-right text-slate-200 border-r border-slate-800 font-semibold">
                      {row.call?.last_price ? row.call.last_price.toFixed(1) : '-'}
                    </td>

                    {/* Strike */}
                    <td className={`py-2 px-4 text-center text-slate-100 font-extrabold ${isAtm ? 'bg-sky-500/20 text-sky-300' : 'bg-slate-800/30'}`}>
                      {row.strike.toLocaleString('en-IN')}
                      {isAtm && <span className="ml-1 text-[9px] px-1 py-0.2 rounded bg-sky-500 text-slate-900">ATM</span>}
                    </td>

                    {/* Put LTP */}
                    <td className="py-2 px-3 text-left text-slate-200 border-l border-slate-800 font-semibold">
                      {row.put?.last_price ? row.put.last_price.toFixed(1) : '-'}
                    </td>
                    {/* Put IV */}
                    <td className="py-2 px-2 text-left text-slate-400 text-[11px]">
                      {row.put?.iv ? (row.put.iv * 100).toFixed(1) + '%' : '-'}
                    </td>
                    {/* Put Chg OI */}
                    <td className={`py-2 px-2 text-left text-[11px] ${peChg >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {peChg !== 0 ? (peChg > 0 ? '+' : '') + (peChg / 1000).toFixed(0) + 'k' : '-'}
                    </td>
                    {/* Put OI */}
                    <td className="py-2 px-3 text-left text-slate-300">
                      {peOi > 0 ? (peOi / 1000).toFixed(0) + 'k' : '-'}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
