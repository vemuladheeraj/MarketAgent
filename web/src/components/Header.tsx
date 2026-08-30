import React, { useState, useEffect } from 'react';
import { Activity, Clock, Database } from 'lucide-react';

interface HeaderProps {
  selectedSymbol: string;
  onSelectSymbol: (sym: string) => void;
  isLive: boolean;
  lastUpdated: string | null;
}

export const Header: React.FC<HeaderProps> = ({
  selectedSymbol,
  onSelectSymbol,
  isLive,
  lastUpdated,
}) => {
  const [istTime, setIstTime] = useState<string>('');
  const [isMarketOpen, setIsMarketOpen] = useState<boolean>(false);

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      // Format in IST
      const istString = now.toLocaleTimeString('en-IN', {
        timeZone: 'Asia/Kolkata',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
      });
      setIstTime(istString);

      // Check IST market hours (09:15 to 15:30, Mon-Fri)
      const options: Intl.DateTimeFormatOptions = {
        timeZone: 'Asia/Kolkata',
        hour12: false,
        hour: 'numeric',
        minute: 'numeric',
        weekday: 'short',
      };
      const parts = new Intl.DateTimeFormat('en-US', options).formatToParts(now);
      const weekday = parts.find((p) => p.type === 'weekday')?.value;
      const hour = parseInt(parts.find((p) => p.type === 'hour')?.value || '0', 10);
      const minute = parseInt(parts.find((p) => p.type === 'minute')?.value || '0', 10);

      const isWeekday = weekday !== 'Sat' && weekday !== 'Sun';
      const timeMin = hour * 60 + minute;
      const isOpen = isWeekday && timeMin >= 9 * 60 + 15 && timeMin <= 15 * 60 + 30;
      setIsMarketOpen(isOpen);
    };

    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="border-b border-slate-800/80 bg-[#0c1222]/90 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        {/* Left: Branding & Tag */}
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20 ring-1 ring-white/20">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                MarketAgent <span className="text-xs px-2 py-0.5 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-400 font-semibold">v1.0 Pro</span>
              </h1>
            </div>
            <p className="text-xs text-slate-400 font-medium">
              Indian Market Intelligence & Options Research
            </p>
          </div>
        </div>

        {/* Middle: Symbol Switcher */}
        <div className="flex items-center bg-slate-900/90 p-1 rounded-xl border border-slate-800 self-start md:self-auto">
          {(['NIFTY', 'BANKNIFTY', 'FINNIFTY'] as const).map((sym) => (
            <button
              key={sym}
              onClick={() => onSelectSymbol(sym)}
              className={`px-4 py-1.5 rounded-lg text-xs font-semibold tracking-wide transition-all ${
                selectedSymbol === sym
                  ? 'bg-sky-500 text-white shadow-md shadow-sky-500/30 font-bold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              {sym === 'NIFTY' ? 'NIFTY 50' : sym === 'BANKNIFTY' ? 'BANK NIFTY' : 'FIN NIFTY'}
            </button>
          ))}
        </div>

        {/* Right: Live Clocks & Database Status */}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          {/* Market Status Pill */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span className="mono-num text-slate-200 font-medium">{istTime || '09:15:00 IST'}</span>
            <span
              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${
                isMarketOpen
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${isMarketOpen ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`}></span>
              {isMarketOpen ? 'NSE LIVE' : 'POST MARKET'}
            </span>
          </div>

          {/* Firestore Link Status */}
          <div
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium ${
              isLive
                ? 'bg-emerald-950/40 border-emerald-800/50 text-emerald-300'
                : 'bg-sky-950/40 border-sky-800/50 text-sky-300'
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span>{isLive ? 'Firestore Synced' : 'Awaiting live data'}</span>
          </div>

          {lastUpdated && (
            <div className="text-[11px] text-slate-400 mono-num">
              Updated {new Date(lastUpdated).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
