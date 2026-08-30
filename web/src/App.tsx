import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { MarketOverview } from './components/MarketOverview';
import { GeminiInsights } from './components/GeminiInsights';
import { RegimeTechnical } from './components/RegimeTechnical';
import { OptionsAnalytics } from './components/OptionsAnalytics';
import { SignalsTable } from './components/SignalsTable';
import { PaperTrading } from './components/PaperTrading';
import { EventAuditLog } from './components/EventAuditLog';
import { TradeBriefCard } from './components/TradeBriefCard';

import {
  subscribeLatestSnapshot,
  subscribeGeminiAnalyses,
  subscribeRegimes,
  subscribeSignals,
  subscribePaperTrades,
  subscribeSystemEvents,
  subscribeTradeBrief,
} from './services/firestoreService';

import {
  MarketSnapshot,
  GeminiAnalysis,
  RegimeAssessment,
  Signal,
  PaperTrade,
  SystemEvent,
  TradeBrief,
} from './types/market';

import { LayoutDashboard, BarChart2, Zap, Shield, Terminal } from 'lucide-react';

export function App() {
  const [selectedSymbol, setSelectedSymbol] = useState<string>('NIFTY');
  const [activeTab, setActiveTab] = useState<'overview' | 'options' | 'signals' | 'paper' | 'events'>('overview');
  const [isLive, setIsLive] = useState<boolean>(false);

  // Firestore live state
  const [snapshot, setSnapshot] = useState<MarketSnapshot | null>(null);
  const [geminiAnalysis, setGeminiAnalysis] = useState<GeminiAnalysis | null>(null);
  const [regime, setRegime] = useState<RegimeAssessment | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [paperTrades, setPaperTrades] = useState<PaperTrade[]>([]);
  const [systemEvents, setSystemEvents] = useState<SystemEvent[]>([]);
  const [tradeBrief, setTradeBrief] = useState<TradeBrief | null>(null);

  // Subscriptions lifecycle
  useEffect(() => {
    // 1. Snapshot
    const unsubSnap = subscribeLatestSnapshot(
      (data) => {
        if (data) {
          setSnapshot(data);
          setIsLive(true);
        }
      },
      () => setIsLive(false)
    );

    // 2. Gemini Analysis
    const unsubGemini = subscribeGeminiAnalyses(selectedSymbol, (data) => {
      if (data) setGeminiAnalysis(data);
    });

    // 3. Regimes
    const unsubRegime = subscribeRegimes(selectedSymbol, (data) => {
      if (data) setRegime(data);
    });

    // 4. Signals
    const unsubSignals = subscribeSignals((data) => {
      if (data && data.length > 0) setSignals(data);
    });

    // 5. Paper Trades
    const unsubTrades = subscribePaperTrades((data) => {
      if (data && data.length > 0) setPaperTrades(data);
    });

    // 6. System Events
    const unsubEvents = subscribeSystemEvents((data) => {
      if (data && data.length > 0) setSystemEvents(data);
    });

    // 7. Present-moment Trade Brief
    const unsubBrief = subscribeTradeBrief(selectedSymbol, setTradeBrief);

    return () => {
      unsubSnap();
      unsubGemini();
      unsubRegime();
      unsubSignals();
      unsubTrades();
      unsubEvents();
      unsubBrief();
    };
  }, [selectedSymbol]);

  const currentSnapshot = snapshot;
  const currentGemini = geminiAnalysis;
  const currentRegime = regime;
  const currentSignals = signals;
  const currentChain = currentSnapshot?.option_chains?.[selectedSymbol] || null;

  const lastUpdated = currentSnapshot?.timestamp || null;

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col">
      {/* Top Navigation Bar */}
      <Header
        selectedSymbol={selectedSymbol}
        onSelectSymbol={setSelectedSymbol}
        isLive={isLive}
        lastUpdated={lastUpdated}
      />

      {/* Main Content Dashboard */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-800/80 pb-2 overflow-x-auto">
          {[
            { id: 'overview', label: 'Market Overview & AI', icon: LayoutDashboard },
            { id: 'options', label: 'Option Chain & OI', icon: BarChart2 },
            { id: 'signals', label: 'Strategy Signals', icon: Zap },
            { id: 'paper', label: 'Paper Trading & Risk', icon: Shield },
            { id: 'events', label: 'System Audit Log', icon: Terminal },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold tracking-wide transition-all whitespace-nowrap ${
                  isActive
                    ? 'bg-sky-500/15 border border-sky-500/30 text-sky-400 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab 1: Overview & AI Hub */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Present-moment Trade Brief (the companion answer) */}
            <TradeBriefCard brief={tradeBrief} symbol={selectedSymbol} />

            {/* Top Market Cards */}
            <MarketOverview symbol={selectedSymbol} snapshot={currentSnapshot} />

            {/* Gemini AI Intelligence Section */}
            <GeminiInsights analysis={currentGemini} symbol={selectedSymbol} />

            {/* Market Regime & Key Technical Levels */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <RegimeTechnical
                regime={currentRegime}
                snapshot={currentSnapshot}
                symbol={selectedSymbol}
              />
              <SignalsTable
                signals={currentSignals}
                selectedSymbol={selectedSymbol}
              />
            </div>
          </div>
        )}

        {/* Tab 2: Options Chain & OI Analytics */}
        {activeTab === 'options' && (
          <div className="space-y-6">
            <MarketOverview symbol={selectedSymbol} snapshot={currentSnapshot} />
            <OptionsAnalytics chain={currentChain} symbol={selectedSymbol} />
          </div>
        )}

        {/* Tab 3: Strategy Signals */}
        {activeTab === 'signals' && (
          <div className="space-y-6">
            <SignalsTable
              signals={currentSignals}
              selectedSymbol={selectedSymbol}
            />
            <RegimeTechnical
              regime={currentRegime}
              snapshot={currentSnapshot}
              symbol={selectedSymbol}
            />
          </div>
        )}

        {/* Tab 4: Paper Trading & Risk */}
        {activeTab === 'paper' && (
          <div className="space-y-6">
            <PaperTrading trades={paperTrades} />
            <SignalsTable
              signals={currentSignals}
              selectedSymbol={selectedSymbol}
            />
          </div>
        )}

        {/* Tab 5: Event Audit Log */}
        {activeTab === 'events' && (
          <div className="space-y-6">
            <EventAuditLog events={systemEvents} />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-4 bg-[#0c1222]/60 text-center text-xs text-slate-400">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>
            MarketAgent Quantitative Decision Support • Indian Equities & Derivatives (NSE)
          </span>
          <span className="mono-num text-[11px] text-slate-400">
            Connected to Firestore <strong className="text-slate-300">marketagent-9ea8f</strong>
          </span>
        </div>
      </footer>
    </div>
  );
}
export default App;
