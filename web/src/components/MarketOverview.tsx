import React from 'react';
import { ArrowDownRight, ArrowUpRight, BarChart2, Database, DollarSign, Gauge } from 'lucide-react';
import { MarketSnapshot, Quote } from '../types/market';

interface MarketOverviewProps {
  symbol: string;
  snapshot: MarketSnapshot | null;
}

export const MarketOverview: React.FC<MarketOverviewProps> = ({ symbol, snapshot }) => {
  const quote = snapshot?.quotes?.[symbol] as Quote | undefined;
  const breadth = snapshot?.breadth;
  const vix = snapshot?.vix;
  const fiiNet = snapshot?.fii_net_buy;
  const diiNet = snapshot?.dii_net_buy;

  if (!quote) {
    return (
      <div className="glass-panel rounded-2xl p-8 border border-slate-800 bg-[#0f172a]/70 flex flex-col items-center justify-center text-center min-h-[180px]">
        <Database className="w-8 h-8 text-sky-400/60 mb-2" />
        <h3 className="text-sm font-semibold text-slate-200">Awaiting live market snapshot</h3>
        <p className="text-xs text-slate-400 mt-1 max-w-md">
          Start the backend agent with a real data provider to stream {symbol} quotes, VIX, breadth, and flows into Firestore.
        </p>
      </div>
    );
  }

  const change = quote.last_price - quote.previous_close;
  const changePct = quote.previous_close > 0 ? (change / quote.previous_close) * 100 : 0;
  const isPositive = change >= 0;

  const totalBreadth = (breadth?.advancers || 0) + (breadth?.decliners || 0) + (breadth?.unchanged || 0);
  const advPct = totalBreadth > 0 ? Math.round(((breadth?.advancers || 0) / totalBreadth) * 100) : 0;
  const decPct = totalBreadth > 0 ? Math.round(((breadth?.decliners || 0) / totalBreadth) * 100) : 0;

  const rangeSpan = quote.high - quote.low;
  const rangePosPct = rangeSpan > 0 ? Math.min(100, Math.max(0, ((quote.last_price - quote.low) / rangeSpan) * 100)) : 50;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="glass-panel glass-panel-hover rounded-2xl p-5 border border-slate-800 bg-[#0f172a]/70">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-medium">
          <span>{symbol === 'NIFTY' ? 'NIFTY 50 SPOT' : `${symbol} INDEX`}</span>
          <span className="flex items-center gap-1 text-slate-400">
            Vol: <span className="mono-num text-slate-200 font-semibold">{(quote.volume / 100000).toFixed(1)}L</span>
          </span>
        </div>

        <div className="flex items-baseline gap-3 mb-2">
          <span className="text-3xl font-extrabold text-white tracking-tight mono-num">
            {quote.last_price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
          <div
            className={`flex items-center text-xs font-bold px-2 py-0.5 rounded-md ${
              isPositive
                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
            }`}
          >
            {isPositive ? <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" /> : <ArrowDownRight className="w-3.5 h-3.5 mr-0.5" />}
            <span>{isPositive ? '+' : ''}{change.toFixed(2)}</span>
            <span className="ml-1">({isPositive ? '+' : ''}{changePct.toFixed(2)}%)</span>
          </div>
        </div>

        <div className="mt-3 pt-3 border-t border-slate-800/80 text-[11px]">
          <div className="flex justify-between text-slate-400 mb-1">
            <span>L: <strong className="text-slate-200 mono-num">{quote.low.toFixed(1)}</strong></span>
            <span className="text-sky-400 font-semibold">Day Range</span>
            <span>H: <strong className="text-slate-200 mono-num">{quote.high.toFixed(1)}</strong></span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-500 h-full rounded-full"
              style={{ width: `${rangePosPct}%` }}
            ></div>
          </div>
        </div>
      </div>

      <div className="glass-panel glass-panel-hover rounded-2xl p-5 border border-slate-800 bg-[#0f172a]/70">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-medium">
          <span className="flex items-center gap-1.5">
            <Gauge className="w-4 h-4 text-amber-400" />
            INDIA VIX (Volatility)
          </span>
          {vix != null && (
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
              vix < 14 ? 'bg-emerald-500/15 text-emerald-400' : vix < 18 ? 'bg-amber-500/15 text-amber-400' : 'bg-rose-500/15 text-rose-400'
            }`}>
              {vix < 14 ? 'Low Vol' : vix < 18 ? 'Normal' : 'Elevated'}
            </span>
          )}
        </div>

        {vix != null ? (
          <>
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-3xl font-extrabold text-white tracking-tight mono-num">
                {vix.toFixed(2)}
              </span>
              <span className="text-xs text-slate-400 font-medium">
                {vix < 14 ? 'Calm / Option Selling' : vix < 18 ? 'Standard Drift' : 'High Gamma Risk'}
              </span>
            </div>
            <div className="mt-3 pt-3 border-t border-slate-800/80 text-[11px] flex justify-between text-slate-400">
              <span>Lower Range: <strong className="text-emerald-400 mono-num">11-13</strong></span>
              <span>Baseline: <strong className="text-slate-200 mono-num">15.0</strong></span>
              <span>Risk Level: <strong className={vix > 18 ? 'text-rose-400' : 'text-emerald-400'}>{vix > 18 ? 'HIGH' : 'LOW'}</strong></span>
            </div>
          </>
        ) : (
          <p className="text-xs text-slate-400 mt-4">VIX data not available in the latest snapshot.</p>
        )}
      </div>

      <div className="glass-panel glass-panel-hover rounded-2xl p-5 border border-slate-800 bg-[#0f172a]/70">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-medium">
          <span className="flex items-center gap-1.5">
            <BarChart2 className="w-4 h-4 text-sky-400" />
            NIFTY 50 BREADTH
          </span>
          {breadth?.advance_decline_ratio != null && (
            <span className="mono-num text-xs font-semibold text-slate-300">
              A/D: {breadth.advance_decline_ratio.toFixed(2)}
            </span>
          )}
        </div>

        {breadth ? (
          <>
            <div className="flex items-baseline gap-3 mb-2">
              <span className="text-lg font-bold text-emerald-400 mono-num">
                {breadth.advancers} <span className="text-xs text-slate-400 font-normal">Adv</span>
              </span>
              <span className="text-slate-600">/</span>
              <span className="text-lg font-bold text-rose-400 mono-num">
                {breadth.decliners} <span className="text-xs text-slate-400 font-normal">Dec</span>
              </span>
            </div>
            <div className="mt-3 pt-3 border-t border-slate-800/80">
              <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                <span className="text-emerald-400 font-medium">{advPct}% Bulls</span>
                <span className="text-rose-400 font-medium">{decPct}% Bears</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 flex overflow-hidden">
                <div className="bg-emerald-500 h-full transition-all" style={{ width: `${advPct}%` }}></div>
                <div className="bg-rose-500 h-full transition-all" style={{ width: `${decPct}%` }}></div>
              </div>
            </div>
          </>
        ) : (
          <p className="text-xs text-slate-400 mt-4">Breadth data not available in the latest snapshot.</p>
        )}
      </div>

      <div className="glass-panel glass-panel-hover rounded-2xl p-5 border border-slate-800 bg-[#0f172a]/70">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-medium">
          <span className="flex items-center gap-1.5">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            INSTITUTIONAL FLOWS
          </span>
          <span className="text-[10px] uppercase font-bold text-slate-400">Cash Net (Cr INR)</span>
        </div>

        {fiiNet != null || diiNet != null ? (
          <>
            <div className="grid grid-cols-2 gap-2 mb-2">
              <div>
                <div className="text-[11px] text-slate-400">FII Net</div>
                <div className={`text-base font-bold mono-num ${(fiiNet ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {(fiiNet ?? 0) >= 0 ? '+' : ''}{(fiiNet ?? 0).toLocaleString('en-IN')} Cr
                </div>
              </div>
              <div>
                <div className="text-[11px] text-slate-400">DII Net</div>
                <div className={`text-base font-bold mono-num ${(diiNet ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {(diiNet ?? 0) >= 0 ? '+' : ''}{(diiNet ?? 0).toLocaleString('en-IN')} Cr
                </div>
              </div>
            </div>
            <div className="mt-3 pt-3 border-t border-slate-800/80 text-[11px] flex justify-between text-slate-400">
              <span>Total Net Flow:</span>
              <strong className={`mono-num ${((fiiNet ?? 0) + (diiNet ?? 0)) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {((fiiNet ?? 0) + (diiNet ?? 0)) >= 0 ? '+' : ''}{((fiiNet ?? 0) + (diiNet ?? 0)).toFixed(1)} Cr
              </strong>
            </div>
          </>
        ) : (
          <p className="text-xs text-slate-400 mt-4">FII/DII flow data not available in the latest snapshot.</p>
        )}
      </div>
    </div>
  );
};
