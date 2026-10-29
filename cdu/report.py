"""Self-contained, dependency-free HTML reports for CDU screening calculations."""

from __future__ import annotations

from html import escape
import math


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _number(value: float | None, precision: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:,.{precision}f}"


def _chart(
    chart_id: str,
    title: str,
    series: list[tuple[str, str, list[tuple[float, float]]]],
    x_label: str,
    y_label: str,
    *,
    zero_x: bool = False,
    zero_y: bool = False,
) -> str:
    """Draw a labeled line chart, including a useful scale for constant data."""
    points = [point for _, _, values in series for point in values]
    if not points:
        return '<p class="muted">No data available for this chart.</p>'
    if not all(math.isfinite(v) for point in points for v in point):
        raise ValueError("Charts require finite values.")
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    if zero_x:
        min_x = min(0.0, min_x)
    if zero_y:
        min_y = min(0.0, min_y)
    if max_x == min_x:
        max_x = min_x + max(abs(min_x) * 0.1, 1.0)
    if max_y == min_y:
        max_y = min_y + max(abs(min_y) * 0.1, 1.0)
    left, right, top, bottom = 83.0, 586.0, 28.0, 278.0

    def xy(x: float, y: float) -> tuple[float, float]:
        return (
            left + (x - min_x) / (max_x - min_x) * (right - left),
            bottom - (y - min_y) / (max_y - min_y) * (bottom - top),
        )

    elements = [
        f'<svg viewBox="0 0 620 350" role="img" aria-labelledby="{chart_id}-title {chart_id}-desc">',
        f'<title id="{chart_id}-title">{_text(title)}</title>',
        f'<desc id="{chart_id}-desc">{_text(x_label)} versus {_text(y_label)}. '
        'Data values are available in point tooltips and accompanying tables.</desc>',
    ]
    for i in range(5):
        fraction = i / 4
        x = min_x + fraction * (max_x - min_x)
        y = min_y + fraction * (max_y - min_y)
        px, py = xy(x, y)
        elements.extend([
            f'<line class="grid" x1="{left}" y1="{py:.2f}" x2="{right}" y2="{py:.2f}"/>',
            f'<text class="tick" x="{left - 10}" y="{py + 4:.2f}" text-anchor="end">{_number(y)}</text>',
            f'<text class="tick" x="{px:.2f}" y="{bottom + 23}" text-anchor="middle">{_number(x)}</text>',
        ])
    elements.extend([
        f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{bottom}"/>',
        f'<line class="axis" x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}"/>',
        f'<text class="axis-label" x="{(left + right) / 2}" y="337" text-anchor="middle">{_text(x_label)}</text>',
        f'<text class="axis-label" transform="translate(18 153) rotate(-90)" text-anchor="middle">{_text(y_label)}</text>',
    ])
    for name, color, values in series:
        coordinates = " ".join(f"{xy(x, y)[0]:.2f},{xy(x, y)[1]:.2f}" for x, y in values)
        elements.append(f'<polyline points="{coordinates}" fill="none" stroke="{color}" stroke-width="3"/>')
        for x, y in values:
            px, py = xy(x, y)
            tooltip = f"{name}: {x_label} = {_number(x)}, {y_label} = {_number(y)}"
            elements.append(
                f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="{color}">'
                f'<title>{_text(tooltip)}</title></circle>'
            )
    elements.append("</svg>")
    elements.append('<div class="legend">')
    for name, color, _ in series:
        elements.append(f'<span><i style="background:{color}"></i>{_text(name)}</span>')
    elements.append("</div>")
    return "".join(elements)


def _card(label: str, value: float, unit: str, note: str = "") -> str:
    return (
        f'<article class="metric"><span>{_text(label)}</span>'
        f'<strong>{_number(value)} <small>{_text(unit)}</small></strong>'
        f'<p>{_text(note)}</p></article>'
    )


