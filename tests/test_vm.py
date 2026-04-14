"""Tests for the EML virtual machine (vm.py)."""
from __future__ import annotations

import mpmath
import pytest

from emlvm.rpn import tokenize
from emlvm.vm import EMLMachine, eml, fmt_num


class TestEmlOperator:
    """Test the raw eml(x, y) = exp(x) - ln(y) function."""

    def test_eml_1_1(self):
        """eml(1, 1) = e - 0 = e."""
        r = eml(mpmath.mpc(1), mpmath.mpc(1))
        assert abs(r - mpmath.e) < mpmath.mpf(10) ** -40

    def test_eml_0_1(self):
        """eml(0, 1) = exp(0) - ln(1) = 1 - 0 = 1."""
        r = eml(mpmath.mpc(0), mpmath.mpc(1))
        assert abs(r - 1) < mpmath.mpf(10) ** -40

    def test_eml_x_1_is_exp(self):
        """eml(x, 1) = exp(x) for any x."""
        for x_val in [0, 1, 2, -1, 0.5]:
            r = eml(mpmath.mpc(x_val), mpmath.mpc(1))
            expected = mpmath.exp(x_val)
            assert abs(r - expected) < mpmath.mpf(10) ** -40, f"Failed at x={x_val}"

    def test_eml_noncommutative(self):
        """eml is NOT commutative: eml(a,b) != eml(b,a) in general."""
        a, b = mpmath.mpc(2), mpmath.mpc(3)
        assert abs(eml(a, b) - eml(b, a)) > 0.01


class TestEMLMachine:
    """Test the stack machine execution."""

    def test_single_constant(self):
        m = EMLMachine(["1"], {})
        assert float(mpmath.re(m.run())) == 1.0

    def test_single_variable(self):
        m = EMLMachine(["x"], {"x": mpmath.mpc(42)})
        assert float(mpmath.re(m.run())) == 42.0

    def test_exp_program(self):
        """x1E = exp(x)."""
        toks = tokenize("x1E")
        m = EMLMachine(toks, {"x": mpmath.mpc(2)})
        result = m.run()
        assert abs(result - mpmath.exp(2)) < mpmath.mpf(10) ** -30

    def test_e_program(self):
        """11E = e."""
        toks = tokenize("11E")
        m = EMLMachine(toks, {})
        result = m.run()
        assert abs(result - mpmath.e) < mpmath.mpf(10) ** -30

    def test_zero_program(self):
        """111E1EE = 0."""
        toks = tokenize("111E1EE")
        m = EMLMachine(toks, {})
        result = m.run()
        assert abs(result) < mpmath.mpf(10) ** -30

    def test_ln_program(self):
        """11xE1EE = ln(x)."""
        toks = tokenize("11xE1EE")
        m = EMLMachine(toks, {"x": mpmath.mpc(10)})
        result = m.run()
        assert abs(result - mpmath.log(10)) < mpmath.mpf(10) ** -30

    def test_step_by_step(self):
        """Verify step() produces correct history."""
        toks = tokenize("11E")
        m = EMLMachine(toks, {})
        records = []
        while not m.done:
            rec = m.step()
            records.append(rec)
        assert len(records) == 3
        assert records[0].token == "1"
        assert records[1].token == "1"
        assert records[2].token == "E"
        assert records[2].eml_args is not None

    def test_history_length(self):
        toks = tokenize("x1E")
        m = EMLMachine(toks, {"x": mpmath.mpc(1)})
        m.run()
        assert len(m.history) == 3

    def test_precision(self):
        """High precision should give more accurate results."""
        toks = tokenize("11E")
        m = EMLMachine(toks, {}, prec=100)
        result = m.run()
        diff = abs(result - mpmath.e)
        assert diff < mpmath.mpf(10) ** -90


class TestFmtNum:
    """Test number formatting."""

    def test_real_positive(self):
        s = fmt_num(mpmath.mpc(3.14))
        assert "3.14" in s

    def test_real_negative(self):
        s = fmt_num(mpmath.mpc(-2.5))
        assert "-2.5" in s

    def test_pure_imaginary(self):
        s = fmt_num(mpmath.mpc(0, 1))
        assert "i" in s

    def test_zero(self):
        s = fmt_num(mpmath.mpc(0))
        assert "0" in s

    def test_inf(self):
        s = fmt_num(mpmath.mpc(float("inf")))
        assert "∞" in s
