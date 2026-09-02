import React, { useEffect, useState } from 'react';
import {
  Crosshair,
  Clock,
  AlertTriangle,
  ArrowUpRight,
  ArrowDownRight,
  PauseCircle,
  ShieldAlert,
  Hourglass,
  Info,
} from 'lucide-react';
import { TradeBrief } from '../types/market';

interface TradeBriefCardProps {
  brief: TradeBrief | null;
  symbol: string;
}

/** Firestore may deliver datetimes as ISO strings or Timestamp objects. */
function toDate(value: any): Date | null {
  if (!value) return null;
  if (typeof value === 'string') {
    const d = new Date(value);
    return isNaN(d.getTime()) ? null : d;
  }
  if (typeof value?.toDate === 'function') return value.toDate();
  if (typeof value === 'number') return new Date(value);
  return null;
}

function fmtTime(d: Date | null): string {
  if (!d) return '—';
  return d.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Asia/Kolkata',
  });
}

function fmtDate(d: Date | null): string {
  if (!d) return '—';
  return d.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    timeZone: 'Asia/Kolkata',
  });
}

export const TradeBriefCard: React.FC<TradeBriefCardProps> = ({ brief, symbol }) => {
  const [now, setNow] = useState(() => Date.now());

  // Keep the validity countdown honest without spamming renders.
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(timer);
  }, []);

  if (!brief || brief.underlying_symbol?.toUpperCase() !== symbol.toUpperCase()) {
    return (
      <div className="glass-panel rounded-2xl p-6 border border-slate-800 bg-[#0f172a]/70">
        <div className="flex items-center gap-2 mb-2">
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <Crosshair className="w-4 h-4" />
          </div>
          <h3 className="text-sm font-bold text-white tracking-tight">
            Trade Brief — What To Do Right Now
          </h3>
        </div>
        <div className="py-6 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800/60 text-xs">
          <Hourglass className="w-6 h-6 text-slate-500 mx-auto mb-1.5" />
          No brief published for {symbol} yet. Run the live agent (
          <span className="mono-num">scripts/run_live.ps1</span>) to start receiving
          present-moment guidance.
        </div>
      </div>
    );
  }

  const isWait = brief.action === 'WAIT';
  const isBuy = brief.action === 'BUY';
  const validUntil = toDate(brief.valid_until);
  const generatedAt = toDate(brief.generated_at);
  const isExpired = validUntil ? validUntil.getTime() < now : false;
  const expiryDate = toDate(brief.contract?.expiry_date);

  const actionBadge = isWait ? (
    <span
      title="WAIT — no setup cleared the score, risk and expected-value gates right now. Standing aside is a deliberate recommendation."
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-extrabold uppercase bg-amber-500/15 text-amber-300 border border-amber-500/40"
    >
      <PauseCircle className="w-4 h-4" /> Stand Aside — Wait
    </span>
  ) : (
    <span
      title="BUY — the model found a qualifying setup and names one exact contract to buy. It never places the order; you do."
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-extrabold uppercase border ${
        isBuy
          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50'
          : 'bg-rose-500/20 text-rose-300 border-rose-500/50'
      }`}
    >
      {isBuy ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
      {brief.action} {brief.contract?.option_type === 'call' ? 'Call' : 'Put'}
    </span>
  );

  const directionNote =
    brief.underlying_direction === 'long'
      ? 'Long bias'
      : brief.underlying_direction === 'short'
        ? 'Short bias'
        : null;

  return (
    <div
      className={`glass-panel rounded-2xl p-6 border bg-[#0f172a]/80 transition-all ${
        isWait
          ? 'border-amber-900/50'
          : isExpired
            ? 'border-rose-900/60'
            : 'border-emerald-800/50 shadow-[0_0_40px_-12px_rgba(16,185,129,0.25)]'
      }`}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800/80">
        <div className="flex items-center gap-2">
          <div
            className={`p-2 rounded-xl border ${
              isWait
                ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
            }`}
          >
            <Crosshair className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">
              Trade Brief — What To Do Right Now
            </h3>
            <p className="text-xs text-slate-400">
              {brief.strategy_name ? `Via ${brief.strategy_name}` : 'Quantitative companion'}
              {directionNote ? ` • ${directionNote}` : ''}
              {brief.regime ? ` • ${brief.regime.replace(/_/g, ' ').toUpperCase()}` : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {brief.score != null && (
            <span
              title="SCORE — weighted strength of the underlying strategy signal (0-100). Only strong scores become BUY briefs."
              className="px-2.5 py-1 rounded-md text-[10px] font-extrabold border bg-sky-500/15 text-sky-300 border-sky-500/30 mono-num"
            >
              SCORE {brief.score.toFixed(0)}/100
            </span>
          )}
          {actionBadge}
        </div>
      </div>

      {/* WAIT state */}
      {isWait ? (
        <div className="pt-4 space-y-3">
          <div className="p-3 rounded-xl bg-amber-950/30 border border-amber-900/50 text-xs text-amber-200">
            {brief.waiting_reason || 'No qualifying setup at this moment.'}
          </div>
          <div className="flex items-start gap-2 text-[11px] text-slate-400">
            <Info className="w-3.5 h-3.5 mt-0.5 shrink-0 text-slate-500" />
            <span>
              WAIT is a deliberate recommendation, not an error: no setup cleared the score, risk
              and expected-value gates right now. Not every session produces a trade.
            </span>
          </div>
          {brief.rationale.length > 0 && (
            <ul className="space-y-1.5">
              {brief.rationale.slice(0, 4).map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-slate-300">
                  <span className="text-amber-400 mt-0.5">•</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <>
          {/* Contract headline */}
          <div className="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <div className="text-2xl font-extrabold text-white tracking-tight mono-num">
                {brief.contract?.tradingsymbol || brief.underlying_symbol}
              </div>
              <div className="text-[11px] text-slate-400">
                {expiryDate ? `Expiry ${fmtDate(expiryDate)}` : ''}
                {brief.contract?.open_interest
                  ? ` • OI ${brief.contract.open_interest.toLocaleString('en-IN')}`
                  : ''}
                {brief.contract?.delta != null
                  ? ` • Δ ${brief.contract.delta.toFixed(2)}`
                  : ''}
              </div>
            </div>
            {brief.spot != null && (
              <div className="text-right">
                <div
                  title="Spot — the live index level the strike was chosen against (nearest-ATM)."
                  className="text-[10px] text-slate-400 uppercase tracking-wider"
                >
                  Spot
                </div>
                <div className="mono-num font-bold text-slate-200">
                  {brief.spot.toFixed(1)}
                </div>
              </div>
            )}
          </div>

          {/* Plain-English translation of the contract call */}
          <div className="mt-2 p-3 rounded-xl bg-slate-900/60 border border-slate-800/60 text-[11px] leading-relaxed text-slate-300">
            {brief.contract?.option_type === 'put' ? (
              <>
                In plain words: <strong className="text-rose-300">buy this PUT (PE)</strong> — the
                model is betting <strong className="text-white">{brief.underlying_symbol}</strong>{' '}
                goes <strong className="text-rose-300">DOWN</strong>. You pay the premium (the Entry
                ₹) now; that premium is your maximum loss per lot. The Stop and Targets below are
                premium (₹) levels, not index points.
              </>
            ) : (
              <>
                In plain words: <strong className="text-emerald-300">buy this CALL (CE)</strong> —
                the model is betting <strong className="text-white">{brief.underlying_symbol}</strong>{' '}
                goes <strong className="text-emerald-300">UP</strong>. You pay the premium (the Entry
                ₹) now; that premium is your maximum loss per lot. The Stop and Targets below are
                premium (₹) levels, not index points.
              </>
            )}
          </div>

          {/* Premium plan grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 mt-4">
            <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/60">
              <div
                title="Entry — the premium (₹) you aim to pay for this option. Treat it as your maximum buy price."
                className="text-slate-400 text-[10px] uppercase tracking-wider"
              >
                Entry
              </div>
              <div className="mono-num font-bold text-white mt-0.5">
                ₹{brief.entry?.toFixed(2) ?? '—'}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950/60 border border-rose-900/40">
              <div
                title="Stop — exit (sell) if the premium falls to this level. It caps the loss per lot and is always below the entry for a BUY brief."
                className="text-rose-400 text-[10px] uppercase tracking-wider"
              >
                Stop
              </div>
              <div className="mono-num font-bold text-rose-300 mt-0.5">
                ₹{brief.stop_loss?.toFixed(2) ?? '—'}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950/60 border border-emerald-900/40">
              <div
                title="Targets — premium levels to book profit: T1 first, T2 optional runner."
                className="text-emerald-400 text-[10px] uppercase tracking-wider"
              >
                Targets
              </div>
              <div className="mono-num font-bold text-emerald-300 mt-0.5">
                {(brief.targets || []).map((t) => `₹${t.toFixed(1)}`).join(' / ') || '—'}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/60">
              <div
                title="Size — how many lots to buy. lots × lot-size = number of option units."
                className="text-slate-400 text-[10px] uppercase tracking-wider"
              >
                Size
              </div>
              <div className="mono-num font-bold text-slate-200 mt-0.5">
                {brief.lots != null
                  ? `${brief.lots} lot${brief.lots === 1 ? '' : 's'}${brief.lot_size ? ` (${brief.lots * brief.lot_size} units)` : ''}`
                  : '—'}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/60">
              <div
                title="Risk : Reward — expected reward per ₹1 of risk at T1. 2.0 or higher is generally considered healthy."
                className="text-sky-400 text-[10px] uppercase tracking-wider"
              >
                Risk : Reward
              </div>
              <div className="mono-num font-bold text-sky-300 mt-0.5">
                {brief.risk_reward != null ? `1 : ${brief.risk_reward.toFixed(2)}` : '—'}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/60">
              <div
                title="Net EV — average expected profit per trade after all Indian costs (brokerage, STT, exchange/SEBI fees, stamp duty, slippage, spread). Positive = worth considering."
                className="text-slate-400 text-[10px] uppercase tracking-wider"
              >
                Net EV
              </div>
              <div className="mono-num font-bold text-slate-200 mt-0.5">
                {brief.net_expected_value != null
                  ? `₹${brief.net_expected_value.toFixed(0)}`
                  : '—'}
              </div>
            </div>
          </div>

          {/* Risk / reward rupee amounts */}
          {(brief.risk_amount != null || brief.target_amount != null) && (
            <div className="flex flex-wrap gap-4 mt-3 text-[11px] mono-num">
              {brief.risk_amount != null && (
                <span className="text-rose-300">
                  Risk ≈ <strong>₹{brief.risk_amount.toFixed(0)}</strong>
                </span>
              )}
              {brief.target_amount != null && (
                <span className="text-emerald-300">
                  Reward @ T1 ≈ <strong>₹{brief.target_amount.toFixed(0)}</strong>
                </span>
              )}
            </div>
          )}

          {/* Rationale */}
          {brief.rationale.length > 0 && (
            <div className="mt-4 pt-3 border-t border-slate-800/80">
              <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1.5">
                Why now
              </div>
              <ul className="space-y-1.5">
                {brief.rationale.slice(0, 6).map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-slate-300">
                    <span className="text-emerald-400 mt-0.5">•</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Warnings */}
          {brief.warnings.length > 0 && (
            <div className="mt-3 p-3 rounded-xl bg-amber-950/30 border border-amber-900/50">
              <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-amber-300 mb-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Watch-outs
              </div>
              <ul className="space-y-1">
                {brief.warnings.map((w, i) => (
                  <li key={i} className="text-xs text-amber-200">• {w}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {/* Footer: validity + disclaimer */}
      <div className="mt-4 pt-3 border-t border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px]">
        <span className={`flex items-center gap-1.5 ${isExpired ? 'text-rose-400 font-bold' : 'text-slate-400'}`}>
          <Clock className="w-3.5 h-3.5" />
          {isExpired ? (
            <>
              Expired {validUntil ? `at ${fmtTime(validUntil)}` : ''} — waiting for the next cycle
            </>
          ) : (
            <>
              Valid until{' '}
              <strong className="text-slate-300 mono-num">{fmtTime(validUntil)}</strong> IST
              {generatedAt ? ` • generated ${fmtTime(generatedAt)}` : ''}
            </>
          )}
        </span>
        <span className="flex items-center gap-1.5 text-slate-500">
          <ShieldAlert className="w-3.5 h-3.5" />
          Decision support only — you place the trade. Verify live premium first.
        </span>
      </div>
    </div>
  );
};

