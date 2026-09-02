/**
 * Signals Table Component - Shows recent trading signals from strategies.
 */

import React from 'react';
import { ApiSignal } from '../services/apiService';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface ApiSignalsTableProps {
  signals: ApiSignal[];
  loading: boolean;
}

export function ApiSignalsTable({ signals, loading }: ApiSignalsTableProps) {
  if (loading) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6">
        <div className="text-slate-400">Loading signals...</div>
      </div>
    );
  }

  if (signals.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6">
        <div className="text-slate-400">No signals available</div>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-800 border-b border-slate-700">
            <tr>
              <th className="px-4 py-2 text-left text-slate-300">Symbol</th>
              <th className="px-4 py-2 text-left text-slate-300">Strategy</th>
              <th className="px-4 py-2 text-left text-slate-300">Direction</th>
              <th className="px-4 py-2 text-right text-slate-300">Entry</th>
              <th className="px-4 py-2 text-right text-slate-300">Stop</th>
              <th className="px-4 py-2 text-right text-slate-300">Target</th>
              <th className="px-4 py-2 text-right text-slate-300">Score</th>
              <th className="px-4 py-2 text-center text-slate-300">Status</th>
              <th className="px-4 py-2 text-left text-slate-300">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {signals.map((signal, idx) => (
              <tr key={idx} className="hover:bg-slate-800 transition">
                <td className="px-4 py-2 font-semibold text-white">{signal.symbol}</td>
                <td className="px-4 py-2 text-slate-300">{signal.strategy}</td>
                <td className="px-4 py-2">
                  <div
                    className={`flex items-center gap-1 ${
                      signal.direction === 'long' ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {signal.direction === 'long' ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                    <span className="capitalize">{signal.direction}</span>
                  </div>
                </td>
                <td className="px-4 py-2 text-right text-white font-semibold">{signal.entry.toFixed(2)}</td>
                <td className="px-4 py-2 text-right text-red-400">{signal.stop_loss.toFixed(2)}</td>
                <td className="px-4 py-2 text-right text-green-400">{signal.targets[0]?.toFixed(2) || '—'}</td>
                <td className="px-4 py-2 text-right font-bold text-yellow-400">{signal.score.toFixed(0)}%</td>
                <td className="px-4 py-2 text-center">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      signal.accepted ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
                    }`}
                  >
                    {signal.accepted ? 'Accepted' : 'Rejected'}
                  </span>
                </td>
                <td className="px-4 py-2 text-slate-400 text-xs">
                  {new Date(signal.timestamp).toLocaleTimeString('en-IN', {
                    timeZone: 'Asia/Kolkata',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
