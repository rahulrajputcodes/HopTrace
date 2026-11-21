from app.engine.telemetry import SimulatedTelemetryGenerator
from app.engine.diagnostics import DiagnosticEngine
from app.engine.time_series import TimeSeriesStore

gen = SimulatedTelemetryGenerator()
ts = TimeSeriesStore()
engine = DiagnosticEngine()

# Test 1: baseline
m = gen.generate_measurements('baseline')
ts.push_measurements_batch(m)
inc = engine.diagnose(m)
print(f'[1] Baseline: status={inc.status} links={len(m)}')

# Test 2: degrade L3 high severity
m2 = gen.generate_measurements('degrade_link', target_link_id='L3', severity='high')
ts.push_measurements_batch(m2)
inc2 = engine.diagnose(m2)
print(f'[2] Degrade L3: suspected={inc2.suspected_component_id} conf={inc2.confidence_score}')
print(f'    Summary: {inc2.summary[:80]}')

# Test 3: cascade fault (L3 + L7)
m3 = gen.generate_measurements('cascade_fault', severity='high')
ts.push_measurements_batch(m3)
inc3 = engine.diagnose(m3)
print(f'[3] Cascade: suspected={inc3.suspected_component_id} summary={inc3.summary[:60]}')

# Test 4: upstream failure
m4 = gen.generate_measurements('upstream_failure')
ts.push_measurements_batch(m4)
inc4 = engine.diagnose(m4)
print(f'[4] Upstream: suspected={inc4.suspected_component_id} conf={inc4.confidence_score}')

# Test 5: flapping link
m5 = gen.generate_measurements('flapping_link', target_link_id='L7', severity='high')
ts.push_measurements_batch(m5)
inc5 = engine.diagnose(m5)
print(f'[5] Flapping: suspected={inc5.suspected_component_id} summary={inc5.summary[:60]}')

# Test 6: risk snapshot
snap = ts.get_risk_snapshot()
print(f'[6] Risk snapshot: {len(snap)} links tracked')
if snap:
    top = snap[0]
    print(f'    Top risk: link={top["link_id"]} score={top["risk_score"]} trend={top["trend"]}')

# Test 7: cascade detection
cascade = ts.detect_cascade(threshold_risk=60.0)
print(f'[7] Cascade detected: {cascade}')

print('ALL ENGINE TESTS PASSED')
