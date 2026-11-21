# HopTrace Local Docker Testbed

A zero-mock emulation environment running all 14 physical/virtual topology nodes on a dedicated bridge network (`192.0.2.0/24`) for live validation of hop-by-hop probing, topological fault subtraction, and agent store-and-forward resilience.

## 10-Step Quickstart & Fault Isolation Walkthrough

1. **Spin up testbed containers:**
   ```bash
   docker compose -f testbed/docker-compose.testbed.yml up -d
   ```
2. **Start HopTrace backend API (with live mode):**
   ```bash
   DATA_MODE=live uvicorn backend.app.main:app --port 8000
   ```
3. **Start the HopTrace edge agent:**
   ```bash
   python agent/hoptrace_agent.py --config testbed/agent.config.json
   ```
4. **Observe dashboard / API:**
   All 14 links show `freshness: "live"` and diagnostic status is `closed` (normal baseline).
5. **Inject a backhaul failure at WB3 (Bhatpur wireless backhaul):**
   ```bash
   sh testbed/fault.sh WB3 down
   ```
6. **Observe hop-by-hop path probe results:**
   Agent pings show `WB3` unreachable along with descendants `WB4`, `R2`, `AP3`, `AP4`.
7. **Verify topological subtraction in HopTrace Engine:**
   Engine marks only `L6` (`R1 -> WB3`) as down (100% loss). Descendants `L7`, `L8`, `L9`, `L10` are tagged `behind_failure` and suppressed from false incident creation.
8. **Check Root Cause Analysis:**
   Incident opens blaming `L6` with high confidence. Cause reasoning attributes failure to `hardware_power_outage` or `physical_cut`.
9. **Heal the topology segment:**
   ```bash
   sh testbed/fault.sh WB3 heal
   ```
10. **Tear down testbed containers when finished:**
    ```bash
    docker compose -f testbed/docker-compose.testbed.yml down
    ```
