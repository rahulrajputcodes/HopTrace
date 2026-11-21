/**
 * M4 — Walkthrough pure-function tests
 *
 * Uses node:test + node:assert/strict (no JSDOM, no React renderer).
 * Tests cover only steps.js — pure data, fully importable in Node.
 *
 * Run from frontend/: node --test src/components/Walkthrough/Walkthrough.test.js
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { STEPS, REQUIRED_STEP_KEYS } from './steps.js';

describe('STEPS array', () => {
  it('is an array', () => {
    assert.ok(Array.isArray(STEPS), 'STEPS must be an array');
  });

  it('has at least 5 steps', () => {
    assert.ok(STEPS.length >= 5, `expected >= 5 steps, got ${STEPS.length}`);
  });

  it('every step has all required keys with non-empty string values', () => {
    for (const step of STEPS) {
      for (const key of REQUIRED_STEP_KEYS) {
        assert.ok(
          key in step,
          `step "${step.id ?? '?'}" missing key: "${key}"`
        );
        assert.ok(
          typeof step[key] === 'string' && step[key].trim().length > 0,
          `step "${step.id ?? '?'}" key "${key}" must be a non-empty string`
        );
      }
    }
  });

  it('step ids are unique', () => {
    const ids = STEPS.map(s => s.id);
    const unique = new Set(ids);
    assert.equal(
      unique.size,
      ids.length,
      `duplicate step ids found: ${ids.filter((id, i) => ids.indexOf(id) !== i).join(', ')}`
    );
  });

  it('no step body contains hardcoded metric values (fake data check)', () => {
    // Reject patterns like "12.7V", "99.9%", "150ms" that look like invented metrics
    const fakeMetricPattern = /\b\d+\.\d+\s*(V|ms|Mbps|kbps|%)\b/i;
    for (const step of STEPS) {
      assert.ok(
        !fakeMetricPattern.test(step.body),
        `step "${step.id}" body contains a likely hardcoded metric value: "${step.body.match(fakeMetricPattern)?.[0]}"`
      );
    }
  });

  it('every step title is concise (≤ 60 characters)', () => {
    for (const step of STEPS) {
      assert.ok(
        step.title.length <= 60,
        `step "${step.id}" title too long (${step.title.length} chars): "${step.title}"`
      );
    }
  });

  it('the "welcome" step exists as the first step', () => {
    assert.equal(STEPS[0].id, 'welcome', 'first step must have id "welcome"');
  });

  it('the "public-status" step exists', () => {
    const found = STEPS.some(s => s.id === 'public-status');
    assert.ok(found, 'a step with id "public-status" must exist');
  });
});
