"""Exercise the public executable against temporary CSV and report files."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "cdu_pinch_analysis.py"
EXAMPLE = ROOT / "examples" / "streams.csv"
HEADER = "name,kind,supply_c,target_c,cp_kw_per_k\n"


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cdu-cli-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.json_path = self.directory / "results" / "analysis.json"
        self.html_path = self.directory / "results" / "report.html"

    def run_cli(self, source=EXAMPLE, *arguments):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(source), "--json", str(self.json_path),
             "--html", str(self.html_path), *arguments],
            cwd=self.directory, text=True, capture_output=True, timeout=20,
        )

    def assert_clean_error(self, result):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.json_path.exists())
        self.assertFalse(self.html_path.exists())

    def test_example_generates_json_and_standalone_html_without_baseline(self):
        result = self.run_cli(EXAMPLE, "--dt-min", "20")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(self.json_path.read_text())
        self.assertAlmostEqual(payload["target"]["hot_utility_kw"], 29)
        self.assertAlmostEqual(payload["target"]["cold_utility_kw"], 60)
        self.assertAlmostEqual(payload["target"]["heat_recovery_kw"], 355)
        self.assertIsNone(payload["economics"])
        self.assertIsNone(payload["assumptions"]["baseline_heater_duty_kw"])
        self.assertIn("synthetic", payload["data_note"].lower())
        html = self.html_path.read_text()
        self.assertIn("<html", html.lower())
        self.assertIn("<svg", html.lower())
        self.assertRegex(html, r"\b29(?:\.0+)?\b")
        self.assertNotIn('<script src="http', html.lower())

    def test_user_csv_sweep_and_measured_baseline_enable_estimates(self):
        source = self.directory / "streams.csv"
        source.write_text(HEADER + "H,hot,200,100,2\nC,cold,20,100,1\n")
        original = source.read_bytes()
        result = self.run_cli(
            source, "--dt-min", "20", "--sweep", "30,5,30",
            "--baseline-duty", "100", "--heater-efficiency", "0.8",
            "--hours", "8000", "--fuel-price", "40", "--retrofit-cost", "16000",
            "--data-note", "Synthetic regression case",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(self.json_path.read_text())
        self.assertEqual([point["dt_min_c"] for point in payload["sensitivity"]], [5, 20, 30])
        self.assertEqual(payload["economics"]["fuel_savings_percent"], 100)
        self.assertEqual(payload["data_note"], "Synthetic regression case")
        self.assertEqual(source.read_bytes(), original)

    def test_malformed_csv_headers_rows_and_non_finite_values_fail_cleanly(self):
        contents = [
            "name,kind,supply_c,target_c\nH,hot,200,100\n",
            HEADER + "H,hot,200,100\nC,cold,20,100,1\n",
            HEADER + "H,hot,nan,100,2\nC,cold,20,100,1\n",
            HEADER + "H,hot,200,100,2,extra\nC,cold,20,100,1\n",
            HEADER + "H,hot,100,200,2\nC,cold,20,100,1\n",
        ]
        source = self.directory / "bad.csv"
        for content in contents:
            with self.subTest(content=content):
                source.write_text(content)
                self.assert_clean_error(self.run_cli(source))
                self.assertEqual(source.read_text(), content)

    def test_invalid_sweeps_and_options_fail_before_writing_reports(self):
        for arguments in [
            ("--sweep", "5,nan"), ("--sweep", "5,0"), ("--sweep", "5,"),
            ("--dt-min", "0"), ("--dt-min", "nan"),
            ("--heater-efficiency", "0"), ("--hours", "9000"),
            ("--baseline-duty", "0"),
        ]:
            with self.subTest(arguments=arguments):
                self.assert_clean_error(self.run_cli(EXAMPLE, *arguments))

    def test_output_paths_cannot_overwrite_the_csv(self):
        source = self.directory / "streams.csv"
        source.write_bytes(EXAMPLE.read_bytes())
        original = source.read_bytes()
        result = self.run_cli(source, "--json", str(source))
        self.assert_clean_error(result)
        self.assertEqual(source.read_bytes(), original)
        result = self.run_cli(source, "--html", str(source))
        self.assert_clean_error(result)
        self.assertEqual(source.read_bytes(), original)

    def test_json_and_html_cannot_share_a_destination(self):
        result = self.run_cli(EXAMPLE, "--html", str(self.json_path))
        self.assert_clean_error(result)

    def test_help_describes_csv_units(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"], cwd=self.directory,
            text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cp_kw_per_k", result.stdout)
        self.assertIn("--baseline-duty", result.stdout)


if __name__ == "__main__":
    unittest.main()
