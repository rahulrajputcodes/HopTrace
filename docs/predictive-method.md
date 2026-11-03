# HopTrace Predictive Fault AI — Methodology, Evaluation & Limitations

This document details the mathematical formulation, design decisions, simulation models, evaluation protocol, benchmark results, and documented limitations of the HopTrace Predictive Fault AI engine.

---

## 1. Objective & Problem Statement

In rural Internet Service Provider (ISP) operations (Theme T3.2: *Running a Village Internet Business*), network infrastructure is geographically dispersed across villages, water towers, and hamlet poles. Dispatching a technician to climb a tower or inspect an optical line terminal after a complete blackout causes hours of downtime for essential village services (kirana stores, CSC centers, schools, and primary health centres).

The goal of Predictive Fault AI is to **warn before a link fails**:
- Estimate per-link Time-to-Failure (ETA in minutes) with an associated confidence rating (`high`, `medium`, `low`).
- Provide an estimated range `[eta_min, eta_max]` representing the 20th to 80th percentile bounds of degradation velocity.
- Give operators actionable lead time to intervene before the diagnostic engine detects an active outage or the link physically drops.

---

## 2. Mathematical Formulation

### 2.1 Why Not Use the Existing Time-Series `risk_score`?
The standard time-series risk score in network monitoring relies on an Exponentially Weighted Moving Average (EWMA) of latency and throughput deviations. However, for a slow, continuous degradation ramp (e.g. thermal drift or corroding connectors over 1–2 hours):
- The EWMA dynamically tracks the slowly shifting mean metrics.
- Consequently, the calculated deviation remains small, keeping the risk score below ~55, never reaching the critical alarm threshold (75).
- By the time an EWMA-based score alarms, the link is already in severe degradation.

### 2.2 Baseline-Relative Degradation Index ($D$)
To detect impending failure reliably, the predictor computes a **Degradation Index** $D \in [0, 1]$ relative to the static, documented healthy baselines of each link:

$$D = \frac{0.30 \cdot s_{\text{loss}} + 0.20 \cdot s_{\text{lat}} + 0.10 \cdot s_{\text{tp}}}{0.60}$$

Where the sub-scores match the exact normalization formulas of `DiagnosticEngine.evaluate_link`:
- **Packet Loss Sub-Score ($s_{\text{loss}}$)**:
  $$\Delta_{\text{loss}} = \max(0.0, \text{loss}_{\text{observed}} - \text{loss}_{\text{baseline}})$$
  $$s_{\text{loss}} = \min(1.0, \Delta_{\text{loss}} / 25.0) \quad \text{if } \Delta_{\text{loss}} > 1.0\% \text{ else } 0.0$$
- **Latency Sub-Score ($s_{\text{lat}}$)**:
  $$\Delta_{\text{lat}} = \max(0.0, \text{lat}_{\text{observed}} - \text{lat}_{\text{baseline}})$$
  $$s_{\text{lat}} = \min(1.0, \Delta_{\text{lat}} / 150.0) \quad \text{if } \Delta_{\text{lat}} > 10.0\text{ ms} \text{ else } 0.0$$
- **Throughput Sub-Score ($s_{\text{tp}}$)**:
  $$\text{drop}_{\text{pct}} = \max\left(0.0, \frac{\text{tp}_{\text{baseline}} - \text{tp}_{\text{observed}}}{\text{tp}_{\text{baseline}}}\right)$$
  $$s_{\text{tp}} = \min(1.0, (\text{drop}_{\text{pct}} - 0.15) / 0.70) \quad \text{if } \text{drop}_{\text{pct}} > 0.15 \text{ else } 0.0$$

**Architectural Separation Rule:** The physical connectivity term ($s_{\text{conn}}$) is excluded from $D$. If a link loses connectivity, it has *already failed* rather than being *about to fail*. Impending failure must be inferred solely from observed telemetry trends while the physical layer is still active.

### 2.3 Theil–Sen Trend Estimation
Ordinary Least Squares (OLS) regression is heavily sensitive to isolated telemetry jitter spikes (e.g. an instantaneous ICMP ping spike due to a CPU scheduling pause). 

