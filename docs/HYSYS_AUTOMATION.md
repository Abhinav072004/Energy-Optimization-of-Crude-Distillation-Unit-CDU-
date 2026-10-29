# Aspen HYSYS automation

The exporter reads a running Windows HYSYS case into the portable pinch-analysis
workflow. It never opens/saves a case, changes a setpoint, starts the solver, or
controls the dynamics integrator. Test it on a copy of your case first.

## Windows setup

1. Install and license a compatible Aspen HYSYS version. The original README
   indicates v11+, but the included `.tpl` has not been opened in Aspen here.
   The previously mentioned `CDU_Simulation_Master.hsc` is not supplied.
2. Use Python 3.10+ with a Windows/COM configuration compatible with your Aspen
   installation, and run `py -m pip install -r requirements-hysys.txt`.
3. Open your case in HYSYS, solve it, inspect convergence and property values,
   and pause dynamics. Keep it stable and avoid editing it during export:
   sequential property reads are not an atomic simulation snapshot.
4. Run Python in the same Windows user session as HYSYS. The exporter calls
   `win32com.client.GetActiveObject("HYSYS.Application")`; it does not launch an
   application or choose a case file. Confirm the correct case is active.

## Map the actual flowsheet

Copy `examples/hysys_mapping.json` to a new file, such as
`my_hysys_mapping.json`. Replace every placeholder with an exact material-stream
name from `ActiveDocument.Flowsheet.MaterialStreams`. Subflowsheets are not
traversed automatically. At least one hot and one cold segment are required.

Each pair describes the **same material stream** before and after sensible
heating/cooling. Use the inlet for supply temperature and outlet for target
temperature. A heat-recovery segment already installed in the case can therefore
be exported, but the target temperatures must represent the process requirements
for the study. Review your system boundary and avoid double-counting duties.

```json
{
  "confirmed_solved": true,
  "streams": [
    {
      "name": "Crude preheat segment",
      "kind": "cold",
      "inlet": "YOUR_CRUDE_INLET",
      "outlet": "YOUR_CRUDE_OUTLET",
      "sensible_only": true
    },
    {
      "name": "Hot product cooling segment",
      "kind": "hot",
      "inlet": "YOUR_PRODUCT_INLET",
      "outlet": "YOUR_PRODUCT_OUTLET",
      "sensible_only": true
    }
  ]
}
```

`confirmed_solved` and `sensible_only` are **user declarations**, not measured
properties. Set them to `true` only after reviewing the case and the segment
basis. The checked-in example defaults to `false` so it cannot silently claim
to represent a solved, sensible-only case. Do not map an entire distillation
column, stripper, mixer, splitter, reacting section, or phase-change segment as
a constant-CP stream.

## Export and analyze

Run these commands from the repository root in PowerShell:

```powershell
py hysys_export.py --map my_hysys_mapping.json --output outputs/hysys_streams.csv --metadata outputs/hysys_export.json
py cdu_pinch_analysis.py outputs/hysys_streams.csv --dt-min 10 --sweep 5,10,15,20,30 --data-note "HYSYS export; see hysys_export.json for case and property basis"
```

Read `outputs/hysys_export.json`, compare its source values against the stream
workbook, and open `outputs/report.html`. The export metadata records case title,
UTC export time, both endpoint states, units, assumptions, and per-segment duties.
Keep the metadata with the CSV; it is not embedded automatically in the analysis
JSON. No `.tpl` or PDF data is inferred or parsed into plant measurements.

To estimate cost/CO₂ savings, add `--baseline-duty` (useful process heat in kW),
`--heater-efficiency`, `--hours`, `--fuel-price`, `--co2-factor`, and optionally
`--retrofit-cost` to the analysis command. The baseline must cover the same
system as the utility target. The exporter does not assume a furnace COM
property or label such as `F-10`; obtain and check the baseline in Aspen.

## Property reads and checks

The exporter explicitly requests these common HYSYS Automation API properties:

| Property call | Unit | Use |
| --- | --- | --- |
| `Temperature.GetValue("C")` | °C | Supply and target temperatures |
| `MassFlow.GetValue("kg/s")` | kg/s | Positive material flow; mass consistency |
| `MassEnthalpy.GetValue("kJ/kg")` | kJ/kg | Sensible duty from enthalpy change |

For each pair, `CP = inlet_mass_flow × (outlet_enthalpy − inlet_enthalpy) /
(outlet_temperature − inlet_temperature)`. This gives kW/K. CP is an effective
constant approximation; it preserves that segment's total duty but cannot
represent strongly variable heat capacity or latent heat. Segment those streams
appropriately before analysis.

Inlet/outlet mass flow must match within 0.1% of the larger flow. Both
temperature and enthalpy must increase for a cold stream and decrease for a hot
stream. Duplicate pair definitions, invalid names, zero/reverse flow,
non-finite values, and inconsistent directions fail before output is written.
Matching flows alone do not prove equal composition or sensible-only behavior.

## Troubleshooting and acceptance

- **Windows/pywin32 error:** the exporter runs on the licensed Windows machine.
  Linux can analyze previously exported CSV files without `pywin32`.
- **Cannot attach / no active case:** open HYSYS and the correct case under the
  same user session as Python; check COM registration and Python compatibility
  using your Aspen installation guidance.
- **Missing stream:** check spelling and the active flowsheet. Equipment names,
  energy streams and nested-flowsheet material streams are not interchangeable.
- **Unsupported property/unit:** compare the error's explicit property/unit
  with the Automation API supported by your installed version. Do not silently
  substitute `.Value`, which may use internal units.
- **Invalid flow or direction:** review the mapping, case convergence, phase
  change and snapshot stability. Do not suppress a failing check to force export.

Automated tests use fake COM objects to check calls, validation, CSV output and
metadata. They do not establish compatibility with a live installation. Live
acceptance requires checking every exported endpoint against Aspen, checking
`CP × |ΔT|` against the segment's enthalpy duty, and comparing utility targets
with an independently prepared Energy Analyzer study at the same ΔTmin.
Fuel savings, network feasibility and dynamic stability require separate
engineering validation. This exporter supplies the data and reproducible
screening workflow; it does not perform closed-loop control or setpoint tuning.
