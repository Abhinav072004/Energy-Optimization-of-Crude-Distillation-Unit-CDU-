"""Screening estimates from useful heater duties; no plant data is inferred."""

import math


def _number(name, value, *, minimum=0, maximum=None, exclusive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < minimum or (exclusive and value == minimum):
        relation = "greater than" if exclusive else "at least"
        raise ValueError(f"{name} must be {relation} {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be at most {maximum}")
    return float(value)


def estimate_savings(
    baseline_heater_duty_kw,
    target_heater_duty_kw,
    *,
    heater_efficiency=0.85,
    operating_hours=8000,
    fuel_price_per_mwh=40,
    emission_factor_kg_co2_per_gj=56.1,
    retrofit_cost=None,
):
    """Compare like-for-like useful duties at constant efficiency.

    Price is per MWh of fuel input, emissions per GJ of fuel input. Negative
    savings are retained when the target uses more energy than the baseline.
    All costs use the same user-selected currency. Simple payback excludes
    financing, maintenance, cooling utilities and taxes.
    """
    baseline = _number("baseline heater duty", baseline_heater_duty_kw, exclusive=True)
    target = _number("target heater duty", target_heater_duty_kw)
    efficiency = _number("heater efficiency", heater_efficiency, maximum=1, exclusive=True)
    hours = _number("operating hours", operating_hours, maximum=8760, exclusive=True)
    price = _number("fuel price", fuel_price_per_mwh)
    factor = _number("CO2 emission factor", emission_factor_kg_co2_per_gj)
    capital = None if retrofit_cost is None else _number("retrofit cost", retrofit_cost)
    thermal = baseline - target
    fuel_kw = thermal / efficiency
    fuel_mwh = fuel_kw * hours / 1000
    annual_cost = fuel_mwh * price
    result = {
        "baseline_heater_duty_kw": baseline,
        "target_heater_duty_kw": target,
        "thermal_savings_kw": thermal,
        "fuel_savings_kw": fuel_kw,
        "fuel_savings_mwh_per_year": fuel_mwh,
        "annual_cost_savings": annual_cost,
        "annual_co2_savings_tonnes": fuel_mwh * 3.6 * factor / 1000,
        "simple_payback_years": capital / annual_cost if capital is not None and annual_cost > 0 else None,
        "fuel_savings_percent": thermal / baseline * 100,
    }
    if not all(math.isfinite(v) for v in result.values() if v is not None):
        raise ValueError("economics inputs produce non-finite results; use smaller values")
    return result
