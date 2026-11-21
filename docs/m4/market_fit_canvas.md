# HopTrace M4 — Market Fit Canvas

> [!IMPORTANT]
> **Traceability system — every claim must carry exactly one tag:**
> - `[Person: <name or role>]` — from a named team member, advisor, or stakeholder
> - `[Own Data: <what data]` — derivable from HopTrace's own codebase, demo, or backend logs
> - `[Pending Call Verification]` — a hypothesis not yet confirmed by a customer call
> - `[Source: <named source, URL, or report title>]` — for external statistics
>
> **If a cell has no tag, it is fabricated. Remove it or add a tag before submission.**

> [!CAUTION]
> **No rounded numbers, no invented statistics.**
> Any market-size figure without a named, dateable source must read `[SOURCE REQUIRED — NO ROUNDED OR INVENTED NUMBERS]`.
> Any pricing figure without call or team validation must read `[TO FILL FROM CALLS / TEAM — NO INVENTED NUMBERS]`.

---

## 1. Target Customer

### Primary
**Rural village ISP / cable owner-operator** — an individual or small-team operator who:
- Runs a broadband network serving one or more villages (typically self-built FTTH or wireless mesh) [Person: team field context — Pending Named Person Tag]
- Holds or operates under an ISP licence or as a reseller/franchisee of a licensed ISP [Pending Call Verification]
- Has limited formal IT staff; often the owner is also the field technician [Pending Call Verification]
- Monitors their network primarily via informal channels (WhatsApp, phone, manual site visits) [Pending Call Verification]

### Secondary
- District or block-level programme administrator overseeing BharatNet / state connectivity scheme coverage [Pending Call Verification]
- Village panchayat representative who needs to report connectivity to block office [Pending Call Verification]

### Anti-target (explicitly out of scope for initial segment)
- Tier-1 or Tier-2 city ISPs with dedicated NOC staff [Person: team decision]
- Enterprise WAN / corporate customers [Person: team decision]

---

## 2. Problem Evidence

| # | Problem Statement | Evidence Tag | Strength |
|---|---|---|---|
| P1 | Operators have no real-time visibility into which link or village is down — they learn from subscriber complaints | [Pending Call Verification] | Hypothesis |
| P2 | Fault diagnosis is manual and slow — operator physically travels to site or calls each AP one by one | [Pending Call Verification] | Hypothesis |
| P3 | No structured subscriber notification for outages — WhatsApp broadcast or word of mouth | [Pending Call Verification] | Hypothesis |
| P4 | No uptime record — SLA cannot be proved to subscribers or regulators | [Pending Call Verification] | Hypothesis |
| P5 | Hindi / local language interface is a barrier to adopting English-only tools | [Pending Call Verification] | Hypothesis |
| P6 | Existing enterprise NMS tools (Zabbix, LibreNMS) require Linux administration skills operators do not have | [Person: team technical assessment] | Team Assessment |

> [!NOTE]
> P1–P5 are hypotheses. Each must be tagged `[Confirmed: Call X]` or `[Disconfirmed: Call X]` after calls are completed.

---

## 3. Current Alternative (What They Do Today Without HopTrace)

| Alternative | Limitation | Evidence Tag |
|---|---|---|
| WhatsApp group for subscriber complaints | Reactive only; no proactive fault detection | [Pending Call Verification] |
| Phone calls from subscribers or field workers | Slow; depends on subscriber availability | [Pending Call Verification] |
| Manual site visit to check equipment | High travel cost and time for rural geography | [Pending Call Verification] |
| Ping/traceroute from laptop when on site | No persistent monitoring; skill-dependent | [Person: team technical assessment] |
| No formal SLA or uptime record | Cannot prove reliability; churn is invisible | [Pending Call Verification] |
| Enterprise NMS (Zabbix / LibreNMS) | Complex setup; not localised; assumes IT staff | [Person: team technical assessment] |

---

## 4. Value Proposition

| Benefit | How HopTrace Delivers It | Evidence Tag |
|---|---|---|
| Real-time fault detection before subscriber complaints | Live telemetry + risk heatmap on NOC dashboard | [Own Data: topology/risk endpoint, live WebSocket] |
| AI-explained root cause in plain language | `/incidents/{id}/explain` with Gemini/Sarvam | [Own Data: AIExplanationCard component, backend explain endpoint] |
| One-click SMS/voice subscriber notification | Notify flow via SubscriberOps + Twilio/console provider | [Own Data: notify endpoint, SubscriberOps component] |
| SLA / uptime report for any time window | SLAView component, `/topology/sla?window_hours=N` | [Own Data: SLAView, public_status.py backend] |
| Public village status page — no login, en + hi | `/status` page (PublicStatus component), bilingual, polled every 15s | [Own Data: PublicStatus component, public_status.py] |
| Optional voice status update (accessibility) | POST `/voice` → audio playback in PublicStatus | [Own Data: tryPlayVoice helper — M3 endpoint pending] |
| Works on mobile, 375px+ | Mobile-first Tailwind layout | [Own Data: PublicStatus responsive design] |

---

## 5. Business Model

> [!CAUTION]
> **No invented pricing. No invented revenue projections.**
> Fill from actual call data or explicit team decision only.

