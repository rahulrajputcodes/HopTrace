/**
 * M4 — PublicStatus pure-function tests
 * node:test + node:assert/strict (no JSDOM, no React renderer).
 * Run from frontend/: node --test src/pages/PublicStatus/PublicStatus.test.js
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { statusConfig, formatUpdatedAt } from './helpers.js';
import { STRINGS, REQUIRED_KEYS } from './strings.js';

describe('statusConfig', () => {
  it('up → green tokens', () => {
    const cfg = statusConfig('up');
    assert.equal(cfg.label, 'up');
    assert.ok(cfg.colorClass.includes('green'));
    assert.ok(cfg.bgClass.includes('green'));
    assert.ok(cfg.borderClass.includes('green'));
    assert.ok(cfg.dotClass.includes('green'));
  });

  it('degraded → amber tokens', () => {
    const cfg = statusConfig('degraded');
    assert.equal(cfg.label, 'degraded');
    assert.ok(cfg.colorClass.includes('amber'));
    assert.ok(cfg.bgClass.includes('amber'));
  });

  it('down → red tokens', () => {
    const cfg = statusConfig('down');
    assert.equal(cfg.label, 'down');
    assert.ok(cfg.colorClass.includes('red'));
    assert.ok(cfg.bgClass.includes('red'));
  });

  it('no_data → slate tokens', () => {
    const cfg = statusConfig('no_data');
    assert.equal(cfg.label, 'no_data');
    assert.ok(cfg.colorClass.includes('slate'));
  });

  it('unknown value → graceful fallback, slate tokens', () => {
    const cfg = statusConfig('some_future_status_xyz');
    assert.ok(cfg !== null && cfg !== undefined);
    assert.ok(typeof cfg.colorClass === 'string');
    assert.ok(cfg.colorClass.includes('slate'));
  });

  it('null input → graceful fallback', () => {
    const cfg = statusConfig(null);
    assert.ok(typeof cfg.colorClass === 'string');
  });

  it('undefined input → graceful fallback', () => {
    const cfg = statusConfig(undefined);
    assert.ok(typeof cfg.colorClass === 'string');
  });
});

describe('formatUpdatedAt', () => {
  it('very recent → "just now"', () => {
    const iso = new Date(Date.now() - 3_000).toISOString();
    assert.equal(formatUpdatedAt(iso, 'en'), 'just now');
  });

  it('~45s ago → "Xs ago"', () => {
    const iso = new Date(Date.now() - 45_000).toISOString();
    assert.match(formatUpdatedAt(iso, 'en'), /^\d+s ago$/);
  });

  it('~5min ago → "Xm ago"', () => {
    const iso = new Date(Date.now() - 5 * 60_000).toISOString();
    assert.match(formatUpdatedAt(iso, 'en'), /^\d+m ago$/);
  });

  it('null → "–"', () => {
    assert.equal(formatUpdatedAt(null, 'en'), '–');
  });

  it('undefined → "–"', () => {
    assert.equal(formatUpdatedAt(undefined, 'en'), '–');
  });

  it('invalid string → "–"', () => {
    assert.equal(formatUpdatedAt('not-a-date', 'en'), '–');
  });

  it('hi lang recent → "अभी"', () => {
    const iso = new Date(Date.now() - 3_000).toISOString();
    assert.equal(formatUpdatedAt(iso, 'hi'), 'अभी');
  });

  it('hi lang ~45s → contains "पहले"', () => {
    const iso = new Date(Date.now() - 45_000).toISOString();
    assert.ok(formatUpdatedAt(iso, 'hi').includes('पहले'));
  });
});

describe('STRINGS', () => {
  it('STRINGS.en has all required keys', () => {
    const missing = REQUIRED_KEYS.filter(k => !(k in STRINGS.en));
    assert.deepEqual(missing, []);
  });

  it('STRINGS.hi has all required keys', () => {
    const missing = REQUIRED_KEYS.filter(k => !(k in STRINGS.hi));
    assert.deepEqual(missing, []);
  });

  it('STRINGS.en all values are non-empty strings', () => {
    for (const [k, v] of Object.entries(STRINGS.en)) {
      assert.ok(typeof v === 'string' && v.length > 0, `STRINGS.en.${k} must be non-empty`);
    }
  });

  it('STRINGS.hi all values are non-empty strings', () => {
    for (const [k, v] of Object.entries(STRINGS.hi)) {
      assert.ok(typeof v === 'string' && v.length > 0, `STRINGS.hi.${k} must be non-empty`);
    }
  });

  it('en and hi have identical key sets', () => {
    const enKeys = Object.keys(STRINGS.en).sort();
    const hiKeys = Object.keys(STRINGS.hi).sort();
    assert.deepEqual(enKeys, hiKeys);
  });
});
