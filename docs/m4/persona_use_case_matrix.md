# HopTrace M4 — Persona Use Case Matrix

> [!IMPORTANT]
> **Traceability system — every claim must carry exactly one tag:**
> - `[Person: <name or role>]` — from a named team member, advisor, or stakeholder
> - `[Own Data: <what>]` — directly observable from HopTrace's implemented system
> - `[Pending Call Verification]` — a hypothesis not yet confirmed by a customer call
> - `[Source: <named source>]` — for external figures or studies
>
> **Use case steps describe only HopTrace's actually implemented behaviour.**
> Do not describe aspirational or unbuilt features as if they exist.

> [!CAUTION]
> No subscriber counts, population figures, or percentage claims without a tag.
> No invented quotes or scenario outcomes.

---

## Segment 1 — Village ISP / Cable Owner-Operator

### Persona

| Attribute | Description | Tag |
|---|---|---|
| **Role** | Owner-operator of a rural broadband network; may also be the sole field technician | [Pending Call Verification] |
| **Scale (typical)** | Serves [SOURCE REQUIRED — NO INVENTED NUMBER] households across 1–5 villages | [Pending Call Verification] |
| **Network setup** | FTTH + last-mile wireless mesh, or cable TV co-ax broadband | [Pending Call Verification] |
| **Technical literacy** | Can install routers; limited Linux/CLI experience; comfortable with Android | [Pending Call Verification] |
| **Language** | Hindi primary; may have basic English reading ability | [Pending Call Verification] |
| **Current monitoring** | WhatsApp subscriber complaints, manual site visits, ad-hoc ping | [Pending Call Verification] |
| **Core pain** | Learns about outages from angry subscribers; cannot prove uptime for billing disputes | [Pending Call Verification] |
| **Device** | Android smartphone + Windows laptop (sometimes shared) | [Pending Call Verification] |

---

### Use Case 1.1 — Primary NOC Journey: Live Fault → AI Root Cause → Subscriber Notify

**Trigger:** A link goes down during daytime peak hours; subscribers begin calling.

| Step | Actor Action | HopTrace Component | M4 Deliverable? |
|---|---|---|---|
| 1 | Opens HopTrace dashboard on laptop or phone | `App.jsx` — dashboard loads, KPI ribbon shows health | No (M1/M2) |
| 2 | Sees NetworkStatusBanner showing degraded/down status | `NetworkStatusBanner` | No (M1) |
| 3 | Switches to Map view — sees red link with pulsing ring on suspected node | `VillageMap` (map clipping fix) | **Yes — M4 fix: Daulatpur no longer cut off** |
| 4 | Clicks suspected link → drawer opens with link telemetry | `TopologyCanvas` / drawer | No (M1/M2) |
| 5 | Reads AI Explanation card — plain-language root cause in Hindi or English | `AIExplanationCard` + `/explain` | No (M3) |
| 6 | Navigates to SubscriberOps → selects affected subscribers → clicks Notify | `SubscriberOps` + `/notify` | No (M1/M2) |
| 7 | Subscribers receive SMS/voice alert in their language | Backend notification provider | No (M1/M3) |

**Success condition:** Operator identifies fault source and notifies subscribers within 5 minutes of the incident appearing on dashboard — without a phone call from a subscriber. `[Own Data: incident + notify flow implemented end-to-end]`

**Gap / open question:** Does the operator actually open the dashboard proactively, or only after subscriber complaints? `[Pending Call Verification]`

---

### Use Case 1.2 — SLA / Uptime Review for Billing Cycle or Dispute

**Trigger:** End of month; subscriber disputes billing because "internet was down for a week."

