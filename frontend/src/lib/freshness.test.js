import test from 'node:test';
import assert from 'node:assert/strict';
import { freshnessStyle, isHealthyForKpi, formatLastSeen } from './freshness.js';

test('freshnessStyle: maps all freshness states correctly', () => {
  assert.deepEqual(freshnessStyle('live'), { label: 'Live', color: '#10b981', dashed: false });
  assert.deepEqual(freshnessStyle('stale'), { label: 'Stale', color: '#f59e0b', dashed: true });
  assert.deepEqual(freshnessStyle('no_data'), { label: 'No data', color: '#64748b', dashed: true });
  assert.deepEqual(freshnessStyle('simulated'), { label: 'Simulated', color: '#94a3b8', dashed: false });
  assert.deepEqual(freshnessStyle(null), { label: 'Unknown', color: '#64748b', dashed: true });
});

test('isHealthyForKpi: no_data links are never healthy', () => {
  const linkNoData = { id: 'L4', freshness: 'no_data', risk_score: 0 };
  assert.equal(isHealthyForKpi(linkNoData), false);

  const linkWithLiveNoData = { id: 'L5', live: { freshness: 'no_data' }, risk_score: 0 };
  assert.equal(isHealthyForKpi(linkWithLiveNoData), false);
});

test('isHealthyForKpi: down or high risk links are not healthy', () => {
  assert.equal(isHealthyForKpi({ id: 'L1', freshness: 'live', connectivity_ok: false }), false);
  assert.equal(isHealthyForKpi({ id: 'L2', freshness: 'live', isDown: true }), false);
  assert.equal(isHealthyForKpi({ id: 'L3', freshness: 'live', status: 'down' }), false);
  assert.equal(isHealthyForKpi({ id: 'L4', freshness: 'live', risk_score: 75 }), false);
});

test('isHealthyForKpi: valid connected links with data are healthy', () => {
  const healthyLink = {
    id: 'L1',
    freshness: 'live',
    connectivity_ok: true,
    risk_score: 10,
    live: { latency_ms: 12.0, packet_loss_pct: 0.0 },
  };
  assert.equal(isHealthyForKpi(healthyLink), true);
});

test('formatLastSeen: handles null, invalid, and elapsed time', () => {
  const fixedNow = new Date('2026-11-15T12:00:00Z').getTime();

  assert.equal(formatLastSeen(null, fixedNow), 'never seen');
  assert.equal(formatLastSeen('', fixedNow), 'never seen');
  assert.equal(formatLastSeen('invalid-date', fixedNow), 'never seen');

  // 42s ago
  const t42s = new Date(fixedNow - 42 * 1000).toISOString();
  assert.equal(formatLastSeen(t42s, fixedNow), 'last seen 42s ago');

  // 5m ago
  const t5m = new Date(fixedNow - 300 * 1000).toISOString();
  assert.equal(formatLastSeen(t5m, fixedNow), 'last seen 5m ago');

  // 2h ago
  const t2h = new Date(fixedNow - 7200 * 1000).toISOString();
  assert.equal(formatLastSeen(t2h, fixedNow), 'last seen 2h ago');
});
