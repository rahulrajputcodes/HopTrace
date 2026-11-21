/**
 * M4 — PublicStatus pure-function tests
 *
 * Uses node:test + node:assert/strict (no JSDOM, no React renderer).
 * Tests cover only helpers.js and strings.js — the pure, importable logic.
 * React component rendering is excluded (no JSDOM in node --test baseline).
 *
 * Run from frontend/: node --test src/pages/PublicStatus/PublicStatus.test.js
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { statusConfig, formatUpdatedAt } from './helpers.js';
import { STRINGS, REQUIRED_KEYS } from './strings.js';

// ---------------------------------------------------------------------------
// statusConfig
// ---------------------------------------------------------------------------
describe('statusConfig', () => {
  it('up → green tokens', () => {
    const cfg = statusConfig('up');
    assert.equal(cfg.label, 'up');
    assert.ok(cfg.colorClass.includes('green'), `expected green in colorClass, got: ${cfg.colorClass}`);
    assert.ok(cfg.bgClass.includes('green'), `expected green in bgClass, got: ${cfg.bgClass}`);
    assert.ok(cfg.borderClass.includes('green'));
    assert.ok(cfg.dotClass.includes('green'));
  });

  it('degraded → amber tokens', () => {
    const cfg = statusConfig('degraded');
    assert.equal(cfg.label, 'degraded');
    assert.ok(cfg.colorClass.includes('amber'));
    assert.ok(cfg.bgClass.includes('amber'));
    assert.ok(cfg.borderClass.includes('amber'));
    assert.ok(cfg.dotClass.includes('amber'));
  });

  it('down → red tokens', () => {
    const cfg = statusConfig('down');
    assert.equal(cfg.label, 'down');
    assert.ok(cfg.colorClass.includes('red'));
    assert.ok(cfg.bgClass.includes('red'));
    assert.ok(cfg.borderClass.includes('red'));
    assert.ok(cfg.dotClass.includes('red'));
  });

  it('no_data → slate tokens', () => {
    const cfg = statusConfig('no_data');
    assert.equal(cfg.label, 'no_data');
    assert.ok(cfg.colorClass.includes('slate'));
    assert.ok(cfg.bgClass.includes('slate'));
    assert.ok(cfg.borderClass.includes('slate'));
    assert.ok(cfg.dotClass.includes('slate'));
  });

  it('unknown value → graceful fallback (no crash, slate tokens)', () => {
    const cfg = statusConfig('some_future_status_xyz');
    assert.ok(cfg !== null && cfg !== undefined, 'must not return null/undefined');
    assert.ok(typeof cfg.colorClass === 'string', 'colorClass must be a string');
    assert.ok(typeof cfg.bgClass === 'string', 'bgClass must be a string');
    assert.ok(typeof cfg.borderClass === 'string', 'borderClass must be a string');
    assert.ok(typeof cfg.dotClass === 'string', 'dotClass must be a string');
    // Should fall back to slate
    assert.ok(cfg.colorClass.includes('slate'), `fallback colorClass should contain 'slate', got: ${cfg.colorClass}`);
  });

  it('null input → graceful fallback (no crash)', () => {
    const cfg = statusConfig(null);
    assert.ok(cfg !== null && cfg !== undefined);
    assert.ok(typeof cfg.colorClass === 'string');
  });

  it('undefined input → graceful fallback (no crash)', () => {
    const cfg = statusConfig(undefined);
    assert.ok(cfg !== null && cfg !== undefined);
    assert.ok(typeof cfg.colorClass === 'string');
  });
});

// ---------------------------------------------------------------------------
// formatUpdatedAt
// ---------------------------------------------------------------------------
describe('formatUpdatedAt', () => {
  it('very recent ISO timestamp → "just now"', () => {
    const iso = new Date(Date.now() - 3_000).toISOString(); // 3 seconds ago
    const result = formatUpdatedAt(iso, 'en');
    assert.equal(result, 'just now', `expected "just now", got: "${result}"`);
  });

  it('~45 seconds ago → "Xs ago" pattern', () => {
    const iso = new Date(Date.now() - 45_000).toISOString();
    const result = formatUpdatedAt(iso, 'en');
    assert.match(result, /^\d+s ago$/, `expected "Xs ago" format, got: "${result}"`);
  });

  it('~5 minutes ago → "Xm ago" pattern', () => {
    const iso = new Date(Date.now() - 5 * 60_000).toISOString();
    const result = formatUpdatedAt(iso, 'en');
    assert.match(result, /^\d+m ago$/, `expected "Xm ago" format, got: "${result}"`);
  });

  it('null → returns "–" without throwing', () => {
    const result = formatUpdatedAt(null, 'en');
    assert.equal(result, '–');
  });

  it('undefined → returns "–" without throwing', () => {
    const result = formatUpdatedAt(undefined, 'en');
    assert.equal(result, '–');
  });

  it('invalid string → returns "–" without throwing', () => {
    const result = formatUpdatedAt('not-a-date', 'en');
    assert.equal(result, '–');
  });

  it('hi lang → returns Hindi relative text for recent timestamp', () => {
    const iso = new Date(Date.now() - 3_000).toISOString();
    const result = formatUpdatedAt(iso, 'hi');
    assert.equal(result, 'अभी', `expected Hindi "अभी", got: "${result}"`);
  });

  it('hi lang ~45s → contains "पहले"', () => {
    const iso = new Date(Date.now() - 45_000).toISOString();
    const result = formatUpdatedAt(iso, 'hi');
    assert.ok(result.includes('पहले'), `expected "पहले" in result, got: "${result}"`);
  });
});

// ---------------------------------------------------------------------------
// STRINGS — completeness
// ---------------------------------------------------------------------------
describe('STRINGS', () => {
  it('STRINGS.en has all required keys', () => {
    const missing = REQUIRED_KEYS.filter(k => !(k in STRINGS.en));
    assert.deepEqual(missing, [], `STRINGS.en missing keys: ${missing.join(', ')}`);
  });

  it('STRINGS.hi has all required keys', () => {
    const missing = REQUIRED_KEYS.filter(k => !(k in STRINGS.hi));
    assert.deepEqual(missing, [], `STRINGS.hi missing keys: ${missing.join(', ')}`);
  });

  it('STRINGS.en all values are non-empty strings', () => {
    for (const [k, v] of Object.entries(STRINGS.en)) {
      assert.ok(typeof v === 'string' && v.length > 0, `STRINGS.en.${k} must be a non-empty string`);
    }
  });

  it('STRINGS.hi all values are non-empty strings', () => {
    for (const [k, v] of Object.entries(STRINGS.hi)) {
      assert.ok(typeof v === 'string' && v.length > 0, `STRINGS.hi.${k} must be a non-empty string`);
    }
  });

  it('STRINGS.en and STRINGS.hi have the same set of keys', () => {
    const enKeys = Object.keys(STRINGS.en).sort();
    const hiKeys = Object.keys(STRINGS.hi).sort();
    assert.deepEqual(enKeys, hiKeys, 'en and hi must have identical keys');
  });
});
