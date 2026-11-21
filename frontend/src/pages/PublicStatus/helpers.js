/**
 * M4 — PublicStatus pure helpers.
 *
 * publicApi  — unauthenticated fetch wrapper (no auth headers, no api() from useApi.js)
 * statusConfig — status enum → Tailwind colour tokens
 * formatUpdatedAt — ISO timestamp → human-readable relative string
 * tryPlayVoice — optional audio playback; returns false silently on any failure
 */

// ---------------------------------------------------------------------------
// publicApi
// ---------------------------------------------------------------------------

const BASE = '/api/v1';

/**
 * Lightweight public API fetch — NO auth headers.
 * Throws an Error on non-2xx responses so callers can distinguish
 * fetch failures from successful "empty" responses.
 *
 * @param {string} path   e.g. '/public/villages?lang=en'
 * @param {RequestInit} [opts]
 * @returns {Promise<any>}  parsed JSON body
 */
export async function publicApi(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// statusConfig
// ---------------------------------------------------------------------------

const STATUS_MAP = {
  up: {
    label: 'up',
    colorClass: 'text-green-700',
    bgClass: 'bg-green-100',
    borderClass: 'border-green-300',
    dotClass: 'bg-green-500',
  },
  degraded: {
    label: 'degraded',
    colorClass: 'text-amber-700',
    bgClass: 'bg-amber-100',
    borderClass: 'border-amber-300',
    dotClass: 'bg-amber-500',
  },
  down: {
    label: 'down',
    colorClass: 'text-red-700',
    bgClass: 'bg-red-100',
    borderClass: 'border-red-300',
    dotClass: 'bg-red-500',
  },
  no_data: {
    label: 'no_data',
    colorClass: 'text-slate-500',
    bgClass: 'bg-slate-100',
    borderClass: 'border-slate-300',
    dotClass: 'bg-slate-400',
  },
};

/** Fallback config for unrecognised status values */
const FALLBACK_CONFIG = {
  label: 'unknown',
  colorClass: 'text-slate-500',
  bgClass: 'bg-slate-100',
  borderClass: 'border-slate-300',
  dotClass: 'bg-slate-400',
};

/**
 * Returns Tailwind styling tokens for a given village status string.
 * Never throws — returns FALLBACK_CONFIG for unexpected values.
 *
 * @param {string} status  'up' | 'degraded' | 'down' | 'no_data' | <anything>
 * @returns {{ label, colorClass, bgClass, borderClass, dotClass }}
 */
export function statusConfig(status) {
  return STATUS_MAP[status] ?? FALLBACK_CONFIG;
}

// ---------------------------------------------------------------------------
// formatUpdatedAt
// ---------------------------------------------------------------------------

/**
 * Converts an ISO timestamp to a human-readable relative string.
 * Returns "–" for null/undefined/invalid input (never throws).
 *
 * @param {string|null|undefined} iso   ISO 8601 timestamp
 * @param {'en'|'hi'} lang
 * @returns {string}
 */
export function formatUpdatedAt(iso, lang = 'en') {
  if (!iso) return '–';
  let ms;
  try {
    ms = Date.now() - new Date(iso).getTime();
  } catch {
    return '–';
  }
  if (!Number.isFinite(ms) || ms < 0) return '–';

  const secs = Math.floor(ms / 1000);
  if (secs < 10) return lang === 'hi' ? 'अभी' : 'just now';

  const mins = Math.floor(secs / 60);
  if (mins < 1) return lang === 'hi' ? `${secs}s पहले` : `${secs}s ago`;

  const hrs = Math.floor(mins / 60);
  if (hrs < 1) return lang === 'hi' ? `${mins}m पहले` : `${mins}m ago`;

  const days = Math.floor(hrs / 24);
  if (days < 1) return lang === 'hi' ? `${hrs}h पहले` : `${hrs}h ago`;
  return lang === 'hi' ? `${days}d पहले` : `${days}d ago`;
}

// ---------------------------------------------------------------------------
// tryPlayVoice
// ---------------------------------------------------------------------------

/**
 * Attempts to fetch and play an audio update from the voice endpoint.
 * Returns false silently on any failure (503, network error, decode error).
 * Never throws, never logs to the user.
 *
 * @param {string} villageId
 * @param {'en'|'hi'} lang
 * @returns {Promise<boolean>}  true if playback started, false otherwise
 */
export async function tryPlayVoice(villageId, lang) {
  try {
    const res = await fetch(`${BASE}/voice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ village_id: villageId, lang }),
    });
    // Treat anything non-2xx (including 503) as "not available"
    if (!res.ok) return false;

    const data = await res.json().catch(() => null);
    if (!data || !data.audio_base64 || !data.mime) return false;

    // Decode base64 → ArrayBuffer → AudioBuffer → play
    const binary = atob(data.audio_base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

    const ctx = new AudioContext();
    const audioBuffer = await ctx.decodeAudioData(bytes.buffer);
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    source.start(0);
    return true;
  } catch {
    return false;
  }
}
