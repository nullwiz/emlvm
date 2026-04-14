"""Tests for the EML compiler — math expressions to EML RPN."""
from __future__ import annotations

import mpmath
import pytest

from emlvm.compiler import compile_expression
from emlvm.rpn import tokenize
from emlvm.vm import EMLMachine


def _eval_compiled(expr: str, variables: dict[str, float], input_var: str = "x") -> float:
    """Compile an expression and evaluate it, returning the real part."""
    mpmath.mp.dps = 50
    r = compile_expression(expr, input_var)
    assert r.ok, f"Compilation failed for '{expr}': {r.warnings}"
    toks = tokenize(r.rpn)
    mp_vars = {k: mpmath.mpc(v) for k, v in variables.items()}
    m = EMLMachine(toks, mp_vars)
    result = m.run()
    return float(mpmath.re(result))


class TestUnaryFunctions:
    def test_exp(self):
        assert _eval_compiled("exp(x)", {"x": 2}) == pytest.approx(7.389056099, rel=1e-8)

    def test_ln(self):
        assert _eval_compiled("ln(x)", {"x": 10}) == pytest.approx(2.302585093, rel=1e-8)

    def test_neg(self):
        assert _eval_compiled("-x", {"x": 5}) == pytest.approx(-5, rel=1e-8)

    def test_inv(self):
        assert _eval_compiled("inv(x)", {"x": 4}) == pytest.approx(0.25, rel=1e-8)

    def test_sqr(self):
        assert _eval_compiled("sqr(x)", {"x": 7}) == pytest.approx(49, rel=1e-8)

    def test_nested_exp_ln(self):
        assert _eval_compiled("exp(ln(x))", {"x": 3.5}) == pytest.approx(3.5, rel=1e-8)

    def test_ln_exp(self):
        assert _eval_compiled("ln(exp(x))", {"x": 2.7}) == pytest.approx(2.7, rel=1e-8)


class TestBinaryOperations:
    def test_add(self):
        assert _eval_compiled("x + y", {"x": 5, "y": 3}) == pytest.approx(8, rel=1e-8)

    def test_sub(self):
        assert _eval_compiled("x - y", {"x": 5, "y": 3}) == pytest.approx(2, rel=1e-8)

    def test_mul(self):
        assert _eval_compiled("x * y", {"x": 5, "y": 3}) == pytest.approx(15, rel=1e-8)

    def test_div(self):
        assert _eval_compiled("x / y", {"x": 15, "y": 3}) == pytest.approx(5, rel=1e-8)

    def test_pow(self):
        assert _eval_compiled("x ** y", {"x": 2, "y": 10}) == pytest.approx(1024, rel=1e-8)

    def test_caret_pow(self):
        assert _eval_compiled("x ^ y", {"x": 3, "y": 3}) == pytest.approx(27, rel=1e-8)


class TestConstants:
    def test_one(self):
        assert _eval_compiled("1", {"x": 0}) == pytest.approx(1, rel=1e-8)

    def test_zero(self):
        assert _eval_compiled("0", {"x": 0}) == pytest.approx(0, abs=1e-8)

    def test_e(self):
        assert _eval_compiled("e", {"x": 0}) == pytest.approx(2.718281828, rel=1e-8)

    def test_integer_2(self):
        assert _eval_compiled("2", {"x": 0}) == pytest.approx(2, rel=1e-8)

    def test_negative_integer(self):
        assert _eval_compiled("-3", {"x": 0}) == pytest.approx(-3, rel=1e-8)


class TestComposedExpressions:
    def test_exp_plus_ln(self):
        r = _eval_compiled("exp(x) + ln(y)", {"x": 1, "y": 1})
        assert r == pytest.approx(float(mpmath.e), rel=1e-8)

    def test_polynomial(self):
        # x^2 + 2*x + 1 at x=3 should be 16
        r = _eval_compiled("x**2 + 2*x + 1", {"x": 3})
        assert r == pytest.approx(16, rel=1e-8)

    def test_mixed_operations(self):
        # (x + y) * (x - y) at x=5, y=3 should be 16
        r = _eval_compiled("(x + y) * (x - y)", {"x": 5, "y": 3})
        assert r == pytest.approx(16, rel=1e-8)
