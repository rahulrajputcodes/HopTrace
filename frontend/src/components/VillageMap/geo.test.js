import test from 'node:test';
import assert from 'node:assert/strict';
import {
  computeBounds,
  parseGHz,
  fresnelF1Metres,
  clearance60,
  getLinkMidpoint,
  getPredictedEtaMinutes,
} from './geo.js';

test('computeBounds: returns null for non-array or empty inputs', () => {
  assert.equal(computeBounds(null), null);
  assert.equal(computeBounds(undefined), null);
  assert.equal(computeBounds([]), null);
  assert.equal(computeBounds('invalid'), null);
});

test('computeBounds: returns null if no nodes have finite lat and lon', () => {
  const nodes = [
    { id: 'n1', lat: null, lon: 80.5 },
    { id: 'n2', lat: 'invalid', lon: 80.5 },
    { id: 'n3', lat: NaN, lon: NaN },
    { id: 'n4', lat: 27.1, lon: undefined },
    null,
  ];
  assert.equal(computeBounds(nodes), null);
});

test('computeBounds: computes bounding box correctly for valid nodes', () => {
  const nodes = [
    { id: 'n1', lat: 27.20000, lon: 80.60000 },
    { id: 'n2', lat: 27.22879, lon: 80.60000 },
    { id: 'n3', lat: 27.17511, lon: 80.62534 },
    { id: 'n4', lat: null, lon: null },
  ];
  const bounds = computeBounds(nodes);
  assert.ok(bounds);
  assert.deepEqual(bounds, [
    [27.17511, 80.60000],
    [27.22879, 80.62534],
  ]);
});

test('computeBounds: handles single valid node', () => {
  const nodes = [{ id: 'n1', lat: 27.2, lon: 80.6 }];
  const bounds = computeBounds(nodes);
  assert.deepEqual(bounds, [
    [27.2, 80.6],
    [27.2, 80.6],
  ]);
});

test('parseGHz: parses strings case-insensitively with optional spaces', () => {
  assert.equal(parseGHz('5GHz'), 5);
  assert.equal(parseGHz('5 GHz'), 5);
  assert.equal(parseGHz('60ghz'), 60);
  assert.equal(parseGHz('60 GHz'), 60);
  assert.equal(parseGHz('2.4 GHz'), 2.4);
});

test('parseGHz: returns null on unparsable, non-positive, or invalid input', () => {
  assert.equal(parseGHz('fiber'), null);
  assert.equal(parseGHz(''), null);
  assert.equal(parseGHz('0 GHz'), null);
  assert.equal(parseGHz('-5 GHz'), null);
  assert.equal(parseGHz('GHz'), null);
  assert.equal(parseGHz(null), null);
  assert.equal(parseGHz(undefined), null);
  assert.equal(parseGHz(5), null);
});

test('fresnelF1Metres and clearance60: exact matches for L3, L7, and L12 (tolerance 0.01 m)', () => {
  // L3: 3.2 km, 5 GHz -> F1 6.93 m, clearance 4.16 m
  const f1_L3 = fresnelF1Metres(3.2, 5);
  assert.ok(f1_L3 !== null);
  assert.ok(Math.abs(f1_L3 - 6.93) < 0.01, `L3 F1: got ${f1_L3}`);
  const c60_L3 = clearance60(f1_L3);
  assert.ok(c60_L3 !== null);
  assert.ok(Math.abs(c60_L3 - 4.16) < 0.01, `L3 clearance: got ${c60_L3}`);

  // L7: 2.8 km, 60 GHz -> F1 1.87 m, clearance 1.12 m
  const f1_L7 = fresnelF1Metres(2.8, 60);
  assert.ok(f1_L7 !== null);
  assert.ok(Math.abs(f1_L7 - 1.87) < 0.01, `L7 F1: got ${f1_L7}`);
  const c60_L7 = clearance60(f1_L7);
  assert.ok(c60_L7 !== null);
  assert.ok(Math.abs(c60_L7 - 1.12) < 0.01, `L7 clearance: got ${c60_L7}`);

  // L12: 4.1 km, 5 GHz -> F1 7.84 m, clearance 4.71 m
  const f1_L12 = fresnelF1Metres(4.1, 5);
  assert.ok(f1_L12 !== null);
  assert.ok(Math.abs(f1_L12 - 7.84) < 0.01, `L12 F1: got ${f1_L12}`);
  const c60_L12 = clearance60(f1_L12);
  assert.ok(c60_L12 !== null);
  assert.ok(Math.abs(c60_L12 - 4.71) < 0.01, `L12 clearance: got ${c60_L12}`);
});

test('fresnelF1Metres and clearance60: return null on non-positive or non-finite inputs', () => {
  assert.equal(fresnelF1Metres(0, 5), null);
  assert.equal(fresnelF1Metres(-3.2, 5), null);
  assert.equal(fresnelF1Metres(3.2, 0), null);
  assert.equal(fresnelF1Metres(3.2, -5), null);
  assert.equal(fresnelF1Metres(NaN, 5), null);
  assert.equal(fresnelF1Metres(null, 5), null);
  assert.equal(fresnelF1Metres(3.2, undefined), null);

  assert.equal(clearance60(0), null);
  assert.equal(clearance60(-1), null);
  assert.equal(clearance60(NaN), null);
  assert.equal(clearance60(null), null);
});

test('getLinkMidpoint: computes center coordinate between endpoints', () => {
  const p1 = { lat: 27.20000, lon: 80.60000 };
  const p2 = { lat: 27.22879, lon: 80.60000 };
  const mid = getLinkMidpoint(p1, p2);
  assert.ok(mid);
  assert.ok(Math.abs(mid[0] - 27.214395) < 0.0001);
  assert.equal(mid[1], 80.60000);

  assert.equal(getLinkMidpoint(null, p2), null);
  assert.equal(getLinkMidpoint(p1, { lat: NaN, lon: 80.6 }), null);
});

test('getPredictedEtaMinutes: validates and rounds predicted ETA', () => {
  assert.equal(getPredictedEtaMinutes({ predicted_eta_minutes: 42.4 }), 42);
  assert.equal(getPredictedEtaMinutes({ predicted_eta_minutes: 42.6 }), 43);
  assert.equal(getPredictedEtaMinutes({ predicted_eta_minutes: 0 }), 0);

  // Absent, null, NaN, string, negative, missing
  assert.equal(getPredictedEtaMinutes({}), null);
  assert.equal(getPredictedEtaMinutes({ predicted_eta_minutes: null }), null);
  assert.equal(getPredictedEtaMinutes({ predicted_eta_minutes: NaN }), null);
  assert.equal(getPredictedEtaMinutes({ predicted_eta_minutes: '42' }), null);
  assert.equal(getPredictedEtaMinutes({ predicted_eta_minutes: -5 }), null);
  assert.equal(getPredictedEtaMinutes(null), null);
  assert.equal(getPredictedEtaMinutes(undefined), null);
});
