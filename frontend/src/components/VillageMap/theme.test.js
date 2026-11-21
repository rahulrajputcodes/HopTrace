import test from 'node:test';
import assert from 'node:assert/strict';
import { telemetryLabel, villageStatusColor } from './theme.js';

test('villageStatusColor: maps all backend status strings', () => {
  assert.equal(villageStatusColor('healthy'), '#10b981');
  assert.equal(villageStatusColor('degraded'), '#f59e0b');
  assert.equal(villageStatusColor('critical'), '#ef4444');
  assert.equal(villageStatusColor('unknown'), '#64748b');
  assert.equal(villageStatusColor(null), '#64748b');
  assert.equal(villageStatusColor(undefined), '#64748b');
  assert.equal(villageStatusColor('invalid'), '#64748b');
});

test('telemetryLabel: returns Simulated telemetry for simulated', () => {
  assert.equal(telemetryLabel('simulated'), 'Simulated telemetry');
});

test('telemetryLabel: returns Measured telemetry for measured', () => {
  assert.equal(telemetryLabel('measured'), 'Measured telemetry');
});

test('telemetryLabel: returns null for anything else', () => {
  assert.equal(telemetryLabel('loading'), null);
  assert.equal(telemetryLabel('unknown'), null);
  assert.equal(telemetryLabel(null), null);
  assert.equal(telemetryLabel(undefined), null);
  assert.equal(telemetryLabel(''), null);
});
