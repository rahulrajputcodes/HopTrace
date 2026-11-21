/**
 * M4 — PublicStatus page
 *
 * Mobile-first public status page (375px+).
 * - No login required; uses publicApi (no auth headers).
 * - Polls /public/villages every 15 seconds.
 * - Language toggle (en / hi).
 * - On fetch error: keeps last good data, turns timestamp amber, shows Retry.
 * - no_data villages: slate card, explicit "unavailable" message.
 * - Optional voice playback: hides button silently on failure.
 *
 * NOTE: This component is NOT yet wired to a /status route.
 *       main.jsx renders <App /> directly (no React Router installed).
 *       Routing requires M2 to add a hash-route or React Router entry.
 *       Do NOT edit main.jsx without M2 approval.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { STRINGS } from './strings.js';
import { publicApi, statusConfig, formatUpdatedAt, tryPlayVoice } from './helpers.js';

const POLL_INTERVAL_MS = 15_000;

// ---------------------------------------------------------------------------
// VillageCard
// ---------------------------------------------------------------------------
function VillageCard({ village, lang, strings }) {
  const [voiceHidden, setVoiceHidden] = useState(false);
  const [voicePlaying, setVoicePlaying] = useState(false);

  const cfg = statusConfig(village.status);
  const isNoData = village.status === 'no_data';

  const handleVoice = async () => {
    setVoicePlaying(true);
    const ok = await tryPlayVoice(village.id, lang);
    setVoicePlaying(false);
    if (!ok) setVoiceHidden(true); // hide button silently on failure
  };

  return (
    <article
      className={`rounded-xl border p-4 ${cfg.bgClass} ${cfg.borderClass} shadow-sm`}
      aria-label={`${village.name} — ${village.status}`}
    >
      {/* Header row */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`inline-block h-2.5 w-2.5 flex-shrink-0 rounded-full ${cfg.dotClass}`}
            aria-hidden="true"
          />
          <h2 className="truncate text-base font-semibold text-slate-800">
            {village.name}
          </h2>
        </div>

        {/* Status pill */}
        {!isNoData && (
          <span
            className={`flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.bgClass} ${cfg.colorClass} border ${cfg.borderClass}`}
          >
            {strings[`status${village.status.charAt(0).toUpperCase() + village.status.slice(1).replace('_d', 'D')}`.replace('status_', 'statusNo_').replace('statusNo_data', 'statusNoData')] ?? village.status}
          </span>
        )}
        {isNoData && (
          <span className="flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium bg-slate-200 text-slate-500 border border-slate-300">
            {strings.statusNoData}
          </span>
        )}
      </div>

      {/* Message */}
      <p className={`mt-2 text-sm ${isNoData ? 'text-slate-400 italic' : 'text-slate-600'}`}>
        {isNoData ? strings.dataUnavailable : (village.message || '—')}
      </p>

      {/* Since */}
      {village.since && !isNoData && (
        <p className="mt-1 text-xs text-slate-400">
          {strings.since}: {formatUpdatedAt(village.since, lang)}
        </p>
      )}

      {/* Voice button — hidden if unavailable or already failed */}
      {!voiceHidden && !isNoData && (
        <button
          onClick={handleVoice}
          disabled={voicePlaying}
          className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-white/60 px-3 py-1.5 text-xs font-medium text-slate-700 border border-slate-200 hover:bg-white active:scale-95 disabled:opacity-50 transition-all"
          aria-label={strings.playAudio}
        >
          🔊 {voicePlaying ? '…' : strings.playAudio}
        </button>
      )}
    </article>
  );
}

// ---------------------------------------------------------------------------
// PublicStatus (main page)
// ---------------------------------------------------------------------------
export default function PublicStatus() {
  const [lang, setLang] = useState('en');
  const [villages, setVillages] = useState([]);
  const [updatedAt, setUpdatedAt] = useState(null);
  // 'loading' | 'ok' | 'stale'
  const [fetchState, setFetchState] = useState('loading');
  const intervalRef = useRef(null);
  const strings = STRINGS[lang] ?? STRINGS.en;

  const doFetch = useCallback(async () => {
    try {
      const data = await publicApi(`/public/villages?lang=${lang}`);
      setVillages(Array.isArray(data.villages) ? data.villages : []);
      setUpdatedAt(data.updated_at ?? new Date().toISOString());
      setFetchState('ok');
    } catch {
      // Keep last good data; mark stale (amber indicator + Retry)
      setFetchState(prev => (prev === 'loading' ? 'stale' : 'stale'));
    }
  }, [lang]);

  // Initial fetch + polling.
  // setTimeout(..., 0) defers the first doFetch out of the synchronous effect
  // body to satisfy react-hooks/set-state-in-effect (setState must not be
  // called synchronously inside an effect).
  useEffect(() => {
    const initial = setTimeout(doFetch, 0);
    intervalRef.current = setInterval(doFetch, POLL_INTERVAL_MS);
    return () => {
      clearTimeout(initial);
      clearInterval(intervalRef.current);
    };
  }, [doFetch]);

  const handleRetry = () => {
    setFetchState(prev => (prev === 'stale' ? 'stale' : prev)); // keep stale until success
    doFetch();
  };

  const toggleLang = () => setLang(l => (l === 'en' ? 'hi' : 'en'));

  // Timestamp indicator colour
  const tsColorClass =
    fetchState === 'stale' ? 'text-amber-500' : 'text-slate-400';

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top bar */}
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur px-4 py-3 shadow-sm">
        <div className="mx-auto flex max-w-2xl items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-lg font-bold text-slate-800">
              {strings.title}
            </h1>
            <p className="truncate text-xs text-slate-500">{strings.subtitle}</p>
          </div>

          {/* Lang toggle */}
          <button
            onClick={toggleLang}
            className="flex-shrink-0 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 active:scale-95 transition-all"
            aria-label="Switch language"
          >
            {strings.langToggle}
          </button>
        </div>
      </header>

      {/* Timestamp + stale warning */}
      <div className="mx-auto max-w-2xl px-4 pt-3 pb-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className={`text-xs ${tsColorClass}`}>
            {fetchState === 'loading'
              ? strings.loading
              : `${strings.lastUpdated}: ${formatUpdatedAt(updatedAt, lang)}`}
          </p>
          {fetchState === 'stale' && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-amber-600">{strings.staleWarning}</span>
              <button
                onClick={handleRetry}
                className="rounded-lg bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700 hover:bg-amber-200 active:scale-95 transition-all border border-amber-300"
              >
                {strings.retry}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Village cards */}
      <main className="mx-auto max-w-2xl px-4 pb-10 pt-3">
        {fetchState === 'loading' && villages.length === 0 ? (
          <div className="mt-16 flex flex-col items-center gap-3 text-slate-400">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-blue-400" />
            <p className="text-sm">{strings.loading}</p>
          </div>
        ) : villages.length === 0 ? (
          <div className="mt-16 text-center text-slate-400">
            <p className="text-sm">{strings.noData}</p>
            <button
              onClick={handleRetry}
              className="mt-4 rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200 transition-all"
            >
              {strings.retry}
            </button>
          </div>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2" role="list">
            {villages.map(v => (
              <li key={v.id}>
                <VillageCard village={v} lang={lang} strings={strings} />
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