| Element | Current Hypothesis | Fill Source |
|---|---|---|
| Revenue model type | [TO FILL FROM CALLS / TEAM — e.g. SaaS monthly / per-village / one-time setup fee] | [TO FILL FROM CALLS / TEAM — NO INVENTED NUMBERS] |
| Price per operator per month | [TO FILL FROM CALLS / TEAM — NO INVENTED NUMBERS] | Customer call willingness-to-pay |
| Price sensitivity range | [TO FILL FROM CALLS / TEAM — NO INVENTED NUMBERS] | Customer call |
| Free tier / freemium threshold | [TO FILL FROM TEAM] | Team decision |
| Onboarding / setup fee | [TO FILL FROM CALLS / TEAM — NO INVENTED NUMBERS] | Customer call |
| Payment collection method | [TO FILL FROM CALLS — e.g. UPI, bank transfer, cash advance] | Customer call |
| Cost to serve per operator | [TO FILL FROM TEAM — infra cost per active deployment] | Team / cloud cost analysis |

**Unit economics hypothesis (not filled until costs and pricing are known from calls + team):**
- CAC: [TO FILL FROM TEAM — NO INVENTED NUMBERS]
- LTV: [TO FILL FROM CALLS / TEAM — NO INVENTED NUMBERS]
- Payback period: [TO FILL — NO INVENTED NUMBERS]

---

## 6. Market Size

> [!CAUTION]
> **Every number in this section requires a named, dateable, linkable source.**
> Do not round numbers to look impressive. Do not use "approximately" without a source range.
> If the source is not available yet, write `[SOURCE REQUIRED — NO ROUNDED OR INVENTED NUMBERS]`.

| Metric | Value | Source | Date |
|---|---|---|---|
| Total Internet Service Providers licensed in India (Class A + B + C) | [SOURCE REQUIRED] | [TRAI Telecom Subscription Data — URL REQUIRED] | [DATE REQUIRED] |
| ISPs operating primarily in rural / semi-urban areas | [SOURCE REQUIRED] | [SOURCE REQUIRED] | [DATE REQUIRED] |
| BharatNet village-level connections active | [SOURCE REQUIRED] | [DoT / BharatNet portal — URL REQUIRED] | [DATE REQUIRED] |
| Average subscribers per rural ISP operator | [SOURCE REQUIRED — from TRAI or primary research] | [SOURCE REQUIRED] | [DATE REQUIRED] |
| Rural broadband penetration (% of rural households) | [SOURCE REQUIRED] | [TRAI Annual Report — URL REQUIRED] | [DATE REQUIRED] |
| Total revenue of rural broadband market (India) | [SOURCE REQUIRED] | [SOURCE REQUIRED] | [DATE REQUIRED] |

> [!NOTE]
> TAM / SAM / SOM will be derived from the above table once sources are confirmed.
> Do not state TAM/SAM/SOM figures without completing the table above.

---

## 7. Competitors

| Competitor | What They Do | Why Gap Remains for Our Segment | Evidence Tag |
|---|---|---|---|
| Zabbix | Open-source network monitoring, highly capable | Requires Linux/SNMP expertise; no Hindi UI; no subscriber notification | [Person: team technical assessment] |
| LibreNMS | Auto-discovery NMS, strong enterprise feature set | Same barrier as Zabbix; not rural-ISP targeted | [Person: team technical assessment] |
| PRTG Network Monitor | Commercial NMS, easy setup | Priced for enterprise; English-only; no village-status public page | [Person: team technical assessment] |
| WhatsApp + manual calls | Current default for most small operators | No proactive detection; no SLA record; no AI fault explanation | [Pending Call Verification] |
| ISP-bundled portals (from upstream carrier) | Sometimes provided by BSNL / state ISP as reseller tools | Coverage limited to carrier links; no last-mile village view | [Pending Call Verification] |
| None identified with: bilingual public status + voice + SLA view + AI explain | — | This combination is the differentiation hypothesis | [Person: team product decision — Pending External Validation] |

---

## 8. First 100 Users

> [!NOTE]
> "Users" here = operator accounts (each operator may serve many villages).

| # | Acquisition Path | Rationale | Evidence Tag |
|---|---|---|---|
| U1 | Hackathon network — evaluators and judges who are practitioners or know practitioners | Warm introductions; willing to try demo | [Person: team — hackathon context] |
| U2 | Direct outreach to ISPs in UP / MP identified via TRAI licence list | TRAI publishes ISP registrant details publicly | [Source: TRAI licence registry — URL REQUIRED] |
| U3 | Referral from Call 1–3 interviewees if product resonates | Likely if pain is confirmed and product fits | [Pending Call Verification] |
| U4 | BharatNet implementation partners / VLEs (Village Level Entrepreneurs) | Direct touchpoint with rural network operators | [Source: CSC / BharatNet VLE programme — URL REQUIRED] |
| U5 | Academic / NGO connectivity research groups (IIT labs, A4AI, LIRNEasia) | Can refer operators they already work with | [Pending Call Verification] |

**Conversion hypothesis:** [TO FILL AFTER CALLS — what makes an operator sign up after seeing the demo]

---

*Last updated: [TO FILL] | Lane: M4 | Status: [Draft — Pending Call Validation]*
