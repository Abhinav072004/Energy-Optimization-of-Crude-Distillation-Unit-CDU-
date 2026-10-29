"""Read-only export of sensible stream segments from a running Aspen HYSYS case.

This module never opens/saves cases, changes the solver, or writes COM properties.
An inlet/outlet pair must represent the same material through sensible heating or
cooling: no mixing, splitting, reaction or phase change. The user must confirm a
converged, stable case and pause dynamics before export; the COM reads cannot
certify convergence or provide an atomic snapshot of a changing simulation.
"""

from datetime import datetime, timezone
import math
from numbers import Real
import sys

from .analysis import Stream


MASS_FLOW_RELATIVE_TOLERANCE = 1e-3


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label}: expected a finite numeric value from HYSYS")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label}: HYSYS returned a non-finite value")
    return number


def _mapping(mapping):
    if not isinstance(mapping, dict):
        raise ValueError("HYSYS mapping must be a JSON object")
    if mapping.get("confirmed_solved") is not True:
        raise ValueError("Confirm the case is solved and stable, pause dynamics, then set confirmed_solved to true in the mapping")
    pairs = mapping.get("streams")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("Mapping streams must be a nonempty list of inlet/outlet pairs")
    normalized = []
    names = set()
    sources = set()
    for index, pair in enumerate(pairs, 1):
        if not isinstance(pair, dict):
            raise ValueError(f"Mapping stream {index} must be an object")
        item = {}
        for key in ("name", "kind", "inlet", "outlet"):
            value = pair.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Mapping stream {index}: {key} must be a nonempty string")
            item[key] = value.strip()
        if item["kind"] not in ("hot", "cold"):
            raise ValueError(f"{item['name']}: kind must be hot or cold")
        if item["name"] in names:
            raise ValueError(f"Duplicate mapping name: {item['name']}")
        if item["inlet"] == item["outlet"]:
            raise ValueError(f"{item['name']}: inlet and outlet must be different streams")
        source = (item["inlet"], item["outlet"])
        if source in sources or source[::-1] in sources:
            raise ValueError(f"{item['name']}: duplicate inlet/outlet pair would double-count heat")
        if pair.get("sensible_only") is not True:
            raise ValueError(f"{item['name']}: confirm no phase change, mixing, splitting or reaction and set sensible_only to true")
        names.add(item["name"])
        sources.add(source)
        item["sensible_only"] = True
        normalized.append(item)
    if {pair["kind"] for pair in normalized} != {"hot", "cold"}:
        raise ValueError("Mapping must contain at least one hot and one cold stream segment")
    return normalized


def _active_application():
    if sys.platform != "win32":
        raise ValueError("Live HYSYS export requires Windows with licensed Aspen HYSYS. Run this exporter on the Windows machine; CSV analysis works on Linux.")
    try:
        import win32com.client
    except ImportError as error:
        raise ValueError("Install pywin32 in your Windows Python environment: py -3 -m pip install pywin32") from error
    try:
        return win32com.client.GetActiveObject("HYSYS.Application")
    except Exception as error:
        raise ValueError("Cannot attach to a running HYSYS application. Open your licensed HYSYS case first and use Python in the same Windows user session.") from error


def _state(material_streams, name):
    try:
        stream = material_streams.Item(name)
        if stream is None:
            raise ValueError("stream not found")
    except Exception as error:
        raise ValueError(f"Cannot find HYSYS material stream {name!r}; edit inlet/outlet names in the mapping") from error
    result = {}
    for field, property_name, unit in (
        ("temperature_c", "Temperature", "C"),
        ("mass_flow_kg_per_s", "MassFlow", "kg/s"),
        ("mass_enthalpy_kj_per_kg", "MassEnthalpy", "kJ/kg"),
    ):
        try:
            value = getattr(stream, property_name).GetValue(unit)
        except Exception as error:
            raise ValueError(f"Cannot read {name!r}.{property_name}.GetValue({unit!r}); verify the stream is solved and the installed HYSYS Automation API supports these properties and units") from error
        result[field] = _number(value, f"{name}.{property_name}")
    if result["temperature_c"] < -273.15:
        raise ValueError(f"{name}: temperature is below absolute zero; the property may be unknown or use an unsupported unit")
    if result["mass_flow_kg_per_s"] <= 0:
        raise ValueError(f"{name}: mass flow must be positive; zero, reverse or unknown flow cannot define a sensible segment")
    return result


