import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getStoredLayers,
  setStoredLayers,
  DEFAULT_MAP_LAYERS,
  LABEL_MIN_ZOOM,
} from './layerPrefs.js';

test('LABEL_MIN_ZOOM: equals 16 per Stage 3 user specification', () => {
  assert.equal(LABEL_MIN_ZOOM, 16);
});

test('getStoredLayers: returns defaults when storage is empty or null', () => {
  assert.deepEqual(getStoredLayers(null), DEFAULT_MAP_LAYERS);

  const mockStorage = {
    getItem: () => null,
    setItem: () => {},
  };
  assert.deepEqual(getStoredLayers(mockStorage), DEFAULT_MAP_LAYERS);
});

test('getStoredLayers: retrieves stored preferences and preserves boolean types', () => {
  const mockStorage = {
    getItem: () => JSON.stringify({ coverage: false, links: true, labels: false }),
    setItem: () => {},
  };
  assert.deepEqual(getStoredLayers(mockStorage), {
    coverage: false,
    links: true,
    labels: false,
  });
});

test('getStoredLayers: safely handles corrupted JSON or throwing storage', () => {
  const throwingStorage = {
    getItem: () => {
      throw new Error('Access denied');
    },
    setItem: () => {},
  };
  assert.deepEqual(getStoredLayers(throwingStorage), DEFAULT_MAP_LAYERS);

  const corruptStorage = {
    getItem: () => 'invalid-json{',
    setItem: () => {},
  };
  assert.deepEqual(getStoredLayers(corruptStorage), DEFAULT_MAP_LAYERS);
});

test('setStoredLayers: writes serialized JSON to storage safely', () => {
  let savedKey = null;
  let savedVal = null;
  const mockStorage = {
    getItem: () => null,
    setItem: (k, v) => {
      savedKey = k;
      savedVal = v;
    },
  };

  const payload = { coverage: false, links: true, labels: false };
  setStoredLayers(payload, mockStorage);
  assert.equal(savedKey, 'hoptrace.mapLayers');
  assert.equal(savedVal, JSON.stringify(payload));
});
