import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getNodeIconConfig,
  getSuspectedRingConfig,
  createNodeIcon,
  createSuspectedRingIcon,
  getPredictionBadgeConfig,
  createPredictionBadgeIcon,
  NODE_Z_INDEX,
} from './icons.js';

test('getNodeIconConfig: distinct shapes, sizes, and colors per node type', () => {
  const gw = getNodeIconConfig({ id: 'GW1', type: 'gateway' });
  assert.deepEqual(gw.iconSize, [30, 30]);
  assert.equal(gw.zIndexOffset, NODE_Z_INDEX.gateway);
  assert.match(gw.html, /border-radius:\s*6px/);
  assert.match(gw.html, /#8b5cf6/);

  const router = getNodeIconConfig({ id: 'R1', type: 'router' });
  assert.deepEqual(router.iconSize, [26, 26]);
  assert.equal(router.zIndexOffset, NODE_Z_INDEX.router);
  assert.match(router.html, /border-radius:\s*9999px/);
  assert.match(router.html, /#3b82f6/);

  const bridge = getNodeIconConfig({ id: 'B1', type: 'wireless_bridge' });
  assert.deepEqual(bridge.iconSize, [28, 28]);
  assert.equal(bridge.zIndexOffset, NODE_Z_INDEX.wireless_bridge);
  assert.match(bridge.html, /transform:\s*rotate\(45deg\)/);
  assert.match(bridge.html, /#f59e0b/);

  const ap = getNodeIconConfig({ id: 'AP1', type: 'access_point' });
  assert.deepEqual(ap.iconSize, [22, 22]);
  assert.equal(ap.zIndexOffset, NODE_Z_INDEX.access_point);
  assert.match(ap.html, /#10b981/);
});

test('getNodeIconConfig: handles suspected state with highest z-index priority', () => {
  const normalNode = getNodeIconConfig({ id: 'R1', type: 'router', isSuspected: false });
  assert.equal(normalNode.zIndexOffset, 300);

  const suspectedNode = getNodeIconConfig({ id: 'R1', type: 'router', isSuspected: true });
  assert.equal(suspectedNode.zIndexOffset, 1000);
});

test('getNodeIconConfig: renders blast radius badge when isBlastAp is true', () => {
  const normalAp = getNodeIconConfig({ id: 'AP1', type: 'access_point', isBlastAp: false });
  assert.equal(normalAp.html.includes('hoptrace-blast-badge'), false);

  const blastAp = getNodeIconConfig({ id: 'AP1', type: 'access_point', isBlastAp: true });
  assert.equal(blastAp.html.includes('hoptrace-blast-badge'), true);
  assert.match(blastAp.html, /aria-label="Blast radius impact"/);
});

test('getSuspectedRingConfig: produces matching ring dimensions and anchor', () => {
  const ring = getSuspectedRingConfig();
  assert.deepEqual(ring.iconSize, [44, 44]);
  assert.deepEqual(ring.iconAnchor, [22, 22]);
  assert.match(ring.html, /hoptrace-suspected-ring/);
});

test('createNodeIcon and createSuspectedRingIcon: delegates to Leaflet divIcon when available', () => {
  const mockLeaflet = {
    divIcon: (opts) => ({ _leafletIcon: true, opts }),
  };

  const icon = createNodeIcon({ id: 'R1', type: 'router' }, mockLeaflet);
  assert.equal(icon._leafletIcon, true);
  assert.deepEqual(icon.opts.iconSize, [26, 26]);

  const ringIcon = createSuspectedRingIcon(mockLeaflet);
  assert.equal(ringIcon._leafletIcon, true);
  assert.deepEqual(ringIcon.opts.iconSize, [44, 44]);
});

test('getPredictionBadgeConfig and createPredictionBadgeIcon: builds amber badge with rounded minutes and simulated label', () => {
  const config = getPredictionBadgeConfig(45.4);
  assert.match(config.html, /~45 min/);
  assert.match(config.html, /aria-label="Predicted ETA about 45 minutes \(simulated\)"/);
  assert.match(config.html, /pointer-events:\s*none/);
  assert.match(config.html, /#f59e0b/);

  const mockLeaflet = {
    divIcon: (opts) => ({ _isIcon: true, opts }),
  };
  const icon = createPredictionBadgeIcon(30, mockLeaflet);
  assert.equal(icon._isIcon, true);
  assert.match(icon.opts.html, /~30 min/);
});