| Step | Actor Action | HopTrace Component | M4 Deliverable? |
|---|---|---|---|
| 1 | Opens SLA Dashboard section in HopTrace | `SLAView` component | **Yes — M4** |
| 2 | Selects "Last 30 days" window | `SLAView` window selector (24h / 7d / 30d) | **Yes — M4** |
| 3 | Reads per-village uptime % and downtime minutes | `SLAView` table — real data from `/topology/sla` | **Yes — M4** |
| 4 | Notes incident count and active incidents for disputing village | `SLAView` total/active incidents columns | **Yes — M4** |
| 5 | Shows subscriber the "As of [timestamp]" line as evidence | `SLAView` timestamp (from API, not invented) | **Yes — M4** |

**Success condition:** Operator can resolve billing dispute with factual uptime data in under 2 minutes, without manual log-digging. `[Own Data: SLAView renders real data from /topology/sla]`

**Gap / open question:** Do operators currently keep any uptime records at all? Would they trust HopTrace's data for billing disputes? `[Pending Call Verification]`

---

### Use Case 1.3 — Demo / Sales: Showing HopTrace to a Potential New Operator Customer

**Trigger:** Operator wants to show another ISP peer what HopTrace does.

| Step | Actor Action | HopTrace Component | M4 Deliverable? |
|---|---|---|---|
| 1 | Runs Demo mode (pre-recorded fault scenario) | `TopBar` — Live / Demo toggle | No (M1/M2) |
| 2 | Peer watches fault appear, risk heatmap colour shift | Map / Graph view | No (M1/M2) |
| 3 | Opens Walkthrough for first-time evaluator guidance | `Walkthrough` modal (6 steps) | **Yes — M4** |
| 4 | Walkthrough explains live/demo, map, incident, notify, public status page | `Walkthrough/steps.js` | **Yes — M4** |

**Success condition:** Peer understands core value in under 3 minutes without needing a guided human demo. `[Own Data: Walkthrough component implemented]`

---

## Segment 2 — Households & Community Institutions

*(Health centre, school, panchayat centre, local shops)*

### Persona

| Attribute | Description | Tag |
|---|---|---|
| **Role** | End user of the village network; not the operator; may be a teacher, ANM nurse, shopkeeper, or panchayat clerk | [Pending Call Verification] |
| **Technical literacy** | Smartphone user; not expected to log in to any tool or understand network terminology | [Pending Call Verification] |
| **Language** | Hindi primary in most rural UP/MP/Rajasthan contexts; English as secondary | [Pending Call Verification] |
| **Device** | Low-cost Android smartphone (4G); no laptop assumed | [Pending Call Verification] |
| **Core need** | Know whether internet is working in the village right now — without calling the operator | [Pending Call Verification] |
| **Accessibility need** | Hindi text at minimum; voice/audio for low-literacy users | [Pending Call Verification] |

---

### Use Case 2.1 — Check Village Connectivity Without Login (Primary Journey)

**Trigger:** Internet is slow or absent; user wants to know if it's their device or the whole village.

| Step | Actor Action | HopTrace Component | M4 Deliverable? |
|---|---|---|---|
| 1 | Opens village status URL (shared by operator via WhatsApp / panchayat notice) | `PublicStatus` page at `/status` | **Yes — M4** |
| 2 | No login required — page loads immediately | `publicApi` (no auth headers) | **Yes — M4** |
| 3 | Sees village status card: "Operational" / "Degraded" / "Down" with colour pill | `VillageCard` with `statusConfig` | **Yes — M4** |
| 4 | Reads message in Hindi (if lang=hi) or English (default) | `PublicStatus` lang toggle + API `?lang=hi` | **Yes — M4** |
| 5 | Sees "Updated Xs ago" timestamp — knows data is fresh | `formatUpdatedAt` helper | **Yes — M4** |
| 6 | Page auto-refreshes every 15 seconds without user action | `setInterval(doFetch, 15000)` | **Yes — M4** |

**Success condition:** User determines village connectivity status in under 10 seconds, in their preferred language, with no account or app required. `[Own Data: PublicStatus component, publicApi, polling, bilingual strings]`