def export_case(mapping, application=None):
    """Return ``(streams, metadata)`` without altering the active simulation.

    ``application`` may be injected for offline tests. Otherwise this attaches
    with GetActiveObject, requiring Windows and optional pywin32. Each exported
    CP is an effective constant value, mdot * Δh / ΔT. Inlet mass flow is used;
    outlet flow must match within 0.1% relative to the larger flow. This average
    CP approximation does not capture temperature-dependent heat capacity.
    """
    pairs = _mapping(mapping)
    application = _active_application() if application is None else application
    try:
        case = application.ActiveDocument
        if case is None:
            raise ValueError("no active document")
        material_streams = case.Flowsheet.MaterialStreams
    except Exception as error:
        raise ValueError("No accessible active HYSYS case/flowsheet. Open a solved case before exporting.") from error
    try:
        title = case.Title
        if not isinstance(title, str):
            title = title.Value
        if not isinstance(title, str):
            title = "Active HYSYS case (title unavailable)"
    except Exception:
        title = "Active HYSYS case (title unavailable)"

    streams = []
    evidence = []
    for pair in pairs:
        inlet = _state(material_streams, pair["inlet"])
        outlet = _state(material_streams, pair["outlet"])
        inlet_flow = inlet["mass_flow_kg_per_s"]
        outlet_flow = outlet["mass_flow_kg_per_s"]
        if abs(inlet_flow - outlet_flow) > MASS_FLOW_RELATIVE_TOLERANCE * max(inlet_flow, outlet_flow):
            raise ValueError(f"{pair['name']}: inlet/outlet mass flows differ by more than 0.1%; mixing, splitting or inconsistent snapshots are unsupported")
        supply = inlet["temperature_c"]
        target = outlet["temperature_c"]
        delta_t = target - supply
        delta_h = outlet["mass_enthalpy_kj_per_kg"] - inlet["mass_enthalpy_kj_per_kg"]
        if pair["kind"] == "cold" and (delta_t <= 0 or delta_h <= 0):
            raise ValueError(f"{pair['name']}: a cold segment must increase both temperature and specific enthalpy")
        if pair["kind"] == "hot" and (delta_t >= 0 or delta_h >= 0):
            raise ValueError(f"{pair['name']}: a hot segment must decrease both temperature and specific enthalpy")
        cp = inlet_flow * delta_h / delta_t
        if not math.isfinite(cp) or cp <= 0:
            raise ValueError(f"{pair['name']}: effective heat-capacity flow is non-finite or non-positive")
        duty = inlet_flow * abs(delta_h)
        if not math.isfinite(duty):
            raise ValueError(f"{pair['name']}: thermal duty exceeds the supported numeric range")
        streams.append(Stream(pair["name"], pair["kind"], supply, target, cp))
        evidence.append({"mapping": pair, "inlet_state": inlet, "outlet_state": outlet,
                         "effective_cp_kw_per_k": cp, "thermal_duty_kw": duty})
    metadata = {
        "schema_version": 1,
        "case_title": title,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "read-only active-case COM; effective CP = inlet mass flow * enthalpy change / temperature change",
        "solved_state": "user-confirmed; not programmatically verified",
        "sensible_segments": "user-confirmed; no phase change, mixing, splitting or reaction",
        "mass_flow_relative_tolerance": MASS_FLOW_RELATIVE_TOLERANCE,
        "units": {"temperature": "C", "mass_flow": "kg/s", "mass_enthalpy": "kJ/kg", "cp": "kW/K", "duty": "kW"},
        "limitations": ["Pause dynamics and do not edit the case during export; sequential COM reads are not an atomic snapshot.",
                        "Effective constant CP is an approximation; segment temperature-dependent CP data separately.",
                        "Export does not verify case convergence, design a heat exchanger network, or validate fuel savings."],
        "streams": evidence,
    }
    return streams, metadata
