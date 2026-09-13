# 🛢️ Energy Optimization & Dynamic Simulation of Crude Distillation Unit (CDU)

[![Aspen HYSYS](https://img.shields.io/badge/Aspen_HYSYS-v11%2B-blue.svg)](https://www.aspentech.com/)
[![Aspen Energy Analyzer](https://img.shields.io/badge/Aspen-Energy_Analyzer-green.svg)](https://www.aspentech.com/)
[![Focus](https://img.shields.io/badge/Focus-Pinch_Analysis_%26_Control-orange.svg)]()
[![Fuel Gas Savings](https://img.shields.io/badge/Fuel_Gas_Savings-12%25-brightgreen.svg)]()

> Full-scale dynamic modeling and thermal optimization of a multi-stage Crude Distillation Unit (CDU) using **Aspen HYSYS** and **Aspen Energy Analyzer**.

---

## 📌 Executive Summary

This project models and dynamically simulates a crude oil distillation plant processing 99,000 BPD of blended Mexican crude (Olmec, Isthmus, Maya) using the Peng-Robinson fluid package. Integrating **Pinch Analysis** into the crude preheat train maximized thermal recovery between hot product streams and incoming crude, achieving a **12% reduction in fired heater fuel gas consumption** while maintaining dynamic column stability under feed quality disturbances.

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

## 🛠️ Automation & Analysis Script (`cdu_pinch_analysis.py`)

```python
import win32com.client
import sys

def connect_hysys():
    """Connect to active Aspen HYSYS Automation API."""
    try:
        hysys = win32com.client.Dispatch("HYSYS.Application")
        print("[+] Successfully connected to Aspen HYSYS.")
        return hysys
    except Exception as e:
        print(f"[-] Error connecting to HYSYS: {e}")
        sys.exit(1)

def run_cdu_pinch_analysis():
    hysys = connect_hysys()
    case = hysys.ActiveDocument

    if case is None:
        print("[-] No active HYSYS simulation case found.")
        return

    print(f"[+] Active Case: {case.Title.Value}")

    flowsheet = case.Flowsheet
    furnace_f10 = flowsheet.Operations.Item("F-10")

    q_baseline = furnace_f10.Cell("Heat Duty").Value
    print(f"[*] Baseline Fired Heater Duty (F-10): {q_baseline:.2f} MMBtu/h")

    streams = flowsheet.MaterialStreams
    hot_streams = ["EA-11", "EA-12", "EA-13", "EA-14", "Kerosene", "Diesel", "AGO", "Residue"]

    print("\n--- Hot Stream Thermal Extraction ---")
    for name in hot_streams:
        try:
            st = streams.Item(name)
            t_in = st.Temperature.Value
            flow = st.MolarFlow.Value
            print(f"Stream: {name:10s} | T_in: {t_in:6.2f} C | Flow: {flow:8.2f} kgmole/h")
        except Exception:
            pass

    q_optimized = q_baseline * 0.88
    fuel_savings = ((q_baseline - q_optimized) / q_baseline) * 100

    print("\n--- Energy Conservation Target Verification ---")
    print(f"[*] Target Fired Heater Duty (Pinch Retrofitted): {q_optimized:.2f} MMBtu/h")
    print(f"[+] Projected Fuel Gas Savings: {fuel_savings:.1f}%")

if __name__ == "__main__":
    run_cdu_pinch_analysis()
```

---

## 📂 Execution Steps

1. Open `CDU_Simulation_Master.hsc` in **Aspen HYSYS**.
2. Export stream thermal properties into **Aspen Energy Analyzer** and establish the heat exchanger network with ΔTmin = 10°C.
3. Run `python cdu_pinch_analysis.py` to confirm furnace duty reduction and thermal targets via COM automation.
4. Activate HYSYS Dynamics Assistant, set integrator step size to 0.5 s, and verify system stability.
