"""Hand-checkable heat-cascade cases and input/energy invariants."""

import math
import unittest

from cdu.analysis import Stream, analyze


class PinchAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.streams = [
            Stream("H1", "hot", 180, 40, 2),
            Stream("H2", "hot", 150, 60, 1.5),
            Stream("C1", "cold", 20, 140, 2),
            Stream("C2", "cold", 80, 160, 1.8),
        ]

    def test_hand_calculated_four_stream_targets(self):
        result = analyze(self.streams, 20)
        self.assertAlmostEqual(result["hot_utility_kw"], 29)
        self.assertAlmostEqual(result["cold_utility_kw"], 60)
        self.assertAlmostEqual(result["heat_recovery_kw"], 355)
        self.assertAlmostEqual(result["total_hot_duty_kw"], 415)
        self.assertAlmostEqual(result["total_cold_duty_kw"], 384)
        # Interval heats 4, -18, -15, 60, 0 give raw minimum -29.
        self.assertEqual(len(result["cascade"]), 5)
        for interval, expected in zip(result["cascade"], [4, -18, -15, 60, 0]):
            self.assertAlmostEqual(interval["interval_heat_kw"], expected)
        self.assertEqual(result["pinch_points"], [
            {"shifted_c": 90.0, "hot_c": 100.0, "cold_c": 80.0},
        ])

    def test_disjoint_temperatures_prevent_recovery(self):
        result = analyze([
            Stream("H", "hot", 40, 20, 1),
            Stream("C", "cold", 100, 120, 1),
        ], 10)
        self.assertEqual(result["heat_recovery_kw"], 0)
        self.assertEqual(result["hot_utility_kw"], 20)
        self.assertEqual(result["cold_utility_kw"], 20)

    def test_hot_utility_threshold_excludes_top_boundary_pinch(self):
        result = analyze([
            Stream("H", "hot", 200, 100, 2),
            Stream("C", "cold", 20, 100, 1),
        ], 20)
        self.assertEqual(result["hot_utility_kw"], 0)
        self.assertEqual(result["cold_utility_kw"], 120)
        self.assertEqual(result["heat_recovery_kw"], 80)
        self.assertEqual(result["pinch_points"], [])

    def test_cold_utility_threshold_excludes_bottom_boundary_pinch(self):
        result = analyze([
            Stream("H", "hot", 150, 100, 1),
            Stream("C", "cold", 100, 200, 2),
        ], 20)
        self.assertEqual(result["hot_utility_kw"], 170)
        self.assertEqual(result["cold_utility_kw"], 20)
        # Below the cold stream's supply there is heat that cannot be recovered.
        self.assertEqual(result["heat_recovery_kw"], 30)

    def test_no_cooling_required_threshold(self):
        result = analyze([
            Stream("H", "hot", 180, 100, 1),
            Stream("C", "cold", 20, 180, 1),
        ], 20)
        self.assertEqual(result["hot_utility_kw"], 80)
        self.assertEqual(result["cold_utility_kw"], 0)
        self.assertEqual(result["heat_recovery_kw"], 80)
        self.assertNotIn(30.0, [p["shifted_c"] for p in result["pinch_points"]])

    def test_energy_balance_and_monotonic_sensitivity(self):
        previous_hot = previous_cold = -1
        for delta_t in [1, 5, 10, 15, 20, 30, 50, 100, 200]:
            with self.subTest(delta_t=delta_t):
                result = analyze(self.streams, delta_t)
                self.assertGreaterEqual(result["hot_utility_kw"] + 1e-8, previous_hot)
                self.assertGreaterEqual(result["cold_utility_kw"] + 1e-8, previous_cold)
                self.assertAlmostEqual(
                    result["hot_utility_kw"] + result["total_hot_duty_kw"],
                    result["cold_utility_kw"] + result["total_cold_duty_kw"],
                )
                self.assertAlmostEqual(
                    result["heat_recovery_kw"],
                    result["total_hot_duty_kw"] - result["cold_utility_kw"],
                )
                self.assertTrue(all(row["residual_kw"] >= 0 for row in result["cascade"]))
                previous_hot, previous_cold = result["hot_utility_kw"], result["cold_utility_kw"]

    def test_input_order_does_not_change_results(self):
        self.assertEqual(analyze(self.streams, 20), analyze(reversed(self.streams), 20))

    def test_rejects_non_positive_and_non_finite_delta_t(self):
        for delta_t in [0, -1, math.nan, math.inf, True, "20"]:
            with self.subTest(delta_t=delta_t), self.assertRaises(ValueError):
                analyze(self.streams, delta_t)

    def test_requires_both_stream_types(self):
        for streams in [[], self.streams[:2], self.streams[2:]]:
            with self.subTest(streams=streams), self.assertRaises(ValueError):
                analyze(streams, 20)

    def test_rejects_wrong_temperature_direction(self):
        for kind, supply, target in [("hot", 20, 30), ("cold", 30, 20), ("hot", 20, 20)]:
            with self.subTest(kind=kind, supply=supply), self.assertRaises(ValueError):
                analyze(self.streams + [Stream("wrong", kind, supply, target, 1)], 20)

    def test_rejects_invalid_stream_values(self):
        invalid = [
            Stream("", "hot", 100, 20, 1),
            Stream("  ", "hot", 100, 20, 1),
            Stream("H1", "hot", 100, 20, 1),
            Stream(" H1 ", "hot", 100, 20, 1),
            Stream("new", "warm", 100, 20, 1),
            Stream("new", "hot", 100, 20, 0),
            Stream("new", "hot", 100, 20, -1),
            Stream("new", "hot", math.inf, 20, 1),
            Stream("new", "hot", 100, math.nan, 1),
            Stream("new", "hot", 100, 20, math.inf),
            Stream("new", "hot", True, 20, 1),
            Stream("new", "hot", 100, 20, True),
            Stream("new", "hot", "100", 20, 1),
        ]
        for stream in invalid:
            with self.subTest(stream=stream), self.assertRaises(ValueError):
                analyze(self.streams + [stream], 20)

    def test_rejects_overflow(self):
        with self.assertRaises(ValueError):
            analyze([Stream("H", "hot", 1e308, -1e308, 1), self.streams[2]], 20)


if __name__ == "__main__":
    unittest.main()
