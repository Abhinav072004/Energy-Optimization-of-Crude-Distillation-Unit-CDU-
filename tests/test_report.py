"""Output safety and degenerate-chart checks for the standalone report."""

import unittest

from cdu.report import render_report


def sample_payload():
    return {
        "schema_version": 1,
        "data_note": 'Illustrative <script>alert("sample")</script> & data',
        "streams": [{"name": '<img src=x onerror="alert(1)">', "kind": "hot",
                     "supply_c": 100, "target_c": 80, "cp_kw_per_k": 2}],
        "target": {
            "dt_min_c": 10, "hot_utility_kw": 0, "cold_utility_kw": 0,
            "heat_recovery_kw": 40, "total_hot_duty_kw": 40,
            "total_cold_duty_kw": 40, "pinch_points": [],
            "cascade": [{"upper_shifted_c": 90, "lower_shifted_c": 90,
                         "net_cp_kw_per_k": 0, "interval_heat_kw": 0,
                         "residual_kw": 0}],
        },
        "assumptions": {
            "baseline_heater_duty_kw": None, "heater_efficiency": 0.85,
            "operating_hours": 8000, "fuel_price_per_mwh": 30,
            "emission_factor_kg_co2_per_gj": 56, "retrofit_cost": None,
        },
        "economics": None,
        "sensitivity": [{"dt_min_c": 10, "hot_utility_kw": 0,
                         "cold_utility_kw": 0, "heat_recovery_kw": 40}],
    }


class ReportTests(unittest.TestCase):
    def test_untrusted_labels_are_escaped(self):
        report = render_report(sample_payload())
        self.assertNotIn("<script>", report)
        self.assertNotIn("<img", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertIn("&lt;img", report)
        self.assertIn("&amp; data", report)

    def test_zero_ranges_produce_finite_self_contained_charts(self):
        report = render_report(sample_payload())
        self.assertEqual(report.count('<svg '), 2)
        self.assertNotRegex(report, r'(?i)(?:points|cx|cy|x1|x2|y1|y2)="[^"]*(?:nan|inf)')
        self.assertNotIn('<script', report)
        self.assertNotIn('src="http', report)
        self.assertNotIn('href="http', report)
        self.assertIn('--baseline-duty', report)

    def test_economics_show_signed_values_and_unavailable_payback(self):
        payload = sample_payload()
        payload["economics"] = {
            "baseline_heater_duty_kw": 100, "target_heater_duty_kw": 120,
            "thermal_savings_kw": -20, "fuel_savings_kw": -25,
            "fuel_savings_mwh_per_year": -200, "annual_cost_savings": -6000,
            "annual_co2_savings_tonnes": -40.32,
            "simple_payback_years": None, "fuel_savings_percent": -20,
        }
        report = render_report(payload)
        self.assertIn('-6,000.0', report)
        self.assertIn('Not available', report)
        self.assertIn('currency/year', report)


if __name__ == "__main__":
    unittest.main()
