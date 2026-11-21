import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getSubscriberVillage,
  getSubscriberAp,
  DEFAULT_AP_TO_VILLAGE,
} from './helpers.js';
import useStore from '../../store/appStore.js';

test('getSubscriberAp: resolves access_point_id from API response', () => {
  const sub = {
    id: 'SUB101',
    display_name: 'Ramesh Patel',
    access_point_id: 'AP1',
  };
  assert.equal(getSubscriberAp(sub), 'AP1');
});

test('getSubscriberAp: resolves ap_id fallback when access_point_id is missing', () => {
  const sub = {
    id: 'SUB101',
    display_name: 'Ramesh Patel',
    ap_id: 'AP2',
  };
  assert.equal(getSubscriberAp(sub), 'AP2');
});

test('getSubscriberAp: returns dash when neither access_point_id nor ap_id exists', () => {
  assert.equal(getSubscriberAp({ id: 'SUB101' }), '—');
  assert.equal(getSubscriberAp(null), '—');
  assert.equal(getSubscriberAp(undefined), '—');
});

test('getSubscriberVillage: returns explicit village if already present', () => {
  const sub = {
    id: 'SUB101',
    access_point_id: 'AP1',
    village: 'Custom Village',
  };
  assert.equal(getSubscriberVillage(sub), 'Custom Village');
});

test('getSubscriberVillage: maps canonical APs to their rural villages', () => {
  assert.equal(getSubscriberVillage({ access_point_id: 'AP1' }), 'Rampur');
  assert.equal(getSubscriberVillage({ access_point_id: 'AP2' }), 'Rampur');
  assert.equal(getSubscriberVillage({ access_point_id: 'AP3' }), 'Bhatpur');
  assert.equal(getSubscriberVillage({ access_point_id: 'AP4' }), 'Bhatpur');
  assert.equal(getSubscriberVillage({ access_point_id: 'AP5' }), 'Daulatpur');
  assert.equal(getSubscriberVillage({ access_point_id: 'AP6' }), 'Daulatpur');
});

test('getSubscriberVillage: works with ap_id field name', () => {
  assert.equal(getSubscriberVillage({ ap_id: 'AP1' }), 'Rampur');
  assert.equal(getSubscriberVillage({ ap_id: 'AP3' }), 'Bhatpur');
  assert.equal(getSubscriberVillage({ ap_id: 'AP5' }), 'Daulatpur');
});

test('getSubscriberVillage: resolves dynamically from villages list', () => {
  const dynamicVillages = [
    { village_id: 'kalyanpur', name: 'Kalyanpur', access_points: ['AP99'] },
    { village_id: 'shivpur', access_points: ['AP100'] },
  ];

  assert.equal(
    getSubscriberVillage({ access_point_id: 'AP99' }, dynamicVillages),
    'Kalyanpur'
  );
  // Uses capitalized village_id if name is not present
  assert.equal(
    getSubscriberVillage({ access_point_id: 'AP100' }, dynamicVillages),
    'Shivpur'
  );
});

test('getSubscriberVillage: returns dash for unknown AP or missing subscriber', () => {
  assert.equal(getSubscriberVillage({ access_point_id: 'AP_UNKNOWN' }), '—');
  assert.equal(getSubscriberVillage({}), '—');
  assert.equal(getSubscriberVillage(null), '—');
  assert.equal(getSubscriberVillage(undefined), '—');
});

test('DEFAULT_AP_TO_VILLAGE: covers AP1 through AP6', () => {
  assert.deepEqual(DEFAULT_AP_TO_VILLAGE, {
    AP1: 'Rampur',
    AP2: 'Rampur',
    AP3: 'Bhatpur',
    AP4: 'Bhatpur',
    AP5: 'Daulatpur',
    AP6: 'Daulatpur',
  });
});

test('appStore setAllSubscribers: enriches API response with village and normalized AP', () => {
  const rawApiSubscribers = [
    {
      id: 'SUB101',
      display_name: 'Ramesh Patel',
      plan: 'Basic',
      access_point_id: 'AP1',
      status: 'active',
      payment_status: 'paid',
      due_date: '2026-11-15',
    },
    {
      id: 'SUB301',
      display_name: 'Bhatpur Mandi',
      plan: 'Enterprise',
      access_point_id: 'AP3',
      status: 'active',
      payment_status: 'due',
      due_date: '2026-11-01',
    },
    {
      id: 'SUB501',
      display_name: 'Daulatpur Haat',
      plan: 'Community',
      access_point_id: 'AP5',
      status: 'active',
      payment_status: 'paid',
      due_date: '2026-11-15',
    },
  ];

  useStore.getState().setAllSubscribers(rawApiSubscribers);
  const stored = useStore.getState().allSubscribers;

  assert.equal(stored.length, 3);
  assert.equal(stored[0].access_point_id, 'AP1');
  assert.equal(stored[0].ap_id, 'AP1');
  assert.equal(stored[0].village, 'Rampur');

  assert.equal(stored[1].access_point_id, 'AP3');
  assert.equal(stored[1].ap_id, 'AP3');
  assert.equal(stored[1].village, 'Bhatpur');

  assert.equal(stored[2].access_point_id, 'AP5');
  assert.equal(stored[2].ap_id, 'AP5');
  assert.equal(stored[2].village, 'Daulatpur');
});

test('appStore alert controls: alertArmed, voiceMuted, alertOpen defaults and setters', () => {
  const state = useStore.getState();
  assert.equal(state.alertArmed, true);
  assert.equal(state.voiceMuted, false);
  assert.equal(state.alertOpen, false);

  state.setAlertArmed(false);
  assert.equal(useStore.getState().alertArmed, false);
  state.setAlertArmed(true);
  assert.equal(useStore.getState().alertArmed, true);

  state.setVoiceMuted(true);
  assert.equal(useStore.getState().voiceMuted, true);
  state.setVoiceMuted(false);
  assert.equal(useStore.getState().voiceMuted, false);

  state.setAlertOpen(true);
  assert.equal(useStore.getState().alertOpen, true);
  state.setAlertOpen(false);
  assert.equal(useStore.getState().alertOpen, false);
});
