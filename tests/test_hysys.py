import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from cdu.hysys import export_case
from cdu.cli import main as analyze_main
import hysys_export


class Property:
    def __init__(self, value, expected_unit):
        self.value = value
        self.expected_unit = expected_unit
        self.reads = []

    def GetValue(self, unit):
        if unit != self.expected_unit:
            raise AssertionError(f"Expected {self.expected_unit}, received {unit}")
        self.reads.append(unit)
        return self.value


def material(temperature, flow, enthalpy):
    return types.SimpleNamespace(Temperature=Property(temperature, "C"),
                                 MassFlow=Property(flow, "kg/s"),
                                 MassEnthalpy=Property(enthalpy, "kJ/kg"))


class Collection:
    def __init__(self, streams):
        self.streams = streams

    def Item(self, name):
        return self.streams[name]


class HysysExportTests(unittest.TestCase):
    def setUp(self):
        self.mapping = {"confirmed_solved": True, "streams": [
            {"name": "crude", "kind": "cold", "inlet": "C_IN", "outlet": "C_OUT", "sensible_only": True},
            {"name": "diesel", "kind": "hot", "inlet": "H_IN", "outlet": "H_OUT", "sensible_only": True},
        ]}
        self.materials = {"C_IN": material(20, 2, 100), "C_OUT": material(120, 2, 300),
                          "H_IN": material(200, 3, 500), "H_OUT": material(80, 3, 260)}
        self.app = types.SimpleNamespace(ActiveDocument=types.SimpleNamespace(
            Title="Test case", Flowsheet=types.SimpleNamespace(MaterialStreams=Collection(self.materials))))

    def test_extracts_unit_explicit_cp_and_provenance(self):
        streams, metadata = export_case(self.mapping, self.app)
        self.assertEqual(streams[0].cp_kw_per_k, 4)
        self.assertEqual(streams[1].cp_kw_per_k, 6)
        self.assertEqual(metadata["streams"][0]["thermal_duty_kw"], 400)
        self.assertEqual(metadata["streams"][1]["thermal_duty_kw"], 720)
        self.assertIn("not programmatically verified", metadata["solved_state"])
        self.assertEqual(metadata["case_title"], "Test case")
        self.assertTrue(metadata["exported_at_utc"].endswith("+00:00"))
        self.assertEqual(self.materials["C_IN"].MassFlow.reads, ["kg/s"])
        json.dumps(metadata, allow_nan=False)

    def test_requires_explicit_user_attestations(self):
        for key in ("confirmed_solved", "sensible_only"):
            mapping = copy.deepcopy(self.mapping)
            if key == "confirmed_solved":
                mapping[key] = False
            else:
                mapping["streams"][0][key] = False
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                export_case(mapping, self.app)

    def test_missing_case_and_stream_are_actionable(self):
        with self.assertRaisesRegex(ValueError, "active HYSYS case"):
            export_case(self.mapping, types.SimpleNamespace(ActiveDocument=None))
        self.mapping["streams"][0]["inlet"] = "MISSING"
        with self.assertRaisesRegex(ValueError, "MISSING"):
            export_case(self.mapping, self.app)

    def test_rejects_mass_imbalance(self):
        self.materials["C_OUT"].MassFlow.value = 2.01
        with self.assertRaisesRegex(ValueError, "0.1%"):
            export_case(self.mapping, self.app)

    def test_tolerates_small_mass_rounding(self):
        self.materials["C_OUT"].MassFlow.value = 2.001
        streams, _ = export_case(self.mapping, self.app)
        self.assertEqual(streams[0].cp_kw_per_k, 4)

    def test_rejects_unknown_reverse_and_nonfinite_values(self):
        for value in (None, -1, 0, float("nan"), float("inf"), True):
            self.materials["C_IN"].MassFlow.value = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                export_case(self.mapping, self.app)

    def test_rejects_temperature_enthalpy_direction_disagreement(self):
        for property_name, value in (("Temperature", 20), ("Temperature", 10), ("MassEnthalpy", 80)):
            self.setUp()
            getattr(self.materials["C_OUT"], property_name).value = value
            with self.subTest(property=property_name, value=value), self.assertRaisesRegex(ValueError, "cold segment"):
                export_case(self.mapping, self.app)

    def test_rejects_duplicate_names_pairs_and_single_kind(self):
        mutations = [lambda m: m["streams"][1].update(name="crude"),
                     lambda m: m["streams"][1].update(inlet="C_OUT", outlet="C_IN"),
                     lambda m: m["streams"][1].update(kind="cold")]
        for mutation in mutations:
            mapping = copy.deepcopy(self.mapping)
            mutation(mapping)
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                export_case(mapping, self.app)

    def test_missing_api_property_does_not_silently_skip(self):
        del self.materials["C_IN"].MassEnthalpy
        with self.assertRaisesRegex(ValueError, "MassEnthalpy.*kJ/kg"):
            export_case(self.mapping, self.app)

    def test_non_windows_message_and_no_com_dependency(self):
        with patch("cdu.hysys.sys.platform", "linux"):
            with self.assertRaisesRegex(ValueError, "requires Windows"):
                export_case(self.mapping)

    def test_attaches_to_running_application_without_launch_or_writes(self):
        package = types.ModuleType("win32com")
        package.__path__ = []
        client = types.ModuleType("win32com.client")
        client.GetActiveObject = Mock(return_value=self.app)
        client.Dispatch = Mock(side_effect=AssertionError("Must not launch HYSYS"))
        package.client = client
        with patch("cdu.hysys.sys.platform", "win32"), patch.dict("sys.modules", {"win32com": package, "win32com.client": client}):
            streams, _ = export_case(self.mapping)
        self.assertEqual(len(streams), 2)
        client.GetActiveObject.assert_called_once_with("HYSYS.Application")
        client.Dispatch.assert_not_called()

    def test_unknown_temperature_sentinel_is_rejected(self):
        self.materials["C_IN"].Temperature.value = -32767
        with self.assertRaisesRegex(ValueError, "below absolute zero"):
            export_case(self.mapping, self.app)

    def test_case_title_property_value(self):
        self.app.ActiveDocument.Title = types.SimpleNamespace(Value="Property title")
        _, metadata = export_case(self.mapping, self.app)
        self.assertEqual(metadata["case_title"], "Property title")

    def test_cli_exports_csv_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mapping = root / "mapping.json"
            output, metadata = root / "streams.csv", root / "provenance.json"
            mapping.write_text(json.dumps(self.mapping))
            with patch("hysys_export.export_case", side_effect=lambda m: export_case(m, self.app)), contextlib.redirect_stdout(io.StringIO()):
                code = hysys_export.main(["--map", str(mapping), "--output", str(output), "--metadata", str(metadata)])
            self.assertEqual(code, 0)
            self.assertIn("name,kind,supply_c,target_c,cp_kw_per_k", output.read_text())
            self.assertIn("crude,cold,20.0,120.0,4.0", output.read_text())
            self.assertEqual(json.loads(metadata.read_text())["case_title"], "Test case")
            # Exercise the real export-to-analysis boundary, not just CSV syntax.
            report_json, report_html = root / "analysis.json", root / "report.html"
            with contextlib.redirect_stdout(io.StringIO()):
                code = analyze_main([str(output), "--dt-min", "20", "--json", str(report_json), "--html", str(report_html)])
            self.assertEqual(code, 0)
            target = json.loads(report_json.read_text())["target"]
            self.assertAlmostEqual(target["hot_utility_kw"], 0)
            self.assertAlmostEqual(target["cold_utility_kw"], 320)
            self.assertAlmostEqual(target["heat_recovery_kw"], 400)
            self.assertIn("Grand composite curve", report_html.read_text())

    def test_cli_failed_extraction_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mapping = root / "mapping.json"
            output, metadata = root / "streams.csv", root / "provenance.json"
            mapping.write_text(json.dumps(self.mapping))
            output.write_text("previous CSV")
            metadata.write_text("previous metadata")
            with patch("hysys_export.export_case", side_effect=ValueError("Unsolved stream")), contextlib.redirect_stderr(io.StringIO()):
                code = hysys_export.main(["--map", str(mapping), "--output", str(output), "--metadata", str(metadata)])
            self.assertEqual(code, 2)
            self.assertEqual(output.read_text(), "previous CSV")
            self.assertEqual(metadata.read_text(), "previous metadata")

    def test_cli_refuses_output_overwriting_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            mapping = Path(tmp) / "mapping.json"
            mapping.write_text(json.dumps(self.mapping))
            with contextlib.redirect_stderr(io.StringIO()):
                code = hysys_export.main(["--map", str(mapping), "--output", str(mapping)])
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
