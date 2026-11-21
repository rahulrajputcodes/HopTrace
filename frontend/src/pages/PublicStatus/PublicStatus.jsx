/**
 * M4 — PublicStatus page component.
 *
 * NOTE: Not yet wired to a /status route — main.jsx has no React Router.
 * M2 must add routing. Do NOT edit main.jsx without M2 approval.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { STRINGS } from './strings.js';
import { publicApi, statusConfig, formatUpdatedAt, tryPlayVoice } from './helpers.js';

const POLL_INTERVAL_MS = 15_000;

function VillageCard({ village, lang, strings }) {
  const [voiceHidden, setVoiceHidden] = useState(false);
  const [voicePlaying, setVoicePlaying] = useState(false);

  const cfg = statusConfig(village.status);
  const isNoData = village.status === 'no_data';

  const handleVoice = async () => {
    setVoicePlaying(true);
    const ok = await tryPlayVoice(village.id, lang);
    setVoicePlaying(false);
    if (!ok) setVoiceHidden(true);
  };

  return (
    <article
      className={`rounded-xl border p-4 ${cfg.bgClass} ${cfg.borderClass} shadow-sm`}
      aria-label={`${village.name} — ${village.status}`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`inline-block h-2.5 w-2.5 flex-shrink-0 rounded-full ${cfg.dotClass}`} aria-hidden="true" />
          <h2 className="truncate text-base font-semibold text-slate-800">{village.name}</h2>
        </div>
        <span className={`flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.bgClass} ${cfg.colorClass} border ${cfg.borderClass}`}>
          {isNoData ? strings.statusNoData : (strings[`status${village.status.charAt(0).toUpperCase()}${village.status.slice(1)}`] ?? village.status)}
        </span>
      </div>
      <p className={`mt-2 text-sm ${isNoData ? 'text-slate-400 italic' : 'text-slate-600'}`}>
        {isNoData ? strings.dataUnavailable : (village.message || '—')}
      </p>
      {village.since && !isNoData && (
        <p className="mt-1 text-xs text-slate-400">{strings.since}: {formatUpdatedAt(village.since, lang)}</p>
      )}
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

export default function PublicStatus() {
  const [lang, setLang] = useState('en');
  const [villages, setVillages] = useState([]);
  const [updatedAt, setUpdatedAt] = useState(null);
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
      setFetchState('stale');
    }
  }, [lang]);

  useEffect(() => {
    const initial = setTimeout(doFetch, 0);
    intervalRef.current = setInterval(doFetch, POLL_INTERVAL_MS);
    return () => {
      clearTimeout(initial);
      clearInterval(intervalRef.current);
    };
  }, [doFetch]);

  const toggleLang = () => setLang(l => (l === 'en' ? 'hi' : 'en'));
  const tsColorClass = fetchState === 'stale' ? 'text-amber-500' : 'text-slate-400';

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur px-4 py-3 shadow-sm">
        <div className="mx-auto flex max-w-2xl items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-lg font-bold text-slate-800">{strings.title}</h1>
            <p className="truncate text-xs text-slate-500">{strings.subtitle}</p>
          </div>
          <button onClick={toggleLang} className="flex-shrink-0 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 active:scale-95 transition-all" aria-label="Switch language">
            {strings.langToggle}
          </button>
        </div>
      </header>
      <div className="mx-auto max-w-2xl px-4 pt-3 pb-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className={`text-xs ${tsColorClass}`}>
            {fetchState === 'loading' ? strings.loading : `${strings.lastUpdated}: ${formatUpdatedAt(updatedAt, lang)}`}
          </p>
          {fetchState === 'stale' && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-amber-600">{strings.staleWarning}</span>
              <button onClick={doFetch} className="rounded-lg bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700 hover:bg-amber-200 active:scale-95 transition-all border border-amber-300">{strings.retry}</button>
            </div>
          )}
        </div>
      </div>
      <main className="mx-auto max-w-2xl px-4 pb-10 pt-3">
        {fetchState === 'loading' && villages.length === 0 ? (
          <div className="mt-16 flex flex-col items-center gap-3 text-slate-400">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-blue-400" />
            <p className="text-sm">{strings.loading}</p>
          </div>
        ) : villages.length === 0 ? (
          <div className="mt-16 text-center text-slate-400">
            <p className="text-sm">{strings.noData}</p>
            <button onClick={doFetch} className="mt-4 rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200 transition-all">{strings.retry}</button>
          </div>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2" role="list">
            {villages.map(v => (
              <li key={v.id}><VillageCard village={v} lang={lang} strings={strings} /></li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
