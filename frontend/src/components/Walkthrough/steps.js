/**
 * M4 — Walkthrough step definitions (pure data, no React).
 *
 * Each step describes one panel in the evaluator walkthrough.
 * - id: unique slug
 * - title: short heading
 * - body: 1–3 sentence explanation (NO hardcoded metrics or invented values)
 * - target: optional CSS selector hint for spotlight (best-effort, not required)
 * - emoji: decorative icon
 */

export const STEPS = [
  {
    id: 'welcome',
    emoji: '🛰️',
    title: 'Welcome to HopTrace',
    body:
      'HopTrace is a real-time NOC dashboard for rural wireless mesh networks. ' +
      'It monitors connectivity across villages, detects faults, and helps operators ' +
      'notify affected subscribers — all from a single screen.',
    target: null,
  },
  {
    id: 'live-demo-mode',
    emoji: '⚡',
    title: 'Live vs Demo Mode',
    body:
      'Use the mode toggle in the top bar to switch between Live and Demo. ' +
      'In Live mode the dashboard streams real telemetry from field agents. ' +
      'Demo mode replays a pre-recorded fault scenario so you can explore every feature without a live network.',
    target: '[aria-label="Data mode"]',
  },
  {
    id: 'map-topology',
    emoji: '🗺️',
    title: 'Map & Topology View',
    body:
      'The main panel shows either a geographic map (Leaflet) or a schematic graph (ReactFlow). ' +
      'Link colours encode risk: green → low, amber → degraded, red → critical, dashed → no data. ' +
      'Click any node or link to open the detail drawer.',
    target: '[aria-label="Network visualization view"]',
  },
  {
    id: 'incident-ai',
    emoji: '🚨',
    title: 'Fault & Incident Inspection',
    body:
      'When a fault is detected, the Incident panel shows the active incident with its suspected root-cause component highlighted on the map. ' +
      'The AI Explanation card beneath it summarises the probable cause and recommended action in plain language.',
    target: null,
  },
  {
    id: 'notify-flow',
    emoji: '📲',
    title: 'Notify Affected Subscribers',
    body:
      'The Subscriber Ops panel (bottom of the dashboard) lists subscribers affected by the current incident. ' +
      'Select one or more and click Notify to send an SMS or voice alert — the system drafts the message automatically based on the incident.',
    target: null,
  },
  {
    id: 'public-status',
    emoji: '🌐',
    title: 'Public Status Page',
    body:
      'The public status page at /status shows village-level connectivity health to anyone — no login required. ' +
      'It polls the backend every 15 seconds, supports Hindi and English, and uses an honest "no data" state rather than inventing values.',
    target: null,
  },
];

/** All keys every step must have */
export const REQUIRED_STEP_KEYS = ['id', 'title', 'body', 'emoji'];
