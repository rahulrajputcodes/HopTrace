import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getViewPref,
  setViewPref,
  STORAGE_KEY,
  DEFAULT_VIEW,
} from './viewPref.js';

function createMockStorage(initial = {}) {
  const store = { ...initial };
  return {
    getItem(key) {
      return store[key] ?? null;
    },
    setItem(key, val) {
      store[key] = String(val);
    },
    removeItem(key) {
      delete store[key];
    },
    clear() {
      for (const k of Object.keys(store)) delete store[k];
    },
  };
}

test('getViewPref: returns default view when storage is empty or null', () => {
  assert.equal(getViewPref(createMockStorage()), DEFAULT_VIEW);
  assert.equal(getViewPref(null), DEFAULT_VIEW);
});

test('getViewPref: returns valid view from storage', () => {
  const storage = createMockStorage({ [STORAGE_KEY]: 'graph' });
  assert.equal(getViewPref(storage), 'graph');

  const storageMap = createMockStorage({ [STORAGE_KEY]: 'map' });
  assert.equal(getViewPref(storageMap), 'map');
});

test('getViewPref: rejects unknown views and falls back to default', () => {
  const storage = createMockStorage({ [STORAGE_KEY]: 'satellite' });
  assert.equal(getViewPref(storage), DEFAULT_VIEW);
});

test('getViewPref: safely recovers when storage.getItem throws', () => {
  const throwingStorage = {
    getItem() {
      throw new Error('Access denied');
    },
  };
  assert.equal(getViewPref(throwingStorage), DEFAULT_VIEW);
});

test('setViewPref: saves valid view and ignores invalid view', () => {
  const storage = createMockStorage();
  setViewPref('graph', storage);
  assert.equal(storage.getItem(STORAGE_KEY), 'graph');

  setViewPref('invalid', storage);
  assert.equal(storage.getItem(STORAGE_KEY), 'graph');

  setViewPref('map', storage);
  assert.equal(storage.getItem(STORAGE_KEY), 'map');
});

test('setViewPref: safely handles throwing storage.setItem', () => {
  const throwingStorage = {
    setItem() {
      throw new Error('Quota exceeded');
    },
  };
  assert.doesNotThrow(() => {
    setViewPref('graph', throwingStorage);
  });
});