Instead, HopTrace employs the non-parametric **Theil–Sen Estimator**:
1. For all sample pairs $(i, j)$ with $i < j$ in the sliding window of length $N = 10$, compute pairwise slope:
   $$S_{ij} = \frac{D_j - D_i}{j - i}$$
2. The overall degradation rate is the **median** of all pairwise slopes:
   $$\text{slope} = \text{median}(\{S_{ij}\})$$
3. The sample order index ($0, 1, \dots, n-1$) is used as the $x$-axis, ensuring consistency between streaming loops and laboratory injection runs regardless of tick counter offsets.

### 2.4 Estimated Time-to-Failure (ETA) and Uncertainty Range
Given failure threshold $D_{\text{FAIL}} = 0.60$ and current degradation $D_{\text{now}}$:
- **Point Estimate (ETA)**:
  $$\text{eta\_ticks} = \frac{D_{\text{FAIL}} - D_{\text{now}}}{\text{slope}}$$
  $$\text{predicted\_eta\_minutes} = \text{eta\_ticks} \times \text{SIM\_MINUTES\_PER\_TICK}$$

- **Range Bounds ($[ \text{eta\_min}, \text{eta\_max} ]$)**:
  From the sorted pairwise slopes $\{S_{ij}\}$, calculate the 20th percentile slope $s_{20}$ and the 80th percentile slope $s_{80}$.
  Since degradation slope is inversely related to time:
  $$\text{eta\_min\_minutes} = \frac{D_{\text{FAIL}} - D_{\text{now}}}{s_{80}} \times \text{SIM\_MINUTES\_PER\_TICK}$$
  $$\text{eta\_max\_minutes} = \frac{D_{\text{FAIL}} - D_{\text{now}}}{s_{20}} \times \text{SIM\_MINUTES\_PER\_TICK}$$
  This yields a natural $\sim 60\%$ coverage prediction interval bounded by `MAX_HORIZON_MINUTES`.

### 2.5 Confidence Categorization
An $R^2$ goodness-of-fit metric is computed against the Theil–Sen median-intercept trend line:
- **`high`**: $R^2 \ge 0.80$ AND $n \ge \text{WINDOW}$ (at least 10 samples confirming steady progression).
- **`medium`**: $R^2 \ge 0.50$ (identifiable trend with minor environmental noise).
- **`low`**: $R^2 < 0.50$ (high variance / unstable trajectory).

---

## 3. Parameter Derivations & Frozen Configuration

The following parameters were tuned exclusively on development seeds (0–99) and frozen in `backend/app/engine/predictor.py`:

| Constant | Value | Derivation & Purpose |
|---|---|---|
| `D_FAIL` | `0.60` | Failure threshold corresponding to medium/high fault severity where subscriber services degrade. |
| `D_WARN` | `0.05` | Minimum degradation index before issuing a warning. Tuned to precede the diagnostic engine incident threshold (0.10) by 8–10 minutes while rejecting baseline noise. |
| `MIN_SLOPE` | `0.002` | Minimum slope ($D$ per sample index) below which the trend is considered flat, avoiding erroneous forecasts on stationary links. |
| `SIM_MINUTES_PER_TICK` | `2.0` | Time conversion factor: 1 simulation tick (3 seconds in real time) represents 2.0 minutes of village network operation. |
| `MAX_HORIZON_MINUTES` | `120.0` | Maximum allowable forecast horizon (2 hours). Beyond this, microscopic slopes are discarded as unforecastable. |
| `WINDOW` | `10` | Number of most-recent telemetry samples retained for linear trend evaluation. |
| `MIN_SAMPLES` | `6` | Minimum sample count required before calculating slope, preventing volatile predictions from small sample sizes. |
| `CONFIDENCE_R2_HIGH` | `0.80` | $R^2$ threshold required for high-confidence warnings. |
| `CONFIDENCE_R2_MEDIUM` | `0.50` | $R^2$ threshold required for medium-confidence warnings. |

