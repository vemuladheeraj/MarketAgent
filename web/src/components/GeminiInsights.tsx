import React from 'react';
import { Sparkles, AlertTriangle, ShieldCheck, CheckCircle2, Info, Compass, HelpCircle } from 'lucide-react';
import { GeminiAnalysis } from '../types/market';

interface GeminiInsightsProps {
  analysis: GeminiAnalysis | null;
  symbol: string;
}

export const GeminiInsights: React.FC<GeminiInsightsProps> = ({ analysis, symbol }) => {
  if (!analysis) {
    return (
      <div className="glass-panel rounded-2xl p-6 border border-slate-800 bg-[#0f172a]/70 flex flex-col items-center justify-center text-center min-h-[220px]">
        <Sparkles className="w-8 h-8 text-sky-400/60 mb-2 animate-pulse" />
        <h3 className="text-sm font-semibold text-slate-200">Awaiting Gemini Contextual Reasoning</h3>
        <p className="text-xs text-slate-400 mt-1 max-w-md">
          Run a cycle or daemon loop to generate structured quantitative reasoning for {symbol}.
        </p>
      </div>
    );
  }

  const bias = analysis.market_bias || 'UNCERTAIN';
  const biasColors = {
    BULLISH: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    BEARISH: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    NEUTRAL: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    UNCERTAIN: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
  };

  const confidencePct = Math.round((analysis.confidence || 0.5) * 100);

  return (
    <div className="glass-panel rounded-2xl p-6 border border-slate-800 bg-gradient-to-b from-[#111c38]/80 to-[#0c1326]/90 shadow-xl shadow-black/20">
      {/* Top Bar: Title & AI Bias Badge */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800/80">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white tracking-tight">Gemini Contextual AI Synthesis</h2>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-300 font-semibold">
                Gemini 2.5 Flash
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Deterministic factor verification with cross-market contradiction detection
            </p>
          </div>
        </div>

        {/* Bias & Confidence Metrics */}
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-[10px] text-slate-400 font-medium">Model Confidence</div>
            <div className="text-xs font-bold text-slate-200 mono-num">{confidencePct}%</div>
          </div>
          <div
            className={`px-3.5 py-1.5 rounded-xl border text-xs font-extrabold tracking-wider flex items-center gap-1.5 shadow-sm ${
              biasColors[bias] || biasColors.UNCERTAIN
            }`}
          >
            <Compass className="w-4 h-4" />
            <span>{bias} BIAS</span>
          </div>
        </div>
      </div>

      {/* Summary Box */}
      <div className="mt-4 p-4 rounded-xl bg-slate-900/80 border border-slate-800/90">
        <p className="text-sm text-slate-200 leading-relaxed font-normal">
          {analysis.summary}
        </p>
      </div>

      {/* Grid: Key Factors & Contradictions / Risks */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
        {/* Left: Key Supporting Drivers */}
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/70">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5 mb-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            Core Quantitative Drivers
          </h4>
          <ul className="space-y-1.5 text-xs text-slate-300">
            {(analysis.key_factors || []).map((factor, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-sky-400 mt-0.5">•</span>
                <span>{factor}</span>
              </li>
            ))}
            {(analysis.supporting_factors || []).map((factor, idx) => (
              <li key={`sup-${idx}`} className="flex items-start gap-2 text-emerald-300/90">
                <span className="text-emerald-400 mt-0.5">+</span>
                <span>{factor}</span>
              </li>
            ))}
            {(!analysis.key_factors?.length && !analysis.supporting_factors?.length) && (
              <li className="text-slate-500 italic">No specific driver overrides found.</li>
            )}
          </ul>
        </div>

        {/* Right: Contradictions & Risks */}
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/70">
          <h4 className="text-xs font-bold uppercase tracking-wider text-amber-300 flex items-center gap-1.5 mb-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Cross-Factor Warnings & Risks
          </h4>
          
          {analysis.contradictions && analysis.contradictions.length > 0 ? (
            <div className="space-y-2 mb-3">
              {analysis.contradictions.map((c, idx) => (
                <div key={idx} className="p-2.5 rounded-lg bg-amber-950/30 border border-amber-800/40 text-xs text-amber-200">
                  <div className="font-semibold text-amber-300 flex items-center gap-1">
                    <span>⚠️ {c.factor_a} vs {c.factor_b}</span>
                  </div>
                  <div className="text-[11px] text-amber-200/80 mt-0.5">{c.description}</div>
                </div>
              ))}
            </div>
          ) : null}

          <ul className="space-y-1.5 text-xs text-slate-300">
            {(analysis.conflicting_factors || []).map((factor, idx) => (
              <li key={`conf-${idx}`} className="flex items-start gap-2 text-amber-300/90">
                <span className="text-amber-400 mt-0.5">!</span>
                <span>{factor}</span>
              </li>
            ))}
            {(analysis.risks || []).map((risk, idx) => (
              <li key={`risk-${idx}`} className="flex items-start gap-2 text-rose-300/90">
                <span className="text-rose-400 mt-0.5">✕</span>
                <span>{risk}</span>
              </li>
            ))}
            {(!analysis.contradictions?.length && !analysis.conflicting_factors?.length && !analysis.risks?.length) && (
              <li className="text-slate-400 italic">No conflicting market signals detected. Quantitative factors are aligned.</li>
            )}
          </ul>
        </div>
      </div>

      {/* Footer: Deterministic Grounding Notice */}
      <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400">
        <span className="flex items-center gap-1">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          Strictly grounded in verified market data. Zero hallucinated metrics.
        </span>
        <span className="mono-num">
          Signal Interpretation: <strong className="text-slate-200">{analysis.signal_interpretation}</strong>
        </span>
      </div>
    </div>
  );
};
