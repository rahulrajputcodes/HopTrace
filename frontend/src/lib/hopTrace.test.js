import test from 'node:test';
import assert from 'node:assert/strict';
import { buildFailurePath } from './hopTrace.js';

const mockTopologyLinks = [
  { id: 'L1', source: 'GW1', target: 'R1' },
  { id: 'L6', source: 'R1', target: 'WB3' },
  { id: 'L7', source: 'WB3', target: 'WB4' },
  { id: 'L8', source: 'WB4', target: 'R2' },
  { id: 'L9', source: 'R2', target: 'AP3' },
];

test('buildFailurePath: handles empty or null input gracefully', () => {
  assert.deepEqual(buildFailurePath(null), { path: [], behind: [] });
  assert.deepEqual(buildFailurePath([]), { path: [], behind: [] });
  assert.deepEqual(buildFailurePath(undefined, mockTopologyLinks), { path: [], behind: [] });
});

test('buildFailurePath: no failure and no degradation returns empty path and behind', () => {
  const trace = [
    { node_id: 'GW1', link_id: null, depth: 0, status: 'ok', reachable: true },
    { node_id: 'R1', link_id: 'L1', depth: 1, status: 'ok', reachable: true },
    { node_id: 'WB3', link_id: 'L6', depth: 2, status: 'ok', reachable: true },
  ];
  const res = buildFailurePath(trace, mockTopologyLinks);
  assert.deepEqual(res, { path: [], behind: [] });
});

test('buildFailurePath: single failure mid-tree (WB3 fails)', () => {
  const trace = [
    { node_id: 'GW1', link_id: null, depth: 0, status: 'ok', reachable: true },
    { node_id: 'R1', link_id: 'L1', depth: 1, status: 'ok', reachable: true },
    { node_id: 'WB3', link_id: 'L6', depth: 2, status: 'failed', reachable: false, packet_loss_pct: 100 },
    { node_id: 'WB4', link_id: 'L7', depth: 3, status: 'behind_failure', reachable: false },
    { node_id: 'R2', link_id: 'L8', depth: 4, status: 'behind_failure', reachable: false },
  ];

  const { path, behind } = buildFailurePath(trace, mockTopologyLinks);

  // Path: GW1 -> R1 -> WB3
  assert.equal(path.length, 3);
  assert.equal(path[0].node_id, 'GW1');
  assert.equal(path[1].node_id, 'R1');
  assert.equal(path[2].node_id, 'WB3');
  assert.equal(path[2].status, 'failed');

  // Behind: WB4, R2
  assert.deepEqual(behind, ['WB4', 'R2']);
});

test('buildFailurePath: root-link failure (R1 fails directly off GW1)', () => {
  const trace = [
    { node_id: 'GW1', link_id: null, depth: 0, status: 'ok', reachable: true },
    { node_id: 'R1', link_id: 'L1', depth: 1, status: 'failed', reachable: false },
    { node_id: 'WB1', link_id: 'L2', depth: 2, status: 'behind_failure', reachable: false },
    { node_id: 'WB3', link_id: 'L6', depth: 2, status: 'behind_failure', reachable: false },
  ];

  const { path, behind } = buildFailurePath(trace, mockTopologyLinks);

  // Path: GW1 -> R1
  assert.equal(path.length, 2);
  assert.equal(path[0].node_id, 'GW1');
  assert.equal(path[1].node_id, 'R1');
  assert.equal(path[1].status, 'failed');

  // Behind: WB1, WB3
  assert.deepEqual(behind, ['WB1', 'WB3']);
});

test('buildFailurePath: degraded-only path isolates worst degraded hop', () => {
  const trace = [
    { node_id: 'GW1', link_id: null, depth: 0, status: 'ok', reachable: true, packet_loss_pct: 0 },
    { node_id: 'R1', link_id: 'L1', depth: 1, status: 'degraded', reachable: true, packet_loss_pct: 5 },
    { node_id: 'WB3', link_id: 'L6', depth: 2, status: 'degraded', reachable: true, packet_loss_pct: 45, latency_ms: 180 },
  ];

  const { path, behind } = buildFailurePath(trace, mockTopologyLinks);

  // Worst degraded hop is WB3 (45% loss)
  assert.equal(path.length, 3);
  assert.equal(path[2].node_id, 'WB3');
  assert.equal(path[2].status, 'degraded');
  assert.deepEqual(behind, []);
});