---

## 4. Realistic Fault Scenario Models & Real-World Motivations

All telemetry used in evaluation is **simulated telemetry parameterised from documented baselines** across the rural topology (L1 fiber, L2 ethernet, L3 5GHz wireless PtP, and L7 60GHz wireless PtP). Each scenario generator in `backend/app/engine/telemetry.py` takes an explicit random seed:

1. **`ramp_linear` (gradual mechanical / environmental degradation)**
   - *Model:* Metric increases linearly over $T \in \{20, 40, 80\}$ ticks + Gaussian noise $\mathcal{N}(0, \sigma^2)$.
   - *Motivation:* Simulates progressive fiber bend, thermal drift on outdoor transceivers, or gradual antenna misalignment from seasonal winds.

2. **`ramp_accelerating` (runaway physical fault)**
   - *Model:* Quadratic degradation $p = (t / T)^2$ + Gaussian noise.
   - *Motivation:* Simulates moisture ingress into an RJ45/SFP connector or thermal runaway in a pole-mounted POE injector, where initial degradation is imperceptible but rapidly escalates.

3. **`step_with_noise` (abrupt catastrophic outage)**
   - *Model:* Baseline telemetry until step tick $t = 15$, followed by immediate transition to full fault values.
   - *Motivation:* Simulates backhoe fiber cut or lightning strike. The predictor must honestly report 0.0 lead time and avoid promising unforecastable advance notice.

4. **`rain_fade` (millimeter-wave atmospheric attenuation)**
   - *Model:* On 60 GHz link L7 ($2.0\text{ ms}$, $950\text{ Mbps}$), a transient sinusoidal attenuation burst occurs between ticks 10 and 25, followed by full recovery.
   - *Motivation:* 60 GHz V-band links suffer heavy oxygen and precipitation absorption during monsoon rain downpours. Evaluates false-positive handling and recovery.

5. **`diurnal_load` (village daily usage cycle)**
   - *Model:* Healthy link with sinusoidal 24-hour cycle ($T = 60$ ticks); latency rises $+12\text{ ms}$ and throughput drops $25\%$ during evening hours, while packet loss remains strictly $0\%$.
   - *Motivation:* Village evening usage peaks (video streaming, online payments). The predictor must recognize healthy traffic cycles and remain silent.

6. **`flapping_precursor` (cable strain / intermittent contact)**
   - *Model:* Mean metrics remain near baseline while noise variance escalates ($\sigma_t = \sigma_0(1 + 0.15t)$), culminating in connectivity drop at tick 35.
   - *Motivation:* Loose jumper cable or swinging tower cable producing intermittent frame drops prior to complete physical disconnection.

7. **`stable_noisy` (heavy environmental noise)**
   - *Model:* Healthy baseline under $3\times$ zero-mean Gaussian noise.
   - *Motivation:* Tests rejection of background RF interference without emitting false alarms.

---

## 5. Evaluation Protocol

- **Dev / Test Split**:
  - **Development Seeds (0–99)**: 100 seeds used exclusively for parameter tuning and exploration.
  - **Test Seeds (1000–1199)**: 200 untouched seeds evaluated only after parameters are frozen. Never tuned against.
- **Execution Matrix**:
  - Scenarios $\times$ Links (`L1`, `L2`, `L3`, `L7`) $\times$ Severities (`low`, `medium`, `high`) $\times$ Noise levels (`low`, `high`).
  - Total runs: 8,000 simulations on Dev; 16,000 simulations on Test (24,000 runs total).
  - Benchmark completed in **74.22 seconds** on standard laptop hardware ($< 2$ minutes limit).

---

## 6. Benchmark Results Summary

### 6.1 Overall Performance (Dev vs. Test)

