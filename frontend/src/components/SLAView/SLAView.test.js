/**
 * M4 — SLAView pure-function tests
 *
 * Uses node:test + node:assert/strict (no JSDOM, no React renderer).
 * Tests cover slaHelpers.js only.
 *
 * Run from frontend/: node --test src/components/SLAView/SLAView.test.js
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  formatUptime,
  formatDowntime,
  slaStatusConfig,
  windowLabel,
} from './slaHelpers.js';

// ---------------------------------------------------------------------------
// formatUptime
// ---------------------------------------------------------------------------
describe('formatUptime', () => {
  it('99.72 → "99.7%"', () => {
    assert.equal(formatUptime(99.72), '99.7%');
  });

  it('100 → "100.0%"', () => {
    assert.equal(formatUptime(100), '100.0%');
  });

  it('0 → "0.0%"', () => {
    assert.equal(formatUptime(0), '0.0%');
  });

  it('null → "–" (no crash)', () => {
    assert.equal(formatUptime(null), '–');
  });

  it('undefined → "–" (no crash)', () => {
    assert.equal(formatUptime(undefined), '–');
  });

  it('NaN → "–" (no crash)', () => {
    assert.equal(formatUptime(NaN), '–');
  });

  it('string "bad" → "–" (no crash)', () => {
    assert.equal(formatUptime('bad'), '–');
  });
});

// ---------------------------------------------------------------------------
// formatDowntime
// ---------------------------------------------------------------------------
describe('formatDowntime', () => {
  it('0 → "0m"', () => {
    assert.equal(formatDowntime(0), '0m');
  });

  it('135 → "2h 15m"', () => {
    assert.equal(formatDowntime(135), '2h 15m');
  });

  it('60 → "1h"', () => {
    assert.equal(formatDowntime(60), '1h');
  });

  it('45 → "45m"', () => {
    assert.equal(formatDowntime(45), '45m');
  });

  it('null → "–" (no crash)', () => {
    assert.equal(formatDowntime(null), '–');
  });

  it('undefined → "–" (no crash)', () => {
    assert.equal(formatDowntime(undefined), '–');
  });

  it('negative value → "0m"', () => {
    assert.equal(formatDowntime(-5), '0m');
  });
});

// ---------------------------------------------------------------------------
// slaStatusConfig
// ---------------------------------------------------------------------------
describe('slaStatusConfig', () => {
  it('healthy → emerald/green tokens', () => {
    const cfg = slaStatusConfig('healthy');
    assert.equal(cfg.label, 'Healthy');
    assert.ok(cfg.colorClass.includes('emerald'), `expected emerald in colorClass, got: ${cfg.colorClass}`);
    assert.ok(cfg.dotClass.includes('emerald'));
    assert.ok(typeof cfg.bgClass === 'string');
    assert.ok(typeof cfg.badgeClass === 'string');
  });

  it('degraded → amber tokens', () => {
    const cfg = slaStatusConfig('degraded');
    assert.equal(cfg.label, 'Degraded');
    assert.ok(cfg.colorClass.includes('amber'));
    assert.ok(cfg.dotClass.includes('amber'));
  });

  it('critical → red tokens', () => {
    const cfg = slaStatusConfig('critical');
    assert.equal(cfg.label, 'Critical');
    assert.ok(cfg.colorClass.includes('red'));
    assert.ok(cfg.dotClass.includes('red'));
  });

  it('unknown_xyz → graceful fallback (no crash, slate tokens)', () => {
    const cfg = slaStatusConfig('unknown_xyz');
    assert.ok(cfg !== null && cfg !== undefined);
    assert.ok(typeof cfg.colorClass === 'string');
    assert.ok(cfg.colorClass.includes('slate'), `fallback should be slate, got: ${cfg.colorClass}`);
  });

  it('null → graceful fallback (no crash)', () => {
    const cfg = slaStatusConfig(null);
    assert.ok(typeof cfg.label === 'string');
  });

  it('undefined → graceful fallback (no crash)', () => {
    const cfg = slaStatusConfig(undefined);
    assert.ok(typeof cfg.label === 'string');
  });
});

// ---------------------------------------------------------------------------
// windowLabel
// ---------------------------------------------------------------------------
describe('windowLabel', () => {
  it('24 → contains "24"', () => {
    const label = windowLabel(24);
    assert.ok(label.includes('24'), `expected "24" in label, got: "${label}"`);
  });

  it('168 → contains "7"', () => {
    const label = windowLabel(168);
    assert.ok(label.includes('7'), `expected "7" in label, got: "${label}"`);
  });

  it('720 → contains "30"', () => {
    const label = windowLabel(720);
    assert.ok(label.includes('30'), `expected "30" in label, got: "${label}"`);
  });

  it('arbitrary hours → fallback string containing the value', () => {
    const label = windowLabel(48);
    assert.ok(label.includes('48'), `expected "48" in fallback label, got: "${label}"`);
  });
});
