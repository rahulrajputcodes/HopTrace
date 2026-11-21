import test from 'node:test';
import assert from 'node:assert/strict';
import {
  riskColor,
  getLinkRisk,
  getLinkStrokeWidth,
  getLinkDashArray,
} from './risk.js';

test('riskColor: verifies all threshold bands', () => {
  // Healthy: < 40
  assert.equal(riskColor(0), '#10b981');
  assert.equal(riskColor(39.99), '#10b981');

  // Medium: 40 - 59.99
  assert.equal(riskColor(40), '#f59e0b');
  assert.equal(riskColor(59.99), '#f59e0b');

  // High: 60 - 79.99
  assert.equal(riskColor(60), '#f97316');
  assert.equal(riskColor(79.99), '#f97316');

  // Critical: >= 80
  assert.equal(riskColor(80), '#ef4444');
  assert.equal(riskColor(100), '#ef4444');

  // Missing / invalid data falls back to healthy
  assert.equal(riskColor(null), '#10b981');
  assert.equal(riskColor(undefined), '#10b981');
  assert.equal(riskColor(NaN), '#10b981');
});

test('getLinkRisk: derives score with precedence: snapshot > liveMap > fallback 0', () => {
  const snapshot = {
    L1: { risk_score: 85 },
    L2: { risk_score: 45 },
  };
  const liveMap = new Map([
    ['L2', { risk_score: 30 }], // snapshot wins for L2
    ['L3', { risk_score: 65 }], // only in liveMap
  ]);

  // Snapshot takes precedence
  assert.equal(getLinkRisk('L1', snapshot, liveMap), 85);
  assert.equal(getLinkRisk('L2', snapshot, liveMap), 45);

  // Live map used when snapshot missing
  assert.equal(getLinkRisk('L3', snapshot, liveMap), 65);

  // Fallback 0 when both missing
  assert.equal(getLinkRisk('L4', snapshot, liveMap), 0);
  assert.equal(getLinkRisk('L1', null, null), 0);
  assert.equal(getLinkRisk(null, snapshot, liveMap), 0);
});

test('getLinkStrokeWidth: scales with risk score and suspected flag', () => {
  assert.equal(getLinkStrokeWidth(0, false), 1.5);
  assert.equal(getLinkStrokeWidth(40, false), 2.5);
  assert.equal(getLinkStrokeWidth(80, false), 3.5);
  assert.equal(getLinkStrokeWidth(0, true), 4);
  assert.equal(getLinkStrokeWidth(85, true), 4);
});

test('getLinkDashArray: returns dashed only when connectivity_ok is strictly false', () => {
  assert.equal(getLinkDashArray(false), '6 4');
  assert.equal(getLinkDashArray(true), undefined);
  assert.equal(getLinkDashArray(undefined), undefined);
  assert.equal(getLinkDashArray(null), undefined);
});
