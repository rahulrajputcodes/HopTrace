import test from 'node:test';
import assert from 'node:assert/strict';
import { useAuth } from '../store/authStore.js';
import { api, publicApi } from '../hooks/useApi.js';

test('authStore: exports useAuth hook matching M2 contract', () => {
  assert.equal(typeof useAuth, 'function');
  const state = useAuth.getState();

  assert.equal(state.user, 'operator');
  assert.equal(state.role, 'operator');
  assert.equal(state.isAuthenticated, true);
  assert.equal(typeof state.login, 'function');
  assert.equal(typeof state.logout, 'function');
});

test('authStore: login and logout stubs execute without throwing', async () => {
  const state = useAuth.getState();
  const res = await state.login('operator', 'anypass');
  assert.equal(res.role, 'operator');
  assert.equal(res.isAuthenticated, true);

  state.logout();
  const afterLogout = useAuth.getState();
  assert.equal(afterLogout.isAuthenticated, true);
  assert.equal(afterLogout.role, 'operator');
});

test('useApi: exports api and publicApi functions', () => {
  assert.equal(typeof api, 'function');
  assert.equal(typeof publicApi, 'function');
});