**Gap / open question:** Will operators actually share the `/status` URL with their subscribers? What is the right sharing mechanism (WhatsApp, QR code, panchayat board)? `[Pending Call Verification]`

---

### Use Case 2.2 — Voice Status Update for Low-Literacy / Accessibility Users

**Trigger:** A health centre ANM or low-literacy subscriber prefers audio over reading a screen.

| Step | Actor Action | HopTrace Component | M4 Deliverable? |
|---|---|---|---|
| 1 | Lands on `/status` page (same as 2.1) | `PublicStatus` | **Yes — M4** |
| 2 | Sees 🔊 "Play audio update" button on village card (if village is not `no_data`) | `VillageCard` voice button | **Yes — M4** |
| 3 | Taps button → audio plays in Hindi/English with village status | `tryPlayVoice` → POST `/api/v1/voice` | **Yes — M4 (M3 endpoint dependency)** |
| 4 | If voice endpoint unavailable (503 / network fail) → button disappears silently | `tryPlayVoice` silent failure path | **Yes — M4** |

**Success condition:** User receives status as audio without any error message shown; if voice is unavailable, text display is unaffected. `[Own Data: tryPlayVoice helper with silent fallback implemented]`

> [!NOTE]
> The `/voice` POST endpoint is an M3 dependency. M4's `tryPlayVoice` safely hides the button on failure — the page does not break without M3's endpoint.

---

### Use Case 2.3 — `no_data` State: Honest "Unavailable" for Unmonitored Villages

**Trigger:** A village has no telemetry data yet (new installation or agent offline).

| Step | Actor Action | HopTrace Component | M4 Deliverable? |
|---|---|---|---|
| 1 | Opens `/status` page | `PublicStatus` | **Yes — M4** |
| 2 | Sees slate card for the village with "No data" pill and "Data unavailable" message | `VillageCard` with `statusConfig('no_data')` | **Yes — M4** |
| 3 | No invented status is shown — no "Operational" assumed for unmonitored village | Backend `no_data` rule in `public_status.py` | **Yes — M4** |

**Success condition:** Page never displays a fake "up" status for a village with no telemetry. `[Own Data: public_status.py no_data logic, statusConfig('no_data') in helpers.js]`

---

## Segment 3 — District / Programme Administrator

*(Government block officer, NGO programme manager, state BharatNet coordinator)*

### Persona

| Attribute | Description | Tag |
|---|---|---|
| **Role** | Oversees connectivity scheme implementation across multiple villages / GPs; responsible for reporting to state/national level | [Pending Call Verification] |
| **Scale** | May be responsible for [SOURCE REQUIRED — NO INVENTED NUMBER] villages across a block or district | [Pending Call Verification] |
| **Technical literacy** | Comfortable with spreadsheets and government portals; not a network engineer | [Pending Call Verification] |
| **Language** | Hindi + English (official government reports in both) | [Pending Call Verification] |
| **Device** | Windows laptop in office; Android smartphone in field | [Pending Call Verification] |
| **Core need** | Accountability reporting: which villages were up/down and for how long; evidence for fund disbursement or penalty | [Pending Call Verification] |

---

### Use Case 3.1 — Cross-Village SLA Comparison for Scheme Reporting

**Trigger:** Monthly block-level connectivity report due to district office; administrator needs uptime data per village.

| Step | Actor Action | HopTrace Component | M4 Deliverable? |
|---|---|---|---|
| 1 | Opens HopTrace dashboard (operator grants read access — auth model TBD) | `App.jsx` | No (M2 auth) |
| 2 | Navigates to SLA Dashboard section | `SLAView` | **Yes — M4** |
| 3 | Selects "Last 30 days" window | `SLAView` window selector | **Yes — M4** |
| 4 | Views all villages sorted by name with uptime %, downtime minutes, incident counts | `SLAView` table (sorted by `village_name`) | **Yes — M4** |
| 5 | Notes which villages are "Critical" or "Degraded" vs "Healthy" | `SLAView` status pills from `slaStatusConfig` | **Yes — M4** |
| 6 | Records "As of [timestamp]" from the dashboard for report traceability | `SLAView` timestamp (real API value) | **Yes — M4** |

