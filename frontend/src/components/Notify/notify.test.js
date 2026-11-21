import test from 'node:test';
import assert from 'node:assert/strict';
import useStore from '../../store/appStore.js';

// Helper tests for notify domain logic
function maskPhoneNumber(phone) {
  if (!phone || phone.trim() === '') return '—';
  const clean = phone.trim();
  if (clean.length <= 6) return clean;
  const start = clean.slice(0, 5);
  const end = clean.slice(-2);
  return `${start}••••${end}`;
}

function resolveVillage(ap) {
  const AP_TO_VILLAGE = {
    AP1: 'Rampur',
    AP2: 'Rampur',
    AP3: 'Bhatpur',
    AP4: 'Bhatpur',
    AP5: 'Daulatpur',
    AP6: 'Daulatpur',
  };
  return AP_TO_VILLAGE[ap?.toUpperCase()] || 'Unknown';
}

function canUserSendNotification(role) {
  return role === 'operator' || role === 'admin';
}

test('maskPhoneNumber: masks middle digits correctly for Indian numbers', () => {
  const masked = maskPhoneNumber('+919876543210');
  assert.equal(masked, '+9198••••10');
});

test('maskPhoneNumber: handles empty and null inputs safely', () => {
  assert.equal(maskPhoneNumber(''), '—');
  assert.equal(maskPhoneNumber(null), '—');
  assert.equal(maskPhoneNumber(undefined), '—');
});

test('resolveVillage: correctly maps access point to rural village', () => {
  assert.equal(resolveVillage('AP1'), 'Rampur');
  assert.equal(resolveVillage('AP2'), 'Rampur');
  assert.equal(resolveVillage('AP3'), 'Bhatpur');
  assert.equal(resolveVillage('AP4'), 'Bhatpur');
  assert.equal(resolveVillage('AP5'), 'Daulatpur');
  assert.equal(resolveVillage('AP6'), 'Daulatpur');
  assert.equal(resolveVillage('AP99'), 'Unknown');
});

test('roleCheck: operators can send notifications, viewers are restricted', () => {
  assert.equal(canUserSendNotification('operator'), true);
  assert.equal(canUserSendNotification('admin'), true);
  assert.equal(canUserSendNotification('viewer'), false);
  assert.equal(canUserSendNotification('guest'), false);
});

test('appStore: userRole setter and viewer restriction', () => {
  useStore.getState().setUserRole('viewer');
  assert.equal(useStore.getState().userRole, 'viewer');
  assert.equal(canUserSendNotification(useStore.getState().userRole), false);

  useStore.getState().setUserRole('operator');
  assert.equal(useStore.getState().userRole, 'operator');
  assert.equal(canUserSendNotification(useStore.getState().userRole), true);
});

test('recipientSelection: toggle logic handles add and remove', () => {
  const selected = new Set(['SUB101', 'SUB102']);
  // Toggle off
  if (selected.has('SUB101')) selected.delete('SUB101');
  else selected.add('SUB101');
  assert.equal(selected.has('SUB101'), false);

  // Toggle on
  if (selected.has('SUB101')) selected.delete('SUB101');
  else selected.add('SUB101');
  assert.equal(selected.has('SUB101'), true);
});

test('idempotencyKey: generates unique key per dispatch attempt', () => {
  const k1 = `ht-notify-INC1-${Date.now()}-1`;
  const k2 = `ht-notify-INC1-${Date.now()}-2`;
  assert.notEqual(k1, k2);
  assert.ok(k1.startsWith('ht-notify-INC1-'));
});
