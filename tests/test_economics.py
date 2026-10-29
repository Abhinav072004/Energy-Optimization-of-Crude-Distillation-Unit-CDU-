"""Independent unit conversions and valid ranges for screening estimates."""

import math
import unittest

from cdu.economics import estimate_savings


class EconomicsTests(unittest.TestCase):
    def test_fuel_cost_emissions_and_payback_with_known_units(self):
        result = estimate_savings(
            100, 80, heater_efficiency=0.8, operating_hours=8000,
            fuel_price_per_mwh=40, emission_factor_kg_co2_per_gj=56.1,
            retrofit_cost=16000,
        )
        # 20 kW useful / 0.8 = 25 kW fuel; 8000 h = 200 MWh = 720 GJ.
        self.assertEqual(result["thermal_savings_kw"], 20)
        self.assertEqual(result["fuel_savings_kw"], 25)
        self.assertEqual(result["fuel_savings_mwh_per_year"], 200)
        self.assertEqual(result["annual_cost_savings"], 8000)
        self.assertAlmostEqual(result["annual_co2_savings_tonnes"], 40.392)
        self.assertEqual(result["simple_payback_years"], 2)
        self.assertEqual(result["fuel_savings_percent"], 20)

    def test_worse_target_preserves_negative_savings_without_payback(self):
        result = estimate_savings(
            80, 100, heater_efficiency=0.8, operating_hours=8000,
            fuel_price_per_mwh=40, emission_factor_kg_co2_per_gj=56.1,
            retrofit_cost=16000,
        )
        self.assertEqual(result["fuel_savings_kw"], -25)
        self.assertEqual(result["annual_cost_savings"], -8000)
        self.assertAlmostEqual(result["annual_co2_savings_tonnes"], -40.392)
        self.assertEqual(result["fuel_savings_percent"], -25)
        self.assertIsNone(result["simple_payback_years"])

    def test_zero_savings_and_free_fuel_do_not_produce_infinite_payback(self):
        equal = estimate_savings(100, 100, retrofit_cost=1000)
        free = estimate_savings(100, 50, fuel_price_per_mwh=0, retrofit_cost=1000)
        self.assertEqual(equal["annual_cost_savings"], 0)
        self.assertIsNone(equal["simple_payback_years"])
        self.assertEqual(free["annual_cost_savings"], 0)
        self.assertIsNone(free["simple_payback_years"])
        self.assertGreater(free["annual_co2_savings_tonnes"], 0)

    def test_missing_retrofit_cost_omits_payback(self):
        self.assertIsNone(estimate_savings(100, 50)["simple_payback_years"])

    def test_invalid_finite_and_range_inputs(self):
        invalid = [
            {"baseline_heater_duty_kw": value}
            for value in [0, -1, math.inf, math.nan, True]
        ] + [
            {"target_heater_duty_kw": value}
            for value in [-1, math.inf, math.nan, True]
        ] + [
            {"heater_efficiency": value}
            for value in [0, -0.1, 1.01, math.inf, math.nan, True]
        ] + [
            {"operating_hours": value}
            for value in [0, -1, 8761, math.inf, math.nan, True]
        ]
        for name in ["fuel_price_per_mwh", "emission_factor_kg_co2_per_gj", "retrofit_cost"]:
            invalid.extend({name: value} for value in [-1, math.inf, math.nan, True])
        for override in invalid:
            arguments = {"baseline_heater_duty_kw": 100, "target_heater_duty_kw": 80}
            arguments.update(override)
            with self.subTest(override=override), self.assertRaises(ValueError):
                estimate_savings(**arguments)

    def test_non_finite_calculated_outputs_are_rejected(self):
        with self.assertRaises(ValueError):
            estimate_savings(1e308, 0, heater_efficiency=0.1)


if __name__ == "__main__":
    unittest.main()