**Success condition:** Administrator can generate a factual cross-village uptime table in under 5 minutes, with a real timestamp, without calling each operator individually. `[Own Data: SLAView, /topology/sla endpoint]`

**Gap / open question:** Does the district administrator currently receive any uptime data from operators? What format do they need it in (PDF, table, CSV)? `[Pending Call Verification]`

---

### Use Case 3.2 — Hindi Public Status Audit (Accessibility / Equity Check)

**Trigger:** Programme officer wants to verify that the public status page works in Hindi for the village population served by the scheme.

| Step | Actor Action | HopTrace Component | M4 Deliverable? |
|---|---|---|---|
| 1 | Opens `/status` page (no login) | `PublicStatus` | **Yes — M4** |
| 2 | Taps "हिन्दी" toggle — page switches to Hindi | `lang` state toggle → `?lang=hi` | **Yes — M4** |
| 3 | Reads village names, status messages, and all UI labels in Hindi | `STRINGS.hi`, API `message` in Hindi | **Yes — M4** |
| 4 | Verifies "अपडेट Xs पहले" timestamp is visible and recent | `formatUpdatedAt(..., 'hi')` | **Yes — M4** |
| 5 | Verifies `no_data` villages show "डेटा अनुपलब्ध" — not a fake status | `STRINGS.hi.dataUnavailable` | **Yes — M4** |

**Success condition:** Every visible label, status message, and timestamp on the page is in Hindi when lang=hi; no English fallback visible to the end user for core content. `[Own Data: STRINGS.hi completeness test in PublicStatus.test.js — 20/20 pass]`

---

### Use Case 3.3 — Stale Data Awareness (Error Transparency)

**Trigger:** Backend is briefly unreachable during a government audit visit.

| Step | Actor Action | HopTrace Component | M4 Deliverable? |
|---|---|---|---|
| 1 | Opens `/status` page; last fetch failed | `PublicStatus` fetchState='stale' | **Yes — M4** |
| 2 | Sees amber "Could not refresh — showing last known data" banner | Stale state indicator + amber `tsColorClass` | **Yes — M4** |
| 3 | Last good village data remains visible — no blank screen | `villages` state kept on error | **Yes — M4** |
| 4 | Taps "Retry" button — fresh fetch attempted | Retry button → `doFetch()` | **Yes — M4** |

**Success condition:** Page never shows blank or invented data. Last known state is shown with an honest amber stale indicator. `[Own Data: PublicStatus stale/retry logic implemented]`

---

## Gaps & Open Questions Across All Segments

> [!NOTE]
> These are items requiring call validation before they can be treated as confirmed.

| # | Gap / Question | Relevant Segment | Priority |
|---|---|---|---|
| G1 | Do operators check the dashboard proactively, or only reactively? | Segment 1 | High |
| G2 | Will operators share the `/status` URL with subscribers? Via what channel? | Segment 1, 2 | High |
| G3 | Is Hindi text sufficient for Segment 2, or is voice/audio essential? | Segment 2 | High |
| G4 | Do district administrators currently receive any structured uptime data? | Segment 3 | Medium |
| G5 | What format does Segment 3 need for official reporting (table, PDF, CSV)? | Segment 3 | Medium |
| G6 | Does Segment 1 currently have any informal SLA or uptime tracking? | Segment 1 | Medium |
| G7 | What is the realistic willingness-to-pay across all segments? | All | High |
| G8 | Is the 15-second polling interval appropriate for rural mobile data connections? | Segment 2 | Low |

*All G-items tagged `[Pending Call Verification]` until addressed in `customer_calls.md`.*

---

*Last updated: [TO FILL] | Lane: M4 | Status: [Draft — Pending Call Validation]*
