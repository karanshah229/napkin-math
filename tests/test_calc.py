"""Tests for skills/napkin-math/scripts/calc.py. Run: python -m unittest discover tests"""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "napkin-math" / "scripts"))
import calc  # noqa: E402

KIB, MIB, GIB, TIB = 2**10, 2**20, 2**30, 2**40
MONTH = 730 * 3600


def value(src, env=None):
    return calc.run(src, env)[-1][2]


def line(src):
    return calc.run(src)[-1][1]


class Units(unittest.TestCase):
    def test_binary_and_decimal_prefixes(self):
        self.assertEqual(value("1 KiB").v, KIB)
        self.assertEqual(value("1 GiB").v, GIB)
        self.assertEqual(value("1 TiB").v, TIB)
        self.assertEqual(value("1 PiB").v, 2**50)
        self.assertEqual(value("1 GB").v, 1e9)
        self.assertEqual(value("1 TB").v, 1e12)
        self.assertEqual(value("1 kB").v, 1e3)

    def test_bits(self):
        self.assertAlmostEqual(value("1 Gbit").v, 1e9 / 8)
        self.assertAlmostEqual(value("10 Gbps").v, 10e9 / 8)
        self.assertEqual(value("10 Gbps").d, (1, -1, 0))

    def test_time(self):
        for src, secs in [("1 ns", 1e-9), ("1 us", 1e-6), ("1 μs", 1e-6), ("1 µs", 1e-6),
                          ("1 ms", 1e-3), ("1 min", 60), ("1 h", 3600), ("1 day", 86400),
                          ("1 month", MONTH), ("1 year", 8760 * 3600)]:
            self.assertAlmostEqual(value(src).v, secs, msg=src)

    def test_counts_are_dimensionless(self):
        self.assertTrue(value("5 req").plain)
        self.assertEqual(value("100 IOPS").d, (0, -1, 0))
        self.assertAlmostEqual(value("5%").v, 0.05)

    def test_number_suffixes(self):
        self.assertEqual(value("100k").v, 1e5)
        self.assertEqual(value("2.5M").v, 2.5e6)
        self.assertEqual(value("3bn").v, 3e9)
        self.assertEqual(value("1e6").v, 1e6)
        self.assertEqual(value("1,000,000").v, 1e6)
        self.assertEqual(value("1_000").v, 1e3)


class Parsing(unittest.TestCase):
    def test_compound_unit_binds_tighter_than_spaced_division(self):
        q = value("1 TiB / 5 GiB/s")
        self.assertEqual(q.d, (0, 1, 0))
        self.assertAlmostEqual(q.v, TIB / (5 * GIB))

    def test_glued_per(self):
        self.assertEqual(value("100k/s").d, (0, -1, 0))
        self.assertAlmostEqual(value("100k/s").v, 1e5)

    def test_plain_division_still_works(self):
        self.assertEqual(value("10/2").v, 5)
        self.assertEqual(value("10 / 2").v, 5)

    def test_money(self):
        q = value("$0.02/GB/month")
        self.assertEqual(q.d, (-1, -1, 1))
        self.assertAlmostEqual(q.v, 0.02 / 1e9 / MONTH)
        self.assertAlmostEqual(value("$5/1M req * 1bn req").v, 5000)

    def test_conversion(self):
        self.assertEqual(line("260 TB * $0.02/GB/month to $/month"), "= $5,200 /month  ≈ $5,000 /month")
        self.assertEqual(line("5 Gbit/s to MiB/s"), "= 596 MiB/s  ≈ 600 MiB/s")
        self.assertIn("8.85 TB/day", line("100k/s * 1 KiB to TB/day"))

    def test_variables_persist_and_count_names_can_be_reused(self):
        env = {}
        calc.run("rps = 100k/s; line = 1 KiB", env)
        q = value("rps * line * 30 day", env)
        self.assertEqual(q.d, (1, 0, 0))
        self.assertAlmostEqual(q.v, 1e5 * KIB * 30 * 86400)

    def test_core_units_cannot_be_redefined(self):
        with self.assertRaises(calc.CalcError):
            calc.run("GB = 5")
        with self.assertRaises(calc.CalcError):
            calc.run("s = 5")

    def test_precedence_and_power(self):
        self.assertEqual(value("2 + 3 * 4").v, 14)
        self.assertEqual(value("2 ^ 3 ^ 2").v, 512)
        self.assertEqual(value("-2 ^ 2").v, -4)  # power binds tighter than minus, as in math
        self.assertEqual(value("(2 + 3) * 4").v, 20)

    def test_functions(self):
        self.assertAlmostEqual(value("log2(1bn)").v, math.log2(1e9))
        self.assertEqual(value("ceil(2.1)").v, 3)
        self.assertEqual(value("max(1 ms, 2 ms)").v, 2e-3)
        self.assertAlmostEqual(value("sqrt(4 GiB^2)").v, 2 * GIB)


class Errors(unittest.TestCase):
    def test_mismatched_dimensions(self):
        for src in ["1 GiB + 1 s", "1 GiB to s", "max(1 ms, 1 GB)", "log2(5 GB)"]:
            with self.assertRaises(calc.CalcError, msg=src):
                calc.run(src)

    def test_unknown_name(self):
        with self.assertRaises(calc.CalcError):
            calc.run("5 * bogus")

    def test_cli_exit_codes(self):
        self.assertEqual(calc.main(["1 + 1"]), 0)
        self.assertEqual(calc.main(["1 GiB + 1 s"]), 1)


class Formatting(unittest.TestCase):
    def test_auto_units(self):
        self.assertEqual(line("1 TiB / 5 GiB/s"), "= 3.41 min  ≈ 3 min")
        self.assertTrue(line("100k/s * 1 KiB * 30 day").startswith("= 241 TiB  (265 TB)"))
        self.assertTrue(line("200 us").startswith("= 200 μs"))
        self.assertTrue(line("8 KiB / 200 us").startswith("= 39.1 MiB/s"))
        self.assertTrue(line("10 TB / (3 MiB / 200 ms)").startswith("= 7.36 days"))
        self.assertEqual(line("$1500"), "= $1,500  ≈ $2,000")

    def test_large_numbers_use_exponents(self):
        self.assertEqual(calc.fmt_num(8.64e9), "8.64e9")
        self.assertEqual(calc.fmt_num(5_200_000), "5,200,000")
        self.assertEqual(calc.fmt_num(132_710), "133,000")
        self.assertEqual(calc.fmt_num(1234.5), "1,230")
        self.assertEqual(calc.fmt_num(0.012345), "0.0123")
        self.assertEqual(calc.fmt_num(0.000123), "1.23e-4")

    def test_napkin_rounding(self):
        self.assertEqual(calc.napkin(173), 200)
        self.assertEqual(calc.napkin(0.034), 0.03)
        self.assertEqual(calc.napkin(-4600), -5000)


class ReferenceTables(unittest.TestCase):
    """The README's own $ / TiB derivation, reproduced with the calculator."""

    def test_memory_read_cost_matches_readme(self):
        # One vCPU of General ($40 / month) reading at 30 GiB/s: README says $0.0005 / TiB.
        q = value("$40/month * (1 TiB / 30 GiB/s)")
        self.assertAlmostEqual(calc.napkin(q.v), 0.0005, places=6)


if __name__ == "__main__":
    unittest.main()
