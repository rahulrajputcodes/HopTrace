import test from 'node:test';
import assert from 'node:assert/strict';
import {
  STORAGE_KEY_MAP_LEGEND,
  STORAGE_KEY_MAP_VILLAGES,
  getStoredPopoverPref,
  setStoredPopoverPref,
} from './popoverPrefs.js';

test('popoverPrefs: defaults to false when storage is empty or null', () => {
  assert.equal(getStoredPopoverPref(STORAGE_KEY_MAP_LEGEND, false, null), false);
  const fakeStorage = { getItem: () => null, setItem: () => {} };
  assert.equal(getStoredPopoverPref(STORAGE_KEY_MAP_LEGEND, false, fakeStorage), false);
  assert.equal(getStoredPopoverPref(STORAGE_KEY_MAP_VILLAGES, false, fakeStorage), false);
});

test('popoverPrefs: returns true when stored value is "true"', () => {
  const fakeStorage = {
    getItem: (key) => (key === STORAGE_KEY_MAP_LEGEND ? 'true' : 'false'),
    setItem: () => {},
  };
  assert.equal(getStoredPopoverPref(STORAGE_KEY_MAP_LEGEND, false, fakeStorage), true);
  assert.equal(getStoredPopoverPref(STORAGE_KEY_MAP_VILLAGES, false, fakeStorage), false);
});

test('popoverPrefs: safely handles throwing storage', () => {
  const badStorage = {
    getItem: () => {
      throw new Error('Access denied');
    },
    setItem: () => {
      throw new Error('Quota exceeded');
    },
  };
  assert.equal(getStoredPopoverPref(STORAGE_KEY_MAP_LEGEND, false, badStorage), false);
  assert.doesNotThrow(() => setStoredPopoverPref(STORAGE_KEY_MAP_LEGEND, true, badStorage));
});

test('popoverPrefs: setStoredPopoverPref writes stringified boolean', () => {
  const store = {};
  const fakeStorage = {
    getItem: (k) => store[k] ?? null,
    setItem: (k, v) => {
      store[k] = String(v);
    },
  };
  setStoredPopoverPref(STORAGE_KEY_MAP_LEGEND, true, fakeStorage);
  assert.equal(store[STORAGE_KEY_MAP_LEGEND], 'true');
  assert.equal(getStoredPopoverPref(STORAGE_KEY_MAP_LEGEND, false, fakeStorage), true);

  setStoredPopoverPref(STORAGE_KEY_MAP_LEGEND, false, fakeStorage);
  assert.equal(store[STORAGE_KEY_MAP_LEGEND], 'false');
  assert.equal(getStoredPopoverPref(STORAGE_KEY_MAP_LEGEND, false, fakeStorage), false);
});
