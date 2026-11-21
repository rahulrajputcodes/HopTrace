import test from 'node:test';
import assert from 'node:assert/strict';

function formatElapsed(createdIso, nowMs = Date.now()) {
  if (!createdIso) return '0s';
  const created = new Date(createdIso).getTime();
  if (isNaN(created)) return '0s';
  const diffSec = Math.max(0, Math.floor((nowMs - created) / 1000));
  if (diffSec < 60) return `${diffSec}s`;
  const m = Math.floor(diffSec / 60);
  const s = diffSec % 60;
  return `${m}m ${s}s`;
}

test('formatElapsed: handles seconds correctly', () => {
  const now = 1700000100000;
  const iso = new Date(now - 45000).toISOString();
  assert.equal(formatElapsed(iso, now), '45s');
});

test('formatElapsed: handles minutes and seconds correctly', () => {
  const now = 1700000100000;
  const iso = new Date(now - 135000).toISOString();
  assert.equal(formatElapsed(iso, now), '2m 15s');
});

test('formatElapsed: handles null and invalid dates', () => {
  assert.equal(formatElapsed(null), '0s');
  assert.equal(formatElapsed('invalid-date'), '0s');
});
