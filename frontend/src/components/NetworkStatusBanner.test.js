import test from 'node:test';
import assert from 'node:assert/strict';
import {
  formatElapsed,
  formatRevenue,
  getNextStep,
} from './networkStatusHelpers.js';

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

test('formatElapsed: handles hours and minutes correctly', () => {
  const now = 1700000100000;
  const iso = new Date(now - (3600000 + 120000)).toISOString();
  assert.equal(formatElapsed(iso, now), '1h 2m');
});

test('formatElapsed: handles null and invalid dates', () => {
  assert.equal(formatElapsed(null), '0s');
  assert.equal(formatElapsed('invalid-date'), '0s');
});

test('formatRevenue: formats numbers in INR currency format', () => {
  assert.equal(formatRevenue(2397), '₹2,397');
  assert.equal(formatRevenue(150000), '₹1,50,000');
  assert.equal(formatRevenue(0), '₹0');
  assert.equal(formatRevenue(null), null);
  assert.equal(formatRevenue(undefined), null);
  assert.equal(formatRevenue('invalid'), null);
});

test('getNextStep: returns null when incident is null or missing', () => {
  assert.equal(getNextStep(null, null), null);
  assert.equal(getNextStep(undefined, null), null);
});

test('getNextStep: resolves first step from aiReport.field_operator_steps', () => {
  const incident = { id: 'inc-1', suspected_component_id: 'L3' };
  const aiReport = {
    field_operator_steps: [
      'Step 1: Check the 5 GHz bridge on L3 alignment',
      'Step 2: Inspect power supply',
    ],
  };
  assert.equal(
    getNextStep(incident, aiReport),
    'Check the 5 GHz bridge on L3 alignment'
  );
});

test('getNextStep: prefers explicit next_step or recommendation on incident', () => {
  const incidentWithNext = {
    id: 'inc-2',
    next_step: 'Replace fiber patch cord at Rampur Node',
  };
  assert.equal(
    getNextStep(incidentWithNext, null),
    'Replace fiber patch cord at Rampur Node'
  );

  const incidentWithRec = {
    id: 'inc-3',
    recommendation: 'Reboot upstream switch',
  };
  assert.equal(getNextStep(incidentWithRec, null), 'Reboot upstream switch');
});

test('getNextStep: heuristic fallback for L3 degradation', () => {
  const incidentL3 = {
    id: 'inc-4',
    suspected_component_id: 'L3',
    summary: '[isolated] Degradation localized to link L3',
  };
  assert.equal(
    getNextStep(incidentL3, null),
    'Check the 5 GHz bridge on L3 alignment'
  );
});

test('getNextStep: heuristic fallback for Upstream Gateway failure', () => {
  const incidentGW = {
    id: 'inc-5',
    suspected_component_id: 'GW1',
    summary: 'Upstream gateway failure',
  };
  assert.equal(
    getNextStep(incidentGW, null),
    'Verify optical backhaul link and gateway router power'
  );
});

test('getNextStep: returns null when no heuristic or explanation matches', () => {
  const incidentGeneric = {
    id: 'inc-6',
    suspected_component_id: 'XYZ_UNKNOWN',
    summary: 'Generic anomaly',
  };
  assert.equal(getNextStep(incidentGeneric, null), null);
});
