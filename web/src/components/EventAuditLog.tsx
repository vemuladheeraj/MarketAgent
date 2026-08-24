import React from 'react';
import { Terminal, Clock, CheckCircle, AlertCircle, Info, Sparkles } from 'lucide-react';
import { SystemEvent } from '../types/market';

interface EventAuditLogProps {
  events: SystemEvent[];
}

export const EventAuditLog: React.FC<EventAuditLogProps> = ({ events }) => {
  const getEventIcon = (type: string) => {
    if (type.includes('GEMINI')) return <Sparkles className="w-3.5 h-3.5 text-sky-400" />;
    if (type.includes('ERROR') || type.includes('REJECTED')) return <AlertCircle className="w-3.5 h-3.5 text-rose-400" />;
    if (type.includes('START') || type.includes('SIGNAL')) return <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />;
    return <Info className="w-3.5 h-3.5 text-slate-400" />;
  };

  const getEventBadge = (type: string) => {
    if (type.includes('GEMINI')) return 'bg-sky-500/15 text-sky-300 border-sky-500/30';
    if (type.includes('ERROR') || type.includes('REJECTED')) return 'bg-rose-500/15 text-rose-300 border-rose-500/30';
    if (type.includes('START') || type.includes('SIGNAL')) return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
    return 'bg-slate-800 text-slate-300 border-slate-700';
  };

  return (
    <div className="glass-panel rounded-2xl p-6 border border-slate-800 bg-[#0f172a]/70">
      <div className="flex items-center justify-between pb-4 border-b border-slate-800/80 mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <Terminal className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">System Audit Log & Live Event Stream</h3>
            <p className="text-xs text-slate-400">Real-time pipeline lifecycle events from Firestore `systemEvents`</p>
          </div>
        </div>

        <span className="mono-num text-xs text-slate-400">
          Showing last <strong className="text-slate-200">{events.length}</strong> events
        </span>
      </div>

      {/* Events List */}
      <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
        {events.length === 0 ? (
          <div className="py-6 text-center text-slate-400 italic text-xs">
            No system events recorded yet. Run a cycle with `python -m app.main`.
          </div>
        ) : (
          events.map((evt, idx) => {
            const timeStr = evt.timestamp
              ? new Date(evt.timestamp).toLocaleTimeString('en-IN', {
                  timeZone: 'Asia/Kolkata',
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                  hour12: false,
                })
              : 'LIVE';

            return (
              <div
                key={evt.id || idx}
                className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/80 flex items-start justify-between gap-3 text-xs"
              >
                <div className="flex items-start gap-2.5">
                  <div className="mt-0.5">{getEventIcon(evt.event_type || '')}</div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${getEventBadge(evt.event_type || '')}`}>
                        {evt.event_type || 'EVENT'}
                      </span>
                      <span className="text-slate-200 font-medium">{evt.message}</span>
                    </div>
                    {evt.details && Object.keys(evt.details).length > 0 && (
                      <div className="text-[11px] text-slate-400 mono-num mt-1 bg-slate-950/60 p-1.5 rounded border border-slate-900">
                        {JSON.stringify(evt.details)}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-1 text-[11px] text-slate-400 mono-num whitespace-nowrap">
                  <Clock className="w-3 h-3 text-slate-400" />
                  <span>{timeStr} IST</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
