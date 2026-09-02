/**
 * Dashboard Page - Main interface for the MarketAgent web dashboard.
 */

import React, { useState, useEffect } from 'react';
import { useSignals, useTradeBrief, useMarketQuote, usePaperTrades, useApiHealth } from '../services/useApi';
import { getRuntimeConfig, setRuntimeConfig } from '../services/apiService';
import { TradeBriefCard } from './ApiBriefCard';
import { ApiSignalsTable } from './ApiSignalsTable';
import { Activity, AlertCircle, TrendingUp, Zap } from 'lucide-react';

export function Dashboard() {
  const [selectedSymbol, setSelectedSymbol] = useState<string>('NIFTY');
  const [activeTab, setActiveTab] = useState<'brief' | 'signals' | 'trades'>('brief');
  const [marketMode, setMarketMode] = useState<'india' | 'us' | 'both'>('india');
  const [providerMode, setProviderMode] = useState<string>('indstocks');

  const { signals, loading: signalsLoading } = useSignals();
  const { brief, loading: briefLoading } = useTradeBrief(selectedSymbol);
  const { quote, loading: quoteLoading } = useMarketQuote(selectedSymbol);
  const { trades, loading: tradesLoading } = usePaperTrades();
  const { healthy, system } = useApiHealth();

  useEffect(() => {
    const loadConfig = async () => {
      const config = await getRuntimeConfig();
      setMarketMode((config.market as 'india' | 'us' | 'both') || 'india');
      setProviderMode(config.provider || 'indstocks');
    };
    loadConfig();
  }, []);

  const handleMarketConfigChange = async (nextMarket: 'india' | 'us' | 'both', nextProvider: string) => {
    const result = await setRuntimeConfig({ market: nextMarket, provider: nextProvider });
    if (result.ok) {
      setMarketMode(nextMarket);
      setProviderMode(nextProvider);
    }
  };

  // Extract unique symbols from signals for quick selection
  const symbolsFromSignals = Array.from(new Set(signals.map((s) => s.symbol))).slice(0, 10);

  return (
    <div className="min-h-screen bg-slate-950 text-white p-4">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Zap className="w-6 h-6 text-yellow-400" />
            <h1 className="text-3xl font-bold">MarketAgent Dashboard</h1>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={`w-3 h-3 rounded-full ${healthy ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}
            />
            <span className="text-sm text-slate-400">{healthy ? 'System Healthy' : 'System Offline'}</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
            <div className="text-xs uppercase text-slate-400">API</div>
            <div className={`mt-1 font-semibold ${healthy ? 'text-green-400' : 'text-red-400'}`}>
              {healthy ? 'Connected' : 'Offline'}
            </div>
          </div>
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
            <div className="text-xs uppercase text-slate-400">AI</div>
            <div className={`mt-1 font-semibold ${system.ai_ready ? 'text-green-400' : 'text-yellow-400'}`}>
              {system.ai_ready ? 'Ready' : 'Not Ready'}
            </div>
          </div>
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
            <div className="text-xs uppercase text-slate-400">Market</div>
            <div className="mt-1 font-semibold text-white capitalize">{system.market || 'india'}</div>
          </div>
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
            <div className="text-xs uppercase text-slate-400">Session</div>
            <div className={`mt-1 font-semibold ${system.market_open ? 'text-green-400' : 'text-slate-300'}`}>
              {system.market_open ? 'Open' : 'Closed'}
            </div>
          </div>
        </div>

        <p className="text-slate-400">{system.message || 'Real-time trading decision support • Manual order placement workflow • No auto-execution'}</p>
      </div>

      {/* Runtime Controls */}
      <div className="mb-6 bg-slate-900 border border-slate-700 rounded-lg p-4">
        <div className="flex flex-col md:flex-row gap-3 items-center justify-between mb-4">
          <div className="text-sm text-slate-400">Live Market Selection</div>
          <div className="flex flex-wrap gap-3">
            <select
              value={marketMode}
              onChange={(e) => handleMarketConfigChange(e.target.value as 'india' | 'us' | 'both', providerMode)}
              className="bg-slate-800 text-white border border-slate-600 px-3 py-2 rounded"
            >
              <option value="india">India</option>
              <option value="us">US</option>
              <option value="both">India + US</option>
            </select>
            <select
              value={providerMode}
              onChange={(e) => handleMarketConfigChange(marketMode, e.target.value)}
              className="bg-slate-800 text-white border border-slate-600 px-3 py-2 rounded"
            >
              <option value="indstocks">IndStocks (India)</option>
              <option value="us_markets">US Markets (yfinance)</option>
              <option value="nse">NSE</option>
            </select>
          </div>
        </div>

        <div className="text-sm text-slate-400 mb-2">Quick Access Symbols</div>
        <div className="flex flex-wrap gap-2">
          {['NIFTY', 'BANKNIFTY', ...symbolsFromSignals].map((sym) => (
            <button
              key={sym}
              onClick={() => setSelectedSymbol(sym)}
              className={`px-3 py-1 rounded text-sm font-semibold transition ${
                selectedSymbol === sym
                  ? 'bg-yellow-500 text-black'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              {sym}
            </button>
          ))}
        </div>
      </div>

      {/* Current Quote */}
      {quote && !quoteLoading && (
        <div className="mb-6 bg-gradient-to-r from-slate-900 to-slate-800 border border-slate-700 rounded-lg p-4">
          <div className="flex items-end justify-between">
            <div>
              <div className="text-sm text-slate-400">Current Price</div>
              <div className="text-4xl font-bold text-white">₹{quote.last_price?.toFixed(2)}</div>
            </div>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <div className="text-slate-400">Bid</div>
                <div className="text-green-400 font-semibold">₹{quote.bid?.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-slate-400">Ask</div>
                <div className="text-red-400 font-semibold">₹{quote.ask?.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-slate-400">Volume</div>
                <div className="text-white font-semibold">{(quote.volume ?? 0).toLocaleString()}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="mb-6 border-b border-slate-700">
        <div className="flex gap-4">
          {['brief', 'signals', 'trades'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab as any)}
              className={`px-4 py-2 font-semibold transition border-b-2 ${
                activeTab === tab
                  ? 'border-yellow-400 text-yellow-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab === 'brief' && (
                <>
                  <TrendingUp className="inline w-4 h-4 mr-1" />
                  Trade Brief
                </>
              )}
              {tab === 'signals' && (
                <>
                  <Activity className="inline w-4 h-4 mr-1" />
                  Recent Signals
                </>
              )}
              {tab === 'trades' && (
                <>
                  <AlertCircle className="inline w-4 h-4 mr-1" />
                  Paper Trades ({trades.length})
                </>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div>
        {activeTab === 'brief' && (
          <TradeBriefCard brief={brief} loading={briefLoading} />
        )}

        {activeTab === 'signals' && (
          <ApiSignalsTable signals={signals} loading={signalsLoading} />
        )}

        {activeTab === 'trades' && (
          <div className="bg-slate-900 border border-slate-700 rounded-lg overflow-hidden">
            {tradesLoading ? (
              <div className="p-6 text-slate-400">Loading paper trades...</div>
            ) : trades.length === 0 ? (
              <div className="p-6 text-slate-400">No open or closed trades</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800 border-b border-slate-700">
                    <tr>
                      <th className="px-4 py-2 text-left text-slate-300">Symbol</th>
                      <th className="px-4 py-2 text-left text-slate-300">Strategy</th>
                      <th className="px-4 py-2 text-right text-slate-300">Entry</th>
                      <th className="px-4 py-2 text-right text-slate-300">Current</th>
                      <th className="px-4 py-2 text-right text-slate-300">P&L</th>
                      <th className="px-4 py-2 text-right text-slate-300">P&L %</th>
                      <th className="px-4 py-2 text-left text-slate-300">Stage</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700">
                    {trades.map((trade, idx) => (
                      <tr key={idx} className="hover:bg-slate-800 transition">
                        <td className="px-4 py-2 font-semibold">{trade.symbol}</td>
                        <td className="px-4 py-2 text-slate-300 text-xs">{trade.strategy}</td>
                        <td className="px-4 py-2 text-right">₹{trade.entry_price.toFixed(2)}</td>
                        <td className="px-4 py-2 text-right">₹{(trade.current_price ?? trade.entry_price).toFixed(2)}</td>
                        <td
                          className={`px-4 py-2 text-right font-semibold ${
                            (trade.pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}
                        >
                          ₹{(trade.pnl ?? 0).toFixed(2)}
                        </td>
                        <td
                          className={`px-4 py-2 text-right font-semibold ${
                            (trade.pnl_pct ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}
                        >
                          {((trade.pnl_pct ?? 0) * 100).toFixed(2)}%
                        </td>
                        <td className="px-4 py-2 text-xs capitalize text-slate-300">{trade.stage}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-8 pt-6 border-t border-slate-700 text-center text-xs text-slate-500">
        <p>MarketAgent Dashboard • Prices update every 5 seconds • Manual order placement only • Check live quotes before trading</p>
      </div>
    </div>
  );
}
