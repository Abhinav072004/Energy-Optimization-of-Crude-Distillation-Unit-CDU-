# 🛢️ Energy Optimization & Dynamic Simulation of Crude Distillation Unit (CDU)

[![Aspen HYSYS](https://img.shields.io/badge/Aspen_HYSYS-v14%2B-blue.svg)](https://www.aspentech.com/)
[![Aspen Energy Analyzer](https://img.shields.io/badge/Aspen-Energy_Analyzer-green.svg)](https://www.aspentech.com/)
[![Focus](https://img.shields.io/badge/Focus-Pinch_Analysis_%26_Control-orange.svg)]()
[![Fuel Gas Savings](https://img.shields.io/badge/Fuel_Gas_Savings-12%25-brightgreen.svg)]()

> **Project Target:** Full-scale modeling, dynamic stability control, and thermal optimization of a multi-stage Crude Distillation Unit (CDU) using **Aspen HYSYS** and **Aspen Energy Analyzer**[cite: 1].

---

## 📌 Executive Summary

This project presents a comprehensive steady-state and dynamic simulation of an industrial crude oil distillation plant processing 99,000 BPD of blended crude[cite: 1]. By integrating **Pinch Analysis** into the crude preheat train, thermal recovery between hot product streams and incoming crude was maximized, achieving a **12% reduction in fired heater fuel gas consumption** while maintaining dynamic column stability under feed disturbances[cite: 1].

---

## 🚀 Key Highlights & Metrics

| Performance Metric | Baseline Model | Retrofitted (Pinch Optimized) | Improvement |
| :--- | :--- | :--- | :--- |
| **Furnace Duty (`F-10`)** | 100% | 88% | **12% Fuel Gas Reduction** |
| **Crude Furnace Inlet Temp** | 228.4°C[cite: 1] | >255.0°C | **+26.6°C Thermal Recovery** |
| **Cooling Utility Load** | High | Minimized | **Reduced Cooling Water Demand** |
| **Dynamic Stability** | Manual / Static Setpoints | 2nd Single Feedback PID[cite: 1] | **Automated Distillate Yield Control**[cite: 1] |

---

## 🏗️ System Architecture & Units

The CDU flowsheet models four major process stages[cite: 1]:

