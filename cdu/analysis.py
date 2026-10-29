"""Minimum-utility targeting using the pinch-analysis heat cascade.

Temperatures are in degrees Celsius, heat-capacity flow rates in kW/K, and
thermal duties in kW. Streams represent sensible heating or cooling with a
constant heat-capacity flow rate; phase changes and exchanger sizing require
additional models.
"""

from dataclasses import dataclass
import math
from numbers import Real
from typing import Iterable


@dataclass(frozen=True)
class Stream:
    """One sensible process-stream segment with positive heat-capacity flow."""

    name: str
    kind: str
    supply_c: float
    target_c: float
    cp_kw_per_k: float


def _number(value: Real, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{label} must be a finite number") from error
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    return result


def _finite(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("Stream values exceed the supported numeric range")
    return value


def analyze(streams: Iterable[Stream], dt_min_c: float) -> dict:
    """Return thermodynamic utility targets and the corrected heat cascade.

    Shift hot temperatures down by half ΔTmin and cold temperatures up by half
    ΔTmin. Cascade each interval's net available heat downward; the most
    negative uncorrected residual fixes the minimum hot utility. Its addition
    makes every residual nonnegative, with the bottom residual equal to the
    minimum cold utility.

    ``pinch_points`` reports internal shifted-temperature boundaries where the
    corrected cascade is zero within numerical tolerance. Top and bottom
    boundary zeros are excluded: those describe utility-threshold conditions.
    For a zero-residual plateau, its internal boundary temperatures are listed;
    a unique pinch temperature must not be inferred from such a plateau.

    Targets assume unrestricted thermodynamically feasible heat exchange and
    sufficiently hot/cold utilities. They are not a network design or evidence
    of an installed plant's achievable savings.
    """
    delta_t = _number(dt_min_c, "ΔTmin")
    if delta_t <= 0:
        raise ValueError("ΔTmin must be greater than zero")
    try:
        stream_list = list(streams)
    except TypeError as error:
        raise ValueError("streams must be an iterable of Stream objects") from error
    if not stream_list:
        raise ValueError("At least one hot and one cold stream are required")

    shifted = []
    names = set()
    kinds = set()
    hot_duties = []
    cold_duties = []
    for stream in stream_list:
        if not isinstance(stream, Stream):
            raise ValueError("Every stream must be a Stream object")
        if not isinstance(stream.name, str) or not stream.name.strip():
            raise ValueError("Every stream must have a nonempty name")
        name = stream.name.strip()
        if name in names:
            raise ValueError(f"Duplicate stream name: {name}")
        names.add(name)
        if stream.kind not in ("hot", "cold"):
            raise ValueError(f"{name}: kind must be 'hot' or 'cold'")
        kinds.add(stream.kind)
        supply = _number(stream.supply_c, f"{name}: supply_c")
        target = _number(stream.target_c, f"{name}: target_c")
        cp = _number(stream.cp_kw_per_k, f"{name}: cp_kw_per_k")
        if cp <= 0:
            raise ValueError(f"{name}: cp_kw_per_k must be greater than zero")
        if stream.kind == "hot":
            if supply <= target:
                raise ValueError(f"{name}: a hot stream must cool (supply_c > target_c)")
            upper = _finite(supply - delta_t / 2)
            lower = _finite(target - delta_t / 2)
            hot_duties.append(_finite(cp * (supply - target)))
        else:
            if supply >= target:
                raise ValueError(f"{name}: a cold stream must heat (supply_c < target_c)")
            upper = _finite(target + delta_t / 2)
            lower = _finite(supply + delta_t / 2)
            cold_duties.append(_finite(cp * (target - supply)))
        if upper <= lower:
            raise ValueError(f"{name}: shifted temperature span is below numeric precision")
        shifted.append((stream.kind, upper, lower, cp))
    if kinds != {"hot", "cold"}:
        raise ValueError("At least one hot and one cold stream are required")

    try:
        total_hot = _finite(math.fsum(hot_duties))
        total_cold = _finite(math.fsum(cold_duties))
        temperatures = sorted({t for _, upper, lower, _ in shifted for t in (upper, lower)}, reverse=True)
        raw_residuals = [0.0]
        cascade = []
        for upper, lower in zip(temperatures, temperatures[1:]):
            # Every endpoint belongs to the interval partition; no midpoint
            # interpolation is needed to decide which streams cross it.
            net_cp = _finite(math.fsum(
                cp if kind == "hot" else -cp
                for kind, high, low, cp in shifted
                if high >= upper and low <= lower
            ))
            heat = _finite(net_cp * _finite(upper - lower))
            residual = _finite(math.fsum((raw_residuals[-1], heat)))
            raw_residuals.append(residual)
            cascade.append({
                "upper_shifted_c": upper,
                "lower_shifted_c": lower,
                "net_cp_kw_per_k": net_cp,
                "interval_heat_kw": heat,
            })
        hot_utility = max(0.0, -min(raw_residuals))
        tolerance = max(1.0, total_hot, total_cold) * 1e-10
        corrected = []
        for residual in raw_residuals:
            value = _finite(math.fsum((residual, hot_utility)))
            corrected.append(0.0 if abs(value) <= tolerance else value)
        cold_utility = corrected[-1]
        recovery = _finite(total_cold - hot_utility)
        if abs(recovery) <= tolerance:
            recovery = 0.0
        for interval, residual in zip(cascade, corrected[1:]):
            interval["residual_kw"] = residual
        pinch_points = [
            {
                "shifted_c": temperature,
                "hot_c": _finite(temperature + delta_t / 2),
                "cold_c": _finite(temperature - delta_t / 2),
            }
            for temperature, residual in zip(temperatures[1:-1], corrected[1:-1])
            if residual == 0.0
        ]
    except OverflowError as error:
        raise ValueError("Stream values exceed the supported numeric range") from error

    return {
        "dt_min_c": delta_t,
        "hot_utility_kw": hot_utility,
        "cold_utility_kw": cold_utility,
        "heat_recovery_kw": recovery,
        "total_hot_duty_kw": total_hot,
        "total_cold_duty_kw": total_cold,
        "pinch_points": pinch_points,
        "cascade": cascade,
    }
