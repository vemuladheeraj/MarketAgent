import React, { useState } from 'react';
import { BookOpen, Search, TrendingUp, CircleHelp, Calculator, Radio, ChevronDown, Info } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface Term {
  term: string;
  definition: string;
}

interface FieldGuideGroup {
  id: string;
  title: string;
  icon: LucideIcon;
  terms: Term[];
}

const GROUPS: FieldGuideGroup[] = [
  {
    id: 'market',
    title: 'Market Basics',
    icon: TrendingUp,
    terms: [
      {
        term: 'Spot Price',
        definition:
          'The last traded price of the underlying right now — for NIFTY / BANKNIFTY it is the current index value, not an option premium.',
      },
      {
        term: 'Open / High / Low / Previous Close',
        definition:
          'The session’s opening price, the highest and lowest price traded so far today, and yesterday’s closing price. They frame today’s range and gaps.',
      },
      {
        term: 'Market Breadth (Advance / Decline)',
        definition:
          'How many stocks are rising vs falling in the index. Strong breadth (many more advancers than decliners) supports an up move; weak breadth can signal a fragile rally.',
      },
      {
        term: 'India VIX',
        definition:
          "The market's fear gauge. A low VIX means traders expect calm, steady moves; a high VIX means traders expect sharp swings. Option premiums get expensive when VIX rises.",
      },
      {
        term: 'FII / DII Flows',
        definition:
          'Net buying (+) or selling (−) in ₹ crore by Foreign Institutional Investors and Domestic Institutional Investors. Big sustained flows often move the market.',
      },
    ],
  },
  {
    id: 'options',
    title: 'Options & Open Interest',
    icon: CircleHelp,
    terms: [
      {
        term: 'Option Premium',
        definition:
          'The price you actually pay to buy a call or put contract. It is quoted in ₹ per share; the full cost is premium × lot size.',
      },
      {
        term: 'Call / Put',
        definition:
          'A Call profits when the market rises; a Put profits when the market falls. Each contract is tied to a strike price and an expiry.',
      },
      {
        term: 'Strike Price',
        definition:
          'The fixed price at which the option is defined. A NIFTY 24800 CE lets you benefit from NIFTY being above 24800 at expiry.',
      },
      {
        term: 'Expiry',
        definition:
          'The date the option contract settles. Weekly index options expire every Thursday; after expiry the contract simply disappears.',
      },
      {
        term: 'Open Interest (OI)',
        definition:
          'The total number of option contracts still open (not squared off). It shows where big money is parked. Heavy OI at a strike acts like a magnet or a wall for price.',
      },
      {
        term: 'Change in OI',
        definition:
          'How open interest moved this session. Rising OI + rising price = fresh buying support; falling OI + falling price = longs being closed. The combination matters more than either number alone.',
      },
      {
        term: 'ITM / ATM / OTM',
        definition:
          'In-the-Money (ITM) options have intrinsic value already; At-the-Money (ATM) are the strikes closest to the current spot; Out-of-the-Money (OTM) are cheaper but need a bigger move to profit.',
      },
      {
        term: 'Implied Volatility (IV)',
        definition:
          'The market’s forecast of how much the underlying will swing, baked into the premium. High IV = rich premiums; low IV = cheap premiums. You are betting direction, but IV mostly decides the price tag.',
      },
      {
        term: 'Bid-Ask Spread',
        definition:
          'The gap between the best price a buyer will pay (bid) and the best price a seller will accept (ask). A wide spread means the contract is illiquid and you will pay extra to get in or out.',
      },
      {
        term: 'Delta',
        definition:
          'How many rupees the option premium moves for every ₹1 move in the underlying. A delta of 0.5 means the premium moves ~₹0.50 for a ₹1 index move.',
      },
      {
        term: 'Lot Size',
        definition:
          'The fixed contract multiplier for index options (e.g. 25 or 75). One contract’s total cost and P&L = premium × lot size.',
      },
      {
        term: 'Position Building',
        definition:
          'A large rise in OI at a strike along with a price move hints that institutions are adding fresh positions there, which often sets the next support or resistance.',
      },
    ],
  },
  {
    id: 'risk',
    title: 'Risk & Trade Math',
    icon: Calculator,
    terms: [
      {
        term: 'Trade Brief',
        definition:
          'The present-moment card on this page. It fuses the best risk-approved signal with the live option chain and tells you exactly what to do right now: BUY, SELL, or WAIT.',
      },
      {
        term: 'Action (BUY / SELL / WAIT)',
        definition:
          "The advisor's verdict. BUY names one exact contract to buy; SELL points to a short; WAIT means no setup cleared the score, risk and expected-value gates — standing aside is a deliberate recommendation.",
      },
      {
        term: 'Risk-Reward Ratio (R:R)',
        definition:
          'How much you stand to gain vs lose. A 1:2 R:R means you risk ₹100 to target ₹200. The risk engine only approves setups above a minimum R:R.',
      },
      {
        term: 'Stop Loss',
        definition:
          'The premium level at which the trade is exited to cap the loss. It is placed based on the underlying’s invalidation level, translated into option-premium space.',
      },
      {
        term: 'Targets (T1 / T2)',
        definition:
          'Pre-defined profit levels. T1 books partial profit early; T2 is the fuller objective. Price may never reach them — that is why the stop loss matters.',
      },
      {
        term: 'Net Expected Value (Net EV)',
        definition:
          'The rupee expected value of the trade after all costs (brokerage, taxes, SEBI fees, stamp duty, slippage, spread). A positive number means the numbers work; it is still not a guarantee — it is an estimate, not an edge claim.',
      },
      {
        term: 'Expectancy (R)',
        definition:
          'Average profit (or loss) expressed in units of risk. 0.2R means, on average, you earn 20% of your risked amount per trade over many repetitions.',
      },
      {
        term: 'Probability',
        definition:
          'The model’s estimated chance the trade works out. It is a prior from quantitative factors — positives still get filtered by the risk engine before a brief is published.',
      },
      {
        term: 'Classification',
        definition:
          'How the system rated the setup: exceptional, high_quality, valid, watch, weak, or no_trade. Only the top tiers clear the acceptance gate.',
      },
    ],
  },
  {
    id: 'system',
    title: 'Regime & System',
    icon: Radio,
    terms: [
      {
        term: 'Market Regime',
        definition:
          'The current behaviour of the market — strong uptrend, range bound, high volatility, etc. It is computed by a deterministic rule-based classifier (no AI bias). Strategies are only enabled in regimes they are built for.',
      },
      {
        term: 'Signal / Candidate Setup',
        definition:
          'A strategy has detected an entry condition and produced a candidate setup: direction, entry, stop loss, targets, invalidation level, and expected value.',
      },
      {
        term: 'Score',
        definition:
          'A weighted score from the sentiment/scoring layer that combines trend, volatility, OI structure and risk factors. It must clear a threshold to be accepted.',
      },
      {
        term: 'Acceptance Gate',
        definition:
          "The risk engine's checklist before anything is acted on: minimum score, minimum R:R, minimum net EV, risk per-trade cap, daily-loss limit, trade-count limit, and cooldown rules. Fail any check and the setup is rejected with a reason.",
      },
      {
        term: 'Contradiction',
        definition:
          'When different data layers disagree — e.g. a bullish price pattern vs heavy call writing at resistance. Gemini flags these deliberately instead of papering over them.',
      },
      {
        term: 'Paper Trading',
        definition:
          'Trades executed with virtual money through the full state machine (signal → entry → monitor → exit). It tests the system’s live decisions without risking real capital.',
      },
    ],
  },
];
export const FieldGuide: React.FC = () => {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState<Record<string, boolean>>(
    Object.fromEntries(GROUPS.map((g) => [g.id, true]))
  );

  const q = query.trim().toLowerCase();
  const visibleTerms = (terms: Term[]) =>
    q
      ? terms.filter(
          (t) =>
            t.term.toLowerCase().includes(q) ||
            t.definition.toLowerCase().includes(q)
        )
      : terms;

  const toggleGroup = (id: string) =>
    setOpen((prev) => ({ ...prev, [id]: !prev[id] }));

  const hasAnyMatches = GROUPS.some((g) => visibleTerms(g.terms).length > 0);

  return (
    <div className="glass-panel rounded-2xl p-6 border border-slate-800 bg-[#0f172a]/70">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-slate-800/80 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <BookOpen className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">
              Field Guide — Plain-English Dictionary
            </h3>
            <p className="text-xs text-slate-400">
              Every term on this page, translated. No niche jargon.
            </p>
          </div>
        </div>

        {/* Search */}
        <div className="relative sm:w-64 w-full">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search a term…"
            className="w-full bg-slate-900/70 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500/50 focus:ring-1 focus:ring-sky-500/30"
          />
        </div>
      </div>

      {/* No results */}
      {!hasAnyMatches && q && (
        <div className="py-8 text-center text-xs text-slate-400">
          No terms match “{query}”. Try “OI”, “premium”, “regime”…
        </div>
      )}
{/* Groups */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {GROUPS.map((group) => {
          const terms = visibleTerms(group.terms);
          const isOpen = open[group.id];

          if (terms.length === 0) return null;

          return (
            <div
              key={group.id}
              className="rounded-xl border border-slate-800/80 bg-slate-900/40 overflow-hidden"
            >
              {/* Group header */}
              <button
                onClick={() => toggleGroup(group.id)}
                className="w-full flex items-center justify-between gap-2 px-4 py-3 text-left hover:bg-slate-900/70 transition-colors"
              >
                <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-200">
                  <group.icon className="w-3.5 h-3.5 text-sky-400" />
                  {group.title}
                  <span className="text-[10px] font-medium text-slate-500 normal-case">
                    {terms.length} term{terms.length === 1 ? '' : 's'}
                  </span>
                </span>
                <ChevronDown
                  className={`w-4 h-4 text-slate-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                />
              </button>

              {/* Group body */}
              {isOpen && (
                <ul className="px-4 pb-4 space-y-3">
                  {terms.map((t) => (
                    <li key={t.term} className="text-xs">
                      <div className="font-semibold text-sky-300">{t.term}</div>
                      <div className="text-slate-300/90 mt-0.5 leading-relaxed">
                        {t.definition}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-3 border-t border-slate-800/60 text-[11px] text-slate-500 flex items-center gap-1.5">
        <Info className="w-3.5 h-3.5 shrink-0" />
        Decision-support for research & learning. Definitions are simplified for
        readability — check NSE and broker documentation before trading.
      </div>
    </div>
  );
};