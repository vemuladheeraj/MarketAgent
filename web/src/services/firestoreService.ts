import {
  collection,
  doc,
  onSnapshot,
  query,
  orderBy,
  limit,
  DocumentData,
} from 'firebase/firestore';
import { db } from '../config/firebase';
import {
  MarketSnapshot,
  GeminiAnalysis,
  RegimeAssessment,
  Signal,
  PaperTrade,
  RiskState,
  SystemEvent,
  TradeBrief,
} from '../types/market';

// --------------------------------------------------------------------------
// Real-time Firestore Listeners
// --------------------------------------------------------------------------

export function subscribeLatestSnapshot(
  callback: (data: MarketSnapshot | null) => void,
  onError?: (error: Error) => void
) {
  try {
    const coll = collection(db, 'marketSnapshots');
    return onSnapshot(
      coll,
      (snap) => {
        if (snap.empty) {
          callback(null);
          return;
        }
        // Pick latest by timestamp or doc ID
        const docs = snap.docs.map((d) => ({
          id: d.id,
          ...d.data(),
        })) as MarketSnapshot[];
        docs.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
        callback(docs[0] || null);
      },
      (err) => {
        console.warn('Firestore snapshot subscription error:', err);
        onError?.(err);
      }
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}

export function subscribeGeminiAnalyses(
  symbol: string,
  callback: (data: GeminiAnalysis | null) => void,
  onError?: (error: Error) => void
) {
  try {
    const coll = collection(db, 'geminiAnalyses');
    return onSnapshot(
      coll,
      (snap) => {
        if (snap.empty) {
          callback(null);
          return;
        }
        const docs = snap.docs
          .map((d) => ({ id: d.id, ...d.data() } as GeminiAnalysis))
          .filter((a) => !symbol || a.symbol?.toUpperCase() === symbol.toUpperCase());
        docs.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
        callback(docs[0] || null);
      },
      (err) => onError?.(err)
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}

export function subscribeRegimes(
  symbol: string,
  callback: (data: RegimeAssessment | null) => void,
  onError?: (error: Error) => void
) {
  try {
    const coll = collection(db, 'marketRegimes');
    return onSnapshot(
      coll,
      (snap) => {
        if (snap.empty) {
          callback(null);
          return;
        }
        const docs = snap.docs
          .map((d) => ({ id: d.id, ...d.data() } as RegimeAssessment))
          .filter((a) => !symbol || a.symbol?.toUpperCase() === symbol.toUpperCase());
        docs.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
        callback(docs[0] || null);
      },
      (err) => onError?.(err)
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}

export function subscribeSignals(
  callback: (signals: Signal[]) => void,
  onError?: (error: Error) => void
) {
  try {
    const coll = collection(db, 'signals');
    return onSnapshot(
      coll,
      (snap) => {
        const docs = snap.docs.map((d) => ({ id: d.id, ...d.data() } as Signal));
        docs.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
        callback(docs);
      },
      (err) => onError?.(err)
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}

export function subscribePaperTrades(
  callback: (trades: PaperTrade[]) => void,
  onError?: (error: Error) => void
) {
  try {
    const coll = collection(db, 'paperTrades');
    return onSnapshot(
      coll,
      (snap) => {
        const docs = snap.docs.map((d) => ({ id: d.id, ...d.data() } as PaperTrade));
        docs.sort((a, b) => (b.entry_time || '').localeCompare(a.entry_time || ''));
        callback(docs);
      },
      (err) => onError?.(err)
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}

export function subscribeSystemEvents(
  callback: (events: SystemEvent[]) => void,
  onError?: (error: Error) => void
) {
  try {
    const coll = collection(db, 'systemEvents');
    return onSnapshot(
      coll,
      (snap) => {
        const docs = snap.docs.map((d) => ({ id: d.id, ...d.data() } as SystemEvent));
        docs.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
        callback(docs.slice(0, 30));
      },
      (err) => onError?.(err)
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}

/**
 * Live present-moment trade brief for one symbol.
 * The backend keeps `tradeBriefs/current_<SYMBOL>` fresh on every cycle.
 */
export function subscribeTradeBrief(
  symbol: string,
  callback: (data: TradeBrief | null) => void,
  onError?: (error: Error) => void
) {
  try {
    const ref = doc(db, 'tradeBriefs', `current_${symbol.toUpperCase()}`);
    return onSnapshot(
      ref,
      (snap) => {
        callback(snap.exists() ? ({ id: snap.id, ...snap.data() } as TradeBrief) : null);
      },
      (err) => onError?.(err)
    );
  } catch (err: any) {
    onError?.(err);
    return () => {};
  }
}