def render_report(payload: dict) -> str:
    """Render a portable scientific screening report without external assets.

    All supplied text is escaped. Thermal quantities use kW, temperatures °C;
    economic amounts use the same unspecified currency as the supplied fuel price.
    """
    target = payload["target"]
    assumptions = payload["assumptions"]
    economics = payload.get("economics")
    sensitivity = payload.get("sensitivity", [])
    cascade = target["cascade"]
    gcc = []
    if cascade:
        gcc = [(target["hot_utility_kw"], cascade[0]["upper_shifted_c"])]
        gcc.extend((row["residual_kw"], row["lower_shifted_c"]) for row in cascade)
    gcc_chart = _chart(
        "gcc", "Grand composite curve", [("Corrected heat cascade", "#087f8c", gcc)],
        "Net heat flow (kW)", "Shifted temperature (°C)", zero_x=True,
    )
    sensitivity_chart = _chart(
        "sensitivity", "Minimum utility demand versus temperature approach",
        [
            ("Hot utility", "#c87926", [(row["dt_min_c"], row["hot_utility_kw"]) for row in sensitivity]),
            ("Cold utility", "#087f8c", [(row["dt_min_c"], row["cold_utility_kw"]) for row in sensitivity]),
        ], "Minimum approach ΔTmin (°C)", "Minimum utility duty (kW)", zero_y=True,
    )
    cards = "".join([
        _card("Minimum hot utility", target["hot_utility_kw"], "kW", "External heat target"),
        _card("Minimum cold utility", target["cold_utility_kw"], "kW", "External cooling target"),
        _card("Maximum heat recovery", target["heat_recovery_kw"], "kW", "Thermodynamic recovery target"),
        _card("Temperature approach", target["dt_min_c"], "°C", "Selected ΔTmin"),
    ])
    stream_rows = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in [
            _text(row["name"]), _text(row["kind"]), _number(row["supply_c"]),
            _number(row["target_c"]), _number(row["cp_kw_per_k"], 3),
            _number(abs(row["supply_c"] - row["target_c"]) * row["cp_kw_per_k"]),
        ]) + "</tr>"
        for row in payload["streams"]
    )
    sensitivity_rows = "".join(
        f'<tr><td>{_number(row["dt_min_c"])}</td><td>{_number(row["hot_utility_kw"])}</td>'
        f'<td>{_number(row["cold_utility_kw"])}</td><td>{_number(row["heat_recovery_kw"])}</td></tr>'
        for row in sensitivity
    )
    pinch_rows = "".join(
        f'<tr><td>{_number(row["shifted_c"])}</td><td>{_number(row["hot_c"])}</td>'
        f'<td>{_number(row["cold_c"])}</td></tr>'
        for row in target["pinch_points"]
    )
    if pinch_rows:
        pinch_section = (
            '<div class="table-wrap"><table><caption>Zero-residual pinch locations</caption>'
            '<thead><tr><th>Shifted (°C)</th><th>Hot side (°C)</th><th>Cold side (°C)</th></tr></thead>'
            f'<tbody>{pinch_rows}</tbody></table></div>'
        )
    else:
        pinch_section = '<p class="muted">No zero-residual pinch locations were reported.</p>'
    economics_section = (
        '<p class="muted">Provide <code>--baseline-duty</code> to estimate potential fuel, cost, '
        'and CO₂ savings against your current heater duty.</p>'
    )
    if economics is not None:
        payback = economics["simple_payback_years"]
        payback_text = f"{_number(payback, 2)} years" if payback is not None else "Not available"
        economics_section = '<div class="metrics economics">' + "".join([
            _card("Potential fuel reduction", economics["fuel_savings_percent"], "%", "Relative to supplied baseline"),
            _card("Annual fuel savings", economics["fuel_savings_mwh_per_year"], "MWh/year"),
            _card("Annual cost savings", economics["annual_cost_savings"], "currency/year"),
            _card("Annual CO₂ reduction", economics["annual_co2_savings_tonnes"], "t CO₂/year"),
        ]) + '</div>' + (
            '<dl class="assumptions">'
            f'<div><dt>Baseline heater duty</dt><dd>{_number(economics["baseline_heater_duty_kw"])} kW</dd></div>'
            f'<div><dt>Screening heater target</dt><dd>{_number(economics["target_heater_duty_kw"])} kW</dd></div>'
            f'<div><dt>Thermal duty reduction</dt><dd>{_number(economics["thermal_savings_kw"])} kW</dd></div>'
            f'<div><dt>Simple payback</dt><dd>{payback_text}</dd></div></dl>'
        )
    cost = assumptions.get("retrofit_cost")
    cost_text = f"{_number(cost)} currency units" if cost is not None else "Not supplied"
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CDU energy optimization · Screening report</title>
<style>
:root{{--ink:#193041;--muted:#576a76;--teal:#087f8c;--line:#d9e2e4;--paper:#fff;--background:#f4f4ee}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--background);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1320px;margin:auto;padding:42px 36px 24px}}header{{padding-bottom:24px}}.eyebrow{{color:var(--teal);font-size:12px;letter-spacing:.15em;text-transform:uppercase;font-weight:750}}h1{{font-size:clamp(30px,4vw,48px);line-height:1.1;letter-spacing:-.04em;margin:12px 0}}h2{{font-size:22px;line-height:1.25;margin:0 0 10px}}h3{{font-size:16px;margin:25px 0 8px}}p{{margin:8px 0}}.subtitle,.muted{{color:var(--muted)}}.notice{{border-left:4px solid #c87926;background:#fff7e9;padding:14px 18px;border-radius:0 8px 8px 0;margin-bottom:24px;overflow-wrap:anywhere}}.notice strong{{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.08em}}.metrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-bottom:24px}}.metric,.panel{{background:var(--paper);border:1px solid var(--line);border-radius:12px}}.metric{{padding:20px}}.metric>span{{font-size:13px;color:var(--muted)}}.metric strong{{display:block;font-size:30px;letter-spacing:-.03em;line-height:1.3;margin-top:8px}}.metric small{{font-size:14px;font-weight:500;color:var(--muted);letter-spacing:0}}.metric p{{font-size:12px;color:var(--muted);min-height:18px}}.columns{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}}.panel{{padding:24px;margin-bottom:24px;min-width:0}}.columns>.panel{{margin:0}}.panel>p{{font-size:14px}}svg{{display:block;width:100%;height:auto;margin-top:14px}}.grid{{stroke:#e8edef;stroke-width:1}}.axis{{stroke:#91a2aa;stroke-width:1}}.tick{{font-size:11px;fill:#576a76}}.axis-label{{font-size:12px;fill:#193041}}.legend{{display:flex;gap:20px;flex-wrap:wrap;font-size:12px;color:var(--muted);padding-left:12px}}.legend span{{display:flex;align-items:center;gap:7px}}.legend i{{display:inline-block;width:16px;height:3px}}.table-wrap{{overflow:auto}}table{{border-collapse:collapse;text-align:right;font-size:14px;width:100%;margin-top:16px}}caption{{text-align:left;font-size:13px;color:var(--muted);margin-bottom:10px}}th,td{{padding:11px 14px;border-bottom:1px solid var(--line);white-space:nowrap}}th{{font-size:12px;color:var(--muted);font-weight:600;background:#f7faf9}}th:first-child,td:first-child{{text-align:left}}tbody tr:last-child td{{border-bottom:0}}.assumptions{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px 24px;margin:20px 0 0}}.assumptions div{{border-top:1px solid var(--line);padding-top:10px}}dt{{font-size:12px;color:var(--muted)}}dd{{margin:3px 0 0;font-size:15px}}.economics .metric{{background:#f5faf9}}.caveat{{border-left:3px solid var(--teal);padding-left:16px;color:var(--muted);font-size:14px;margin-top:22px}}footer{{font-size:12px;color:var(--muted);padding:0 0 18px}}code{{font-size:.9em}}
@media(max-width:900px){{.metrics{{grid-template-columns:1fr 1fr}}.columns{{grid-template-columns:1fr}}.assumptions{{grid-template-columns:1fr 1fr}}}}
@media(max-width:520px){{main{{padding:24px 14px}}.panel{{padding:18px 12px}}.metric{{padding:15px}}.metric strong{{font-size:25px}}.assumptions{{grid-template-columns:1fr}}}}
@media print{{body{{background:#fff}}main{{padding:0}}.panel,.metric{{break-inside:avoid}}.metrics{{gap:8px}}.columns{{display:block}}.columns>.panel{{margin-bottom:20px}}}}
</style></head><body><main>
<header><div class="eyebrow">Crude distillation unit / energy analysis</div><h1>Heat recovery, quantified.</h1>
<p class="subtitle">Pinch targeting, temperature-approach sensitivity, and potential operating savings.</p></header>
<div class="notice"><strong>Data basis</strong>{_text(payload.get("data_note", "User-supplied stream data; verify against validated process measurements."))}</div>
<section class="metrics" aria-label="Thermal targets">{cards}</section>
<div class="columns"><section class="panel"><h2>Grand composite curve</h2>
<p class="muted">Corrected heat cascade at ΔTmin = {_number(target["dt_min_c"])} °C. Internal zero heat residuals identify pinch boundaries; endpoint zeros indicate utility thresholds.</p>{gcc_chart}</section>
<section class="panel"><h2>Temperature-approach sensitivity</h2><p class="muted">Compare utility targets across ΔTmin. Exchanger area and capital cost are not modeled.</p>{sensitivity_chart}</section></div>
<section class="panel"><h2>Operating savings potential</h2><p class="muted">Screening estimates compare the hot utility target with your supplied heater baseline, at constant efficiency.</p>{economics_section}
<h3>Economic assumptions</h3><dl class="assumptions">
<div><dt>Heater efficiency</dt><dd>{_number(assumptions["heater_efficiency"] * 100)}%</dd></div>
<div><dt>Annual operating time</dt><dd>{_number(assumptions["operating_hours"], 0)} hours/year</dd></div>
<div><dt>Fuel price</dt><dd>{_number(assumptions["fuel_price_per_mwh"], 2)} currency/MWh fuel</dd></div>
<div><dt>Direct combustion emission factor</dt><dd>{_number(assumptions["emission_factor_kg_co2_per_gj"], 2)} kg CO₂/GJ fuel</dd></div>
<div><dt>Retrofit investment</dt><dd>{cost_text}</dd></div></dl>
<div class="caveat">These are potential savings against the supplied baseline, not measured plant improvements. The baseline must cover the same stream system as the hot utility target. Prices and investment must use the same currency. Payback excludes maintenance, discounting, and exchanger design costs unless included in your investment.</div></section>
<div class="columns"><section class="panel"><h2>Pinch temperatures</h2><p class="muted">Hot streams shift down by ΔTmin/2; cold streams shift up by ΔTmin/2.</p>{pinch_section}</section>
<section class="panel"><h2>Utility comparison</h2><div class="table-wrap"><table><caption>Temperature-approach sweep</caption><thead><tr><th>ΔTmin (°C)</th><th>Hot (kW)</th><th>Cold (kW)</th><th>Recovery (kW)</th></tr></thead><tbody>{sensitivity_rows}</tbody></table></div></section></div>
<section class="panel"><h2>Stream inventory</h2><p class="muted">Heat-capacity flow rate CP = mass flow × specific heat; all duties use sensible heat with constant CP.</p>
<div class="table-wrap"><table><caption>Input temperatures, heat-capacity flow rates, and calculated stream duties</caption><thead><tr><th>Stream</th><th>Type</th><th>Supply (°C)</th><th>Target (°C)</th><th>CP (kW/K)</th><th>Duty (kW)</th></tr></thead><tbody>{stream_rows}</tbody></table></div>
<div class="caveat">Thermodynamic targeting assumes constant heat-capacity flow rates, no phase changes, and unrestricted matching between included streams. For variable properties, provide sensible-heat segments. Results do not size a heat exchanger network or verify HYSYS convergence, column yields, pressure drops, control stability, or the original project's claimed 12% fuel reduction.</div></section>
<footer>CDU portable analysis · Report schema {_text(payload.get("schema_version", 1))} · Self-contained report; no external services or assets.</footer>
</main></body></html>'''