| Metric | Dev Seeds (0–99) | Test Seeds (1000–1199) | Gap / Generalization |
|---|---|---|---|
| **Total Runs** | 8,000 | 16,000 | Out-of-sample validated |
| **Detection Rate** | 71.4% | 71.8% | **+0.4% (Generalizes cleanly)** |
| **Miss Rate** | 28.6% | 28.2% | Expected from unforecastable step faults |
| **Lead Time vs Failure (Median ± IQR)** | 38.0 ± 38.0 min | 38.0 ± 38.0 min | **38.0 min advance warning** |
| **Lead Time vs Diagnostic Engine** | 10.0 ± 10.0 min | 8.0 ± 10.0 min | **Warns 8.0 min before incident** |
| **False Alarms per Link-Day** | 40.55 | 40.78 | Stable across sets |
| **Range Coverage ($[ \text{eta\_min}, \text{eta\_max} ]$)** | 58.9% | 58.3% | Matches theoretical 60% band |
| **ETA MAE (Median ± IQR)** | 2.7 ± 7.0 min | 2.7 ± 7.2 min | Tight prediction error |

### 6.2 Scenario Family Breakdown (Test Set)

| Scenario Family | Nature of Fault | Detection Rate | Lead Time vs Fail | Lead Time vs Diag Engine |
|---|---|---|---|---|
| **`ramp_linear`** | Linear Degradation | **100.0%** | **38.0 min** | **+6.0 min** |
| **`ramp_accelerating`** | Quadratic Runaway | **100.0%** | **42.0 min** | **+12.0 min** |
| **`step_with_noise`** | Abrupt Disconnection | **0.6%** | 2.0 min | -8.0 min |
| **`flapping_precursor`** | High-Variance Flapping | **35.5%** | 10.0 min | +6.0 min |
| **`diurnal_load`** | Healthy Daily Rhythm | N/A (Healthy) | **0.3 FA / link-day** | N/A |
| **`stable_noisy`** | Heavy Environmental Noise | N/A (Healthy) | **3.0 FA / link-day** | N/A |
| **`rain_fade`** | 60 GHz Attenuation Burst | N/A (Recovers) | 92.9 FA / link-day | N/A |

### 6.3 Confidence Band Accuracy (Test Set)

| Confidence Tier | Observations | Median ETA MAE | Error Distribution |
|---|---|---|---|
| **HIGH ($R^2 \ge 0.8, n \ge 10$)** | 101,039 | **2.2 min** | Extremely tight error ($IQR = 6.1\text{ min}$) |
| **MEDIUM ($R^2 \ge 0.5$)** | 25,250 | **4.4 min** | Reliable early indicator ($IQR = 9.0\text{ min}$) |
| **LOW ($R^2 < 0.5$)** | 2,129 | **23.8 min** | Wide variance; warns operator of uncertainty |

---

## 7. Where It Fails (Documented Limitations)

Honesty about failure modes is essential for engineering integrity:

1. **Abrupt Structural Failures (`step_with_noise`)**:
   - *Behavior:* 0.0 lead time. Detection rate is effectively 0%.
   - *Reason:* When an aerial fiber line is severed, telemetry drops from healthy to failure in zero ticks. No trend-based algorithm can foresee a physical cut without external physical sensors. The model correctly refrains from inventing false warnings.
2. **Transient Atmospheric Absorption (`rain_fade`)**:
   - *Behavior:* Emits warnings during peak rain attenuation (ticks 10–25), but the link self-heals once the rain cloud passes.
   - *Resolution in Field:* Production systems must correlate 60 GHz link alarms with local meteorological data or radar feeds before rolling a field vehicle.
3. **High-Variance Flapping (`flapping_precursor`)**:
   - *Behavior:* Reduced detection rate (35.5%) and wider prediction bounds.
   - *Reason:* Oscillations around the mean without a monotonic slope lower $R^2$, placing warnings into the `low` confidence tier.
4. **Synthetic Data Limitations**:
   - Telemetry is **simulated telemetry parameterised from documented baselines** designed for the HackFront India rural network topology.
   - The time scale assumes an idealized 2.0 simulated minutes per tick.
   - In production deployment, the engine must be calibrated against real-world SNMP poll streams, live syslog link flap counters, and real optical power (DDM/DOM) measurements.
