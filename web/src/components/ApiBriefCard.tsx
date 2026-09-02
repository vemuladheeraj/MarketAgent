/**
 * Trade Brief Card Component - Shows actionable recommendations for manual order placement.
 */

import React from 'react';
import { ApiBrief } from '../services/apiService';
import { TrendingUp, TrendingDown, AlertCircle, CheckCircle } from 'lucide-react';

interface TradeBriefCardProps {
  brief: ApiBrief | null;
  loading: boolean;
}

export function TradeBriefCard({ brief, loading }: TradeBriefCardProps) {
  if (loading) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6">
        <div className="text-slate-400">Loading trade brief...</div>
      </div>
    );
  }

  if (!brief) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6">
        <div className="text-slate-400">No brief available</div>
      </div>
    );
  }

  const isActionable = brief.action === 'BUY' || brief.action === 'SELL';
  const isWait = brief.action === 'WAIT';
  const isLong = brief.direction === 'long';

  return (
    <div
      className={`border rounded-lg p-6 ${
        isWait
          ? 'bg-slate-900 border-slate-700'
          : isLong
            ? 'bg-green-950 border-green-700'
            : 'bg-red-950 border-red-700'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-xl font-bold text-white">{brief.symbol}</h3>
          <span
            className={`px-2 py-1 rounded text-sm font-semibold ${
              isWait
                ? 'bg-yellow-500 text-black'
                : isLong
                  ? 'bg-green-500 text-black'
                  : 'bg-red-500 text-black'
            }`}
          >
            {brief.action}
          </span>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-white">{brief.score?.toFixed(0) || '—'}%</div>
          <div className="text-xs text-slate-300">Confidence</div>
        </div>
      </div>

      {/* Strategy & Regime */}
      <div className="grid grid-cols-2 gap-2 mb-4 text-sm">
        <div>
          <div className="text-slate-400">Strategy</div>
          <div className="text-white font-semibold">{brief.strategy}</div>
        </div>
        <div>
          <div className="text-slate-400">Regime</div>
          <div className="text-white font-semibold">{brief.regime}</div>
        </div>
      </div>

      {/* Action Content */}
      {isActionable && brief.contract ? (
        <div className="space-y-4">
          {/* Contract Details */}
          <div className="bg-slate-800 rounded p-4">
            <div className="font-semibold text-white mb-2">Contract: {brief.contract.tradingsymbol}</div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <div className="text-slate-400">Bid/Ask</div>
                <div className="text-white">
                  ₹{brief.contract.bid?.toFixed(2) || '—'} / ₹{brief.contract.ask?.toFixed(2) || '—'}
                </div>
              </div>
              <div>
                <div className="text-slate-400">Delta</div>
                <div className="text-white">{brief.contract.delta?.toFixed(2) || '—'}</div>
              </div>
              <div>
                <div className="text-slate-400">IV</div>
                <div className="text-white">{(brief.contract.iv ?? 0).toFixed(2)}</div>
              </div>
              <div>
                <div className="text-slate-400">Open Interest</div>
                <div className="text-white">{brief.contract.open_interest.toLocaleString()}</div>
              </div>
            </div>
          </div>

          {/* Entry/Exit Levels */}
          <div className="bg-slate-800 rounded p-4 space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-slate-400">Entry (Premium)</span>
              <span className="text-lg font-bold text-yellow-400">₹{brief.entry?.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400">Stop Loss</span>
              <span className="text-lg font-bold text-red-400">₹{brief.stop_loss?.toFixed(2)}</span>
            </div>
            {brief.targets.map((target, idx) => (
              <div key={idx} className="flex justify-between items-center">
                <span className="text-slate-400">Target {idx + 1}</span>
                <span className="text-lg font-bold text-green-400">₹{target.toFixed(2)}</span>
              </div>
            ))}
            {brief.risk_reward && (
              <div className="pt-2 border-t border-slate-700 flex justify-between items-center">
                <span className="text-slate-400">Risk/Reward Ratio</span>
                <span className="text-lg font-bold text-white">1:{brief.risk_reward.toFixed(2)}</span>
              </div>
            )}
          </div>

          {/* Broker Instructions */}
          <div className="bg-slate-800 rounded p-4">
            <div className="font-semibold text-white mb-2 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-green-400" />
              How to Place This Order
            </div>
            <ol className="list-decimal list-inside space-y-1 text-sm text-slate-300">
              <li>Log in to your broker platform</li>
              <li>Search for {brief.contract.tradingsymbol}</li>
              <li>Select {brief.action === 'BUY' ? 'BUY' : 'SELL'} order</li>
              <li>Set price limit to ₹{brief.entry?.toFixed(2)} (or better)</li>
              <li>Enter quantity: {brief.lots || '1'} lot(s)</li>
              <li>Set stop loss order at ₹{brief.stop_loss?.toFixed(2)}</li>
              <li>Set target sell order at ₹{brief.targets[0]?.toFixed(2)}</li>
              <li>Review and submit</li>
            </ol>
          </div>

          {/* Risk & Sizing */}
          {brief.lots && brief.risk_reward && (
            <div className="bg-slate-800 rounded p-4">
              <div className="font-semibold text-white mb-2">Risk Analysis</div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-400">Position Size</span>
                  <span className="text-white">{brief.lots} lot(s)</span>
                </div>
                {brief.risk_amount && (
                  <div className="flex justify-between">
                    <span className="text-slate-400">Max Risk</span>
                    <span className="text-red-400">₹{brief.risk_amount.toFixed(0)}</span>
                  </div>
                )}
                {brief.target_amount && (
                  <div className="flex justify-between">
                    <span className="text-slate-400">Target Profit</span>
                    <span className="text-green-400">₹{brief.target_amount.toFixed(0)}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Warnings */}
          {brief.warnings.length > 0 && (
            <div className="bg-yellow-950 border border-yellow-700 rounded p-3">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-yellow-300 mb-1">Warnings</div>
                  <ul className="text-sm text-yellow-200 space-y-0.5">
                    {brief.warnings.map((w, idx) => (
                      <li key={idx}>• {w}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : isWait ? (
        <div className="bg-yellow-950 border border-yellow-700 rounded p-4">
          <div className="text-yellow-300 font-semibold mb-2">Stand Aside</div>
          <div className="text-sm text-yellow-200 mb-3">{brief.waiting_reason}</div>
          <div className="text-xs text-yellow-300">
            Brief auto-expires at{' '}
            {new Date(brief.valid_until).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}
          </div>
        </div>
      ) : null}

      {/* Rationale */}
      <div className="mt-4 pt-4 border-t border-slate-700">
        <div className="text-xs text-slate-400">Analysis & Rationale</div>
        <ul className="text-xs text-slate-300 space-y-1 mt-2">
          {brief.rationale.slice(0, 3).map((r, idx) => (
            <li key={idx}>• {r}</li>
          ))}
        </ul>
      </div>

      {/* Timing */}
      <div className="mt-2 text-xs text-slate-500">
        Generated: {new Date(brief.generated_at).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}
        {' — '}
        Expires: {new Date(brief.valid_until).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}
      </div>
    </div>
  );
}
