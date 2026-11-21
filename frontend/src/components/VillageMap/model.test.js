import test from 'node:test';
import assert from 'node:assert/strict';
import { buildMapModel } from './model.js';

const mockTopology = {
  nodes: [
    { id: 'GW1', type: 'gateway', village: 'block_hq', lat: 27.20000, lon: 80.57877, coverage_radius_m: null },
    { id: 'R1', type: 'router', village: 'rampur', lat: 27.20000, lon: 80.60000, coverage_radius_m: null },
    { id: 'WB1', type: 'wireless_bridge', village: 'rampur', lat: 27.20045, lon: 80.60000, coverage_radius_m: null },
    { id: 'WB2', type: 'wireless_bridge', village: 'rampur', lat: 27.22879, lon: 80.60562, coverage_radius_m: null },
    { id: 'AP1', type: 'access_point', village: 'rampur', lat: 27.22906, lon: 80.60602, coverage_radius_m: 300 },
    { id: 'AP2', type: 'access_point', village: 'rampur', lat: 27.20000, lon: 80.59949, coverage_radius_m: 250 },
    { id: 'INVALID_NODE', type: 'router', village: 'rampur', lat: null, lon: 80.6 }, // missing coords
  ],
  links: [
    { id: 'L1', source: 'GW1', target: 'R1', distance_km: 2.1, medium: 'fiber' },
    { id: 'L2', source: 'R1', target: 'WB1', distance_km: 0.05, medium: 'cat6' },
    { id: 'L3', source: 'WB1', target: 'WB2', distance_km: 3.2, medium: 'wireless_60ghz' },
    { id: 'L4', source: 'WB2', target: 'AP1', distance_km: 0.05, medium: 'cat6' },
    { id: 'L5', source: 'R1', target: 'AP2', distance_km: 0.05, medium: 'cat6' },
    { id: 'BROKEN_LINK', source: 'R1', target: 'INVALID_NODE' }, // target invalid
  ],
};

const mockVillages = [
  { village_id: 'rampur', name: 'Rampur', status: 'healthy' },
  { village_id: 'bhatpur', name: 'Bhatpur', status: 'degraded' },
];

test('buildMapModel: handles null/undefined arguments gracefully', () => {
  const result = buildMapModel();
  assert.deepEqual(result.nodes, []);
  assert.deepEqual(result.links, []);
  assert.deepEqual(result.villages, []);
  assert.equal(result.blastApIds.size, 0);
  assert.equal(result.suspected, null);
});

test('buildMapModel: filters out nodes with invalid coordinates and links with missing endpoints', () => {
  const model = buildMapModel({
    topology: mockTopology,
    villages: mockVillages,
  });

  // INVALID_NODE is skipped
  assert.equal(model.nodes.length, 6);
  assert.ok(!model.nodes.some((n) => n.id === 'INVALID_NODE'));

  // BROKEN_LINK is skipped because target is skipped
  assert.equal(model.links.length, 5);
  assert.ok(!model.links.some((l) => l.id === 'BROKEN_LINK'));
});

test('buildMapModel: healthy baseline scenario', () => {
  const model = buildMapModel({
    topology: mockTopology,
    villages: mockVillages,
    liveMeasurements: [
      { link_id: 'L1', latency_ms: 12, packet_loss_pct: 0, connectivity_ok: true, risk_score: 5 },
    ],
  });

  assert.equal(model.suspected, null);
  assert.equal(model.blastApIds.size, 0);
  const l1 = model.links.find((l) => l.id === 'L1');
  assert.equal(l1.risk_score, 5);
  assert.equal(l1.isDown, false);
  assert.equal(l1.isSuspected, false);
});

test('buildMapModel: L3 degraded scenario with suspected link and blast APs', () => {
  const activeIncident = {
    id: 'inc-101',
    suspected_component_id: 'L3',
    suspected_component_type: 'link',
  };
  const affectedSubscribers = [
    { id: 'SUB1', access_point_id: 'AP1' },
    { id: 'SUB2', access_point_id: 'AP1' }, // duplicate AP
    { id: 'SUB3', access_point_id: 'AP2' },
    { id: 'SUB4', access_point_id: 'UNKNOWN_AP' }, // unknown AP
    { id: 'SUB5', access_point_id: 'GW1' }, // not an AP (gateway)
  ];
  const riskSnapshot = {
    L3: { risk_score: 85 },
  };
  const liveMeasurements = [
    { link_id: 'L3', latency_ms: 150, packet_loss_pct: 25, connectivity_ok: false, risk_score: 80 },
  ];

  const model = buildMapModel({
    topology: mockTopology,
    villages: mockVillages,
    riskSnapshot,
    liveMeasurements,
    activeIncident,
    affectedSubscribers,
  });

  // Suspected link
  assert.deepEqual(model.suspected, { id: 'L3', type: 'link' });
  const l3 = model.links.find((l) => l.id === 'L3');
  assert.ok(l3);
  assert.equal(l3.isSuspected, true);
  assert.equal(l3.risk_score, 85); // snapshot precedence
  assert.equal(l3.isDown, true); // connectivity_ok === false

  // Blast radius APs: only AP1 and AP2 (duplicates deduped, unknown/non-AP ignored)
  assert.equal(model.blastApIds.size, 2);
  assert.ok(model.blastApIds.has('AP1'));
  assert.ok(model.blastApIds.has('AP2'));
  assert.ok(!model.blastApIds.has('GW1'));
  assert.ok(!model.blastApIds.has('UNKNOWN_AP'));

  const ap1Node = model.nodes.find((n) => n.id === 'AP1');
  assert.equal(ap1Node.isBlastAp, true);
  const gw1Node = model.nodes.find((n) => n.id === 'GW1');
  assert.equal(gw1Node.isBlastAp, false);
});

test('buildMapModel: clearing incident resets all suspected and blast radius flags immediately', () => {
  // When activeIncident: null and affectedSubscribers: []
  const model = buildMapModel({
    topology: mockTopology,
    villages: mockVillages,
    activeIncident: null,
    affectedSubscribers: [],
  });

  assert.equal(model.suspected, null);
  assert.equal(model.blastApIds.size, 0);
  for (const n of model.nodes) {
    assert.equal(n.isSuspected, false);
    assert.equal(n.isBlastAp, false);
  }
  for (const l of model.links) {
    assert.equal(l.isSuspected, false);
  }
});

test('buildMapModel: infers suspected type if suspected_component_type is omitted', () => {
  const modelWithNode = buildMapModel({
    topology: mockTopology,
    activeIncident: { suspected_component_id: 'R1' }, // node without type
  });
  assert.deepEqual(modelWithNode.suspected, { id: 'R1', type: 'node' });

  const modelWithLink = buildMapModel({
    topology: mockTopology,
    activeIncident: { suspected_component_id: 'L1' }, // link without type
  });
  assert.deepEqual(modelWithLink.suspected, { id: 'L1', type: 'link' });
});
