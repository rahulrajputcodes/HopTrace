/**
 * Formats elapsed duration since incident detection.
 *
 * @param {string|null} createdIso
 * @param {number} [nowMs=Date.now()]
 * @returns {string}
 */
export function formatElapsed(createdIso, nowMs = Date.now()) {
  if (!createdIso) return '0s';
  const created = new Date(createdIso).getTime();
  if (isNaN(created)) return '0s';
  const diffSec = Math.max(0, Math.floor((nowMs - created) / 1000));
  if (diffSec < 60) return `${diffSec}s`;
  const m = Math.floor(diffSec / 60);
  const s = diffSec % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h}h ${remM}m`;
}

/**
 * Resolves short actionable next step line for operator diagnosis.
 *
 * @param {object|null} activeIncident
 * @param {object|null} aiReport
 * @returns {string|null}
 */
export function getNextStep(activeIncident, aiReport) {
  if (!activeIncident) return null;

  // 1. AI explanation operator steps if already generated
  if (aiReport?.field_operator_steps) {
    const steps = Array.isArray(aiReport.field_operator_steps)
      ? aiReport.field_operator_steps
      : [aiReport.field_operator_steps];
    if (steps.length > 0 && typeof steps[0] === 'string' && steps[0].trim()) {
      return steps[0].replace(/^Step\s*1\s*:\s*/i, '').trim();
    }
  }

  // 2. Incident-level explicit next step / recommendation
  if (activeIncident.next_step) return activeIncident.next_step;
  if (activeIncident.recommendation) return activeIncident.recommendation;
  if (activeIncident.recommended_action) return activeIncident.recommended_action;

  // 3. Heuristic based on fault class or suspected component
  const faultClass = activeIncident.fault_class || activeIncident.fault_type;
  if (faultClass) {
    const norm = String(faultClass).toLowerCase();
    if (norm.includes('upstream')) return 'Verify optical backhaul and upstream provider gateway';
    if (norm.includes('ptp') || norm.includes('wireless') || norm.includes('degrade')) {
      const comp = activeIncident.suspected_component_id || 'link';
      return `Check the 5 GHz bridge on ${comp} alignment`;
    }
    if (norm.includes('down') || norm.includes('fiber')) {
      const comp = activeIncident.suspected_component_id || 'link';
      return `Inspect physical fiber patch and SFP optical power on ${comp}`;
    }
  }

  const comp = activeIncident.suspected_component_id;
  const summary = (activeIncident.summary || '').toLowerCase();
  if (comp === 'L3' || summary.includes('l3')) {
    return 'Check the 5 GHz bridge on L3 alignment';
  }
  if (comp === 'GW1' || summary.includes('upstream') || summary.includes('gateway')) {
    return 'Verify optical backhaul link and gateway router power';
  }

  return null;
}

/**
 * Formats a currency amount in Indian Rupee format.
 *
 * @param {number|null|undefined} val
 * @returns {string|null}
 */
export function formatRevenue(val) {
  if (val === null || val === undefined) return null;
  const num = Number(val);
  if (isNaN(num)) return null;
  return `₹${num.toLocaleString('en-IN')}`;
}
