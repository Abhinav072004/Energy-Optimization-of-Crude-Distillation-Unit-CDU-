"""CSV-to-report command line workflow, using only the Python standard library."""

import argparse
import csv
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys

from .analysis import Stream, analyze
from .economics import estimate_savings
from .report import render_report


FIELDS = ("name", "kind", "supply_c", "target_c", "cp_kw_per_k")


def read_streams(path):
    """Load explicitly unit-labelled columns and report invalid CSV line numbers."""
    streams = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or len(reader.fieldnames) != len(FIELDS) or set(reader.fieldnames) != set(FIELDS):
            raise ValueError("CSV headers must be exactly: " + ",".join(FIELDS))
        for row in reader:
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("wrong number of columns")
                streams.append(Stream(
                    name=row["name"].strip(), kind=row["kind"].strip().lower(),
                    supply_c=float(row["supply_c"]), target_c=float(row["target_c"]),
                    cp_kw_per_k=float(row["cp_kw_per_k"]),
                ))
            except (ValueError, TypeError) as error:
                raise ValueError(f"CSV line {reader.line_num}: {error}") from error
    return streams


def parser():
    cli = argparse.ArgumentParser(description="CDU sensible-heat pinch targeting, ΔTmin sensitivity, and screening economics.")
    cli.add_argument("streams", type=Path, help="CSV: name,kind,supply_c,target_c,cp_kw_per_k")
    cli.add_argument("--dt-min", type=float, default=10, help="minimum temperature approach in °C (default: 10)")
    cli.add_argument("--sweep", default="5,10,15,20,30", help="comma-separated positive ΔTmin values in °C; selected value is included")
    cli.add_argument("--baseline-duty", type=float, help="measured useful heater duty in kW for the SAME stream boundary; enables savings estimates")
    cli.add_argument("--heater-efficiency", type=float, default=0.85, help="constant useful heat / fuel input, 0 < value <= 1 (default: 0.85)")
    cli.add_argument("--hours", type=float, default=8000, help="annual operating hours, 0 < hours <= 8760 (default: 8000)")
    cli.add_argument("--fuel-price", type=float, default=40, help="currency units per MWh of fuel input (default: 40)")
    cli.add_argument("--co2-factor", type=float, default=56.1, help="kg CO2 per GJ of fuel input (default: 56.1; illustrative natural-gas factor)")
    cli.add_argument("--retrofit-cost", type=float, help="capital cost in same currency as fuel price; enables simple payback")
    cli.add_argument("--data-note", help="provenance/limitations displayed prominently in reports")
    cli.add_argument("--json", dest="json_path", type=Path, default=Path("outputs/analysis.json"), help="JSON output path")
    cli.add_argument("--html", dest="html_path", type=Path, default=Path("outputs/report.html"), help="standalone HTML output path")
    return cli


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    try:
        paths = [args.streams.resolve(), args.json_path.resolve(), args.html_path.resolve()]
        if len(set(paths)) != 3:
            raise ValueError("input CSV, JSON output and HTML output must use different paths")
        streams = read_streams(args.streams)
        target = analyze(streams, args.dt_min)
        sweep_values = {float(value.strip()) for value in args.sweep.split(",")}
        if not sweep_values or any(not math.isfinite(value) or value <= 0 for value in sweep_values):
            raise ValueError("sweep values must be finite positive numbers")
        sweep_values.add(args.dt_min)
        sensitivity = []
        for delta in sorted(sweep_values):
            result = analyze(streams, delta)
            sensitivity.append({key: result[key] for key in ("dt_min_c", "hot_utility_kw", "cold_utility_kw", "heat_recovery_kw")})
        assumptions = {
            "baseline_heater_duty_kw": args.baseline_duty,
            "heater_efficiency": args.heater_efficiency,
            "operating_hours": args.hours,
            "fuel_price_per_mwh": args.fuel_price,
            "emission_factor_kg_co2_per_gj": args.co2_factor,
            "retrofit_cost": args.retrofit_cost,
        }
        # Validate all assumptions even when no baseline was supplied.
        estimate = estimate_savings(
            args.baseline_duty if args.baseline_duty is not None else 1,
            target["hot_utility_kw"],
            heater_efficiency=args.heater_efficiency, operating_hours=args.hours,
            fuel_price_per_mwh=args.fuel_price,
            emission_factor_kg_co2_per_gj=args.co2_factor, retrofit_cost=args.retrofit_cost,
        )
        economics = estimate if args.baseline_duty is not None else None
        sample = Path(__file__).resolve().parents[1] / "examples" / "streams.csv"
        note = args.data_note or ("Illustrative synthetic streams for demonstration only; not extracted from the supplied Aspen template or report."
                                  if paths[0] == sample else "User-supplied stream data; provenance and plant performance have not been independently validated.")
        payload = {"schema_version": 1, "data_note": note,
                   "streams": [asdict(stream) for stream in streams], "target": target,
                   "assumptions": assumptions, "economics": economics, "sensitivity": sensitivity}
        json_text = json.dumps(payload, indent=2, allow_nan=False) + "\n"
        html_text = render_report(payload)
        for path, content in ((args.json_path, json_text), (args.html_path, html_text)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        print(f"ΔTmin: {target['dt_min_c']:g} °C")
        print(f"Minimum hot utility: {target['hot_utility_kw']:.3f} kW")
        print(f"Minimum cold utility: {target['cold_utility_kw']:.3f} kW")
        print(f"Maximum heat recovery: {target['heat_recovery_kw']:.3f} kW")
        if economics is not None:
            print(f"Potential fuel savings: {economics['fuel_savings_percent']:.2f}%")
            print(f"Annual fuel cost savings: {economics['annual_cost_savings']:.2f} currency units/year")
            print(f"Annual CO2 savings: {economics['annual_co2_savings_tonnes']:.3f} tonnes/year")
        print(f"JSON: {args.json_path}\nHTML: {args.html_path}")
        print(note)
        return 0
    except (OSError, ValueError, OverflowError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
