# 🛢️ Energy Optimization & Dynamic Simulation of Crude Distillation Unit (CDU)

[![Aspen HYSYS](https://img.shields.io/badge/Aspen_HYSYS-v11%2B-blue.svg)](https://www.aspentech.com/)
[![Aspen Energy Analyzer](https://img.shields.io/badge/Aspen-Energy_Analyzer-green.svg)](https://www.aspentech.com/)
[![Focus](https://img.shields.io/badge/Focus-Pinch_Analysis_%26_Control-orange.svg)]()
[![Python](https://img.shields.io/badge/Portable_analysis-Python_3.10%2B-blue.svg)]()

> Full-scale dynamic modeling and thermal optimization of a multi-stage Crude Distillation Unit (CDU) using **Aspen HYSYS** and **Aspen Energy Analyzer**.

---

## 📌 Executive Summary

The project documentation describes a crude oil distillation plant processing 99,000 BPD of blended Mexican crude (Olmec, Isthmus, Maya) using the Peng–Robinson fluid package, with a reported 12% fuel reduction target/result. The supplied template and report do not independently reproduce that figure or demonstrate dynamic stability. The tools below calculate targets from explicit stream data rather than assuming a fixed percentage saving.

---

## 🚀 Performance Metrics

| Performance Metric | Baseline Model | Retrofitted (Pinch Optimized) | Improvement |
| :--- | :--- | :--- | :--- |
| **Furnace Duty (`F-10`)** | Baseline Load | Optimized Load | **12% Fuel Gas Reduction** |
| **Crude Furnace Inlet Temp** | 228.4°C | >255.0°C | **+26.6°C Thermal Recovery** |
| **Cooling Utility Load** | Baseline Load | Minimized Load | **Reduced Utility Water Demand** |
| **Dynamic Control** | Manual Setpoints | 2nd Single Feedback PID | **Automated Yield Stability** |

---

## 🏗️ System Architecture & Unit Specs

```
       ┌──────────┐     ┌─────────────┐     ┌───────────┐     ┌──────────┐
Crude ─►│ Preflash │────►│ Atmospheric │────►│ Stabilizer│────►│  Vacuum  │
Blend   │  (C-00)  │     │   (C-10)    │     │  (C-20)   │     │  (C-30)  │
        └────┬─────┘     └──────┬──────┘     └─────┬─────┘     └────┬─────┘
             │                  │                  │                │
             └──────────────────┴─────────┬────────┴────────────────┘
                                           ▼
                            ┌───────────────────────────┐
                            │ Optimized Preheat Train    │ (Pinch Analysis)
                            └───────────────────────────┘
```

<details>
<summary><b>🔍 View Column Specifications & Hardware Breakdown</b></summary>

<br>

| Equipment Label | Description | Stages | Top Press. | Target Temp. | Key Output Fraction |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`C-00`** | Preflash Column | 6 trays | 170 kPa | 42.7°C | Light Naphtha, Preflash Vapor |
| **`C-10`** | Atmospheric Column | 29 trays | 104 kPa | 76.9°C | Naphtha, Kerosene, Diesel, AGO, Residue |
| **`C-11`** | Kerosene Side Stripper | 6 stages | 144.5 kPa | Steam stripped | Kerosene (180–240°C cut) |
| **`C-12`** | Diesel Side Stripper | 3 stages | 158 kPa | Steam stripped | Diesel (240–340°C cut) |
| **`C-13`** | AGO Side Stripper | 3 stages | 174.9 kPa | Steam stripped | AGO (340–370°C cut) |
| **`C-20`** | Naphtha Stabilizer | 36 stages | 1030 kPa | 159.1°C | LPG Overhead, Stabilized Naphtha |
| **`C-30`** | Vacuum Distillation | 14 stages | 2 kPa | 112.0°C | LVGO, HVGO, Vacuum Residue |

</details>

---

## ⚡ Energy Optimization & Pinch Analysis

<details>
<summary><b>🔥 Click to expand Heat Exchanger Network (HEN) Retrofit Details</b></summary>

<br>

### 1. Data Extraction to Aspen Energy Analyzer
* **Cold Streams:** Raw crude feed entering preheat train prior to furnace `F-10` and `F-30`.
* **Hot Streams:** Atmospheric pumparounds (`EA-11` to `EA-14`), Vacuum pumparounds (`EA-31`, `EA-32`), and product rundown streams (`Naphtha`, `Kerosene`, `Diesel`, `AGO`, `Residue`).

### 2. Pinch Targeting Criteria
* **Minimum Temperature Approach (ΔTmin):** 10.0°C – 15.0°C
* **Cross-Pinch Violation Elimination:** Enforced zero heat transfer across the pinch point to minimize external utility loads.

### 3. Quantitative Results

Fuel Gas Reduction (%) = ((Q_Furnace,Base − Q_Furnace,Retrofit) / Q_Furnace,Base) × 100 = **12.0%**

</details>

---

## 🎮 Dynamic Control Architecture

<details>
<summary><b>🎛️ Click to expand PID Controller Configurations</b></summary>

<br>

To handle real-time feed quality and flow variations (Olmec, Isthmus, and Maya crudes), the plant implements automated setpoint adjustment:

* **Atmospheric Coil Outlet Control (`TIC-10`):** Regulates fuel gas to furnace `F-10` to maintain feed at 338.4°C.
* **Side Stripper Flow Control (`FIC-11`, `FIC-12`, `FIC-13`):** Implements 2nd Single Feedback Control based on volumetric yield calculations:

  SPᵢ = Σⱼ (Q̇ⱼ × Fractionᵢ)

* **Column Pressure & Level Control:** `PIC-10` and `LIC-10` maintain partial condenser pressure and liquid hold-up at 50% volume.

</details>

---

## 🛠️ New automation and analysis features

- **Read-only Aspen HYSYS export:** attach to an open Windows case and export configured inlet/outlet pairs with explicit unit conversions, mass-flow consistency checks, and provenance metadata.
- **Actual pinch targeting:** shifted-temperature heat cascade calculates minimum heating/cooling, maximum heat recovery, and internal pinch temperatures from your data.
- **ΔTmin sensitivity:** compare utility demand at several temperature approaches before considering exchanger design.
- **Economics and emissions:** estimate potential fuel, annual cost, direct CO₂, and simple payback against a supplied heater baseline.
- **Standalone visual reports:** grand composite curve, utility sensitivity, stream tables, and assumptions in an offline HTML file, plus machine-readable JSON.

### 1. Connect a real Aspen case (Windows)

Use a Python version compatible with your HYSYS COM installation. Install the optional Windows dependency:

```powershell
py -m pip install -r requirements-hysys.txt
```

Open a **copy** of the supplied `.tpl` in a compatible licensed Aspen installation, or open your validated case. The repository does not contain the previously referenced `CDU_Simulation_Master.hsc`; template compatibility must be checked in Aspen. Solve and review the case yourself.

Copy `examples/hysys_mapping.json` to your own mapping file. Replace placeholder stream names with exact names from the active flowsheet and confirm the solved/sensible-stream declarations only after reviewing the case. Then run:

```powershell
py hysys_export.py --map my_hysys_mapping.json --output outputs/hysys_streams.csv --metadata outputs/hysys_export.json
py cdu_pinch_analysis.py outputs/hysys_streams.csv --dt-min 10 --sweep 5,10,15,20,30
```

Open `outputs/report.html` in a browser. See [the HYSYS automation guide](docs/HYSYS_AUTOMATION.md) for mapping, property reads, limitations, and troubleshooting. Live HYSYS integration requires Windows, Aspen, and a license; the portable analysis requires none of these.

### 2. Try the portable analysis now

Python **3.10+**, standard library only. No package installation or server is needed:

```bash
python3 cdu_pinch_analysis.py examples/streams.csv --dt-min 20
```

The supplied CSV is **synthetic demonstration data**, not an export of the supplied case. Its hand-checkable targets at ΔTmin = 20°C are **29 kW hot utility**, **60 kW cold utility**, and **355 kW heat recovery**. The internal pinch is **100°C hot / 80°C cold**.

Outputs default to `outputs/analysis.json` and `outputs/report.html`. Use `--json` and `--html` to choose paths. These output files are ignored by Git.

For an illustrative economic scenario:

```bash
python3 cdu_pinch_analysis.py examples/streams.csv --dt-min 20 --baseline-duty 35 --heater-efficiency 0.85 --hours 8000 --fuel-price 40 --co2-factor 56.1 --retrofit-cost 1000
```

This **synthetic** example yields 17.14% potential fuel reduction and about 2,258.82 currency units/year in savings. It is not a verification of the original 12% claim.

### Input data and units

Use this exact CSV schema (column order may vary):

```csv
name,kind,supply_c,target_c,cp_kw_per_k
Hot product,hot,180,40,2
Crude preheat,cold,20,140,2
```

`cp_kw_per_k` is **heat-capacity flow rate**, not specific heat: mass flow (kg/s) × specific heat (kJ/kg/K). Hot streams cool; cold streams heat. Names must be unique, numbers finite, CP positive, and at least one stream of each type supplied. ΔTmin must be positive. Invalid inputs fail with a clear error rather than producing a report. Add `--data-note` to record measurement source and case conditions.

HYSYS exports use an effective constant CP = mass flow × enthalpy difference / temperature difference. Use sensible-only segments with approximately constant properties; segment variable-property streams before analysis. Do not include both an overall stream and its component segments, or count both sides of the same heat requirement as separate process demands.

### Calculation basis

Hot temperatures shift down by ΔTmin/2 and cold temperatures up by ΔTmin/2. Each shifted interval releases `(ΣCP_hot − ΣCP_cold) × ΔT`. The deepest heat-cascade deficit determines minimum hot utility; the corrected bottom residual determines minimum cold utility. Internal zero residuals identify pinch locations; endpoint zeros indicate utility thresholds. Recovery equals total cold duty minus hot utility, also equal to total hot duty minus cold utility.

The hot utility target is a **system-level** minimum. Compare it with a measured useful heater duty only when both cover the same stream/system boundary. Baseline duty is heat delivered to the process, not fuel-input power. With constant efficiency:

```text
Fuel savings (kW) = (baseline useful duty − targeted useful duty) / efficiency
Annual fuel savings (MWh) = fuel savings (kW) × operating hours / 1000
Annual cost savings = annual fuel savings (MWh) × price per MWh fuel
Annual CO₂ savings (tonnes) = annual fuel savings (MWh) × 3.6 × kg CO₂/GJ / 1000
Simple payback (years) = retrofit capital cost / positive annual cost savings
```

A target above baseline retains negative savings. Payback is unavailable without investment or positive annual savings. Fuel price and investment use the same chosen currency. Defaults (85% efficiency, 8,000 hours/year, 40 currency/MWh, 56.1 kg CO₂/GJ fuel) are editable screening assumptions, not measured case properties. Emissions exclude upstream lifecycle effects; payback excludes financing, maintenance, taxes, and cooling-utility costs.

These calculations do not size or optimize an exchanger network, account for forbidden matches or finite utility temperatures, solve a column, tune PID controllers, or verify dynamic stability. Smaller ΔTmin can reduce utility demand while increasing exchanger area; the sweep does not claim an economic optimum.

### Validation

```bash
python3 -m unittest discover -s tests -v
```

Tests cover hand-calculated cascade targets, thermal balances, sensitivity, malformed input, economic conversions, HTML escaping, and simulated COM exports. COM test doubles verify exporter logic and requested units; they do not validate a live Aspen installation. For live acceptance, compare exported properties and duties with Aspen's stream workbook before using the report for engineering decisions.

The original `.tpl` and PDF remain unchanged. Aspen Energy Analyzer and HYSYS Dynamics remain the tools for full network and dynamic simulation validation.
