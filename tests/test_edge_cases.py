"""Edge-case and stress tests for the EML compiler and VM."""
from __future__ import annotations

import math

import mpmath
import pytest

from emlvm.compiler import compile_expression
from emlvm.rpn import tokenize, validate
from emlvm.vm import EMLMachine


def _compile_and_eval(expr: str, variables: dict[str, float], input_var: str = "x") -> float:
    """Compile, validate, evaluate, and return real part."""
    mpmath.mp.dps = 50
    r = compile_expression(expr, input_var)
    assert r.ok, f"Compilation failed for '{expr}': {r.warnings}"

    toks = tokenize(r.rpn)
    vr = validate(toks)
    assert vr.ok, f"Invalid RPN for '{expr}': {vr.message}"

    mp_vars = {k: mpmath.mpc(v) for k, v in variables.items()}
    m = EMLMachine(toks, mp_vars)
    result = m.run()
    return float(mpmath.re(result))


# ── Negative and zero inputs ──────────────────────────────────────────────────

class TestNegativeInputs:
    def test_exp_negative(self):
        assert _compile_and_eval("exp(x)", {"x": -3}) == pytest.approx(math.exp(-3), rel=1e-8)

    def test_ln_small_positive(self):
        assert _compile_and_eval("ln(x)", {"x": 0.001}) == pytest.approx(math.log(0.001), rel=1e-8)

    def test_neg_of_negative(self):
        """Double negation: -(-3) = 3."""
        assert _compile_and_eval("-x", {"x": -3}) == pytest.approx(3, rel=1e-8)

    def test_double_neg(self):
        """-(-x) should equal x."""
        assert _compile_and_eval("-(-x)", {"x": 4}) == pytest.approx(4, rel=1e-8)

    def test_sub_negative_result(self):
        assert _compile_and_eval("x - y", {"x": 2, "y": 5}) == pytest.approx(-3, rel=1e-8)


# ── Zero handling ─────────────────────────────────────────────────────────────

class TestZeroHandling:
    def test_add_zeros(self):
        assert _compile_and_eval("x + y", {"x": 0, "y": 0}) == pytest.approx(0, abs=1e-8)

    def test_mul_by_zero(self):
        assert _compile_and_eval("x * y", {"x": 0, "y": 5}) == pytest.approx(0, abs=1e-8)

    def test_sub_equal(self):
        assert _compile_and_eval("x - y", {"x": 3, "y": 3}) == pytest.approx(0, abs=1e-8)

    def test_zero_constant(self):
        assert _compile_and_eval("0", {"x": 99}) == pytest.approx(0, abs=1e-8)

    def test_add_zero_identity(self):
        """x + 0 = x."""
        assert _compile_and_eval("x + 0", {"x": 7.5}) == pytest.approx(7.5, rel=1e-8)

    def test_mul_by_one_identity(self):
        """x * 1 = x."""
        assert _compile_and_eval("x * 1", {"x": 7.5}) == pytest.approx(7.5, rel=1e-8)


# ── Large values ──────────────────────────────────────────────────────────────

class TestLargeValues:
    def test_add_large(self):
        assert _compile_and_eval("x + y", {"x": 1000, "y": 2000}) == pytest.approx(3000, rel=1e-8)

    def test_mul_large(self):
        assert _compile_and_eval("x * y", {"x": 100, "y": 200}) == pytest.approx(20000, rel=1e-8)

    def test_pow_large_base(self):
        assert _compile_and_eval("x ** y", {"x": 10, "y": 3}) == pytest.approx(1000, rel=1e-8)


# ── Small / fractional values ────────────────────────────────────────────────

class TestSmallValues:
    def test_div_fraction(self):
        assert _compile_and_eval("x / y", {"x": 1, "y": 3}) == pytest.approx(1 / 3, rel=1e-8)

    def test_sqrt_via_pow(self):
        """x^0.5 = sqrt(x)."""
        assert _compile_and_eval("x ** y", {"x": 4, "y": 0.5}) == pytest.approx(2, rel=1e-8)

    def test_mul_tiny(self):
        assert _compile_and_eval("x * y", {"x": 0.001, "y": 0.002}) == pytest.approx(2e-6, rel=1e-6)


# ── Composition and nesting ──────────────────────────────────────────────────

class TestComposition:
    def test_exp_ln_roundtrip(self):
        assert _compile_and_eval("exp(ln(x))", {"x": 7.5}) == pytest.approx(7.5, rel=1e-8)

    def test_ln_exp_roundtrip(self):
        assert _compile_and_eval("ln(exp(x))", {"x": -2.5}) == pytest.approx(-2.5, rel=1e-8)

    def test_difference_of_squares(self):
        """(x + y)(x - y) = x^2 - y^2."""
        assert _compile_and_eval("(x + y) * (x - y)", {"x": 5, "y": 3}) == pytest.approx(16, rel=1e-8)

    def test_pythagorean(self):
        """x^2 + y^2 at (3,4) = 25."""
        assert _compile_and_eval("x ** 2 + y ** 2", {"x": 3, "y": 4}) == pytest.approx(25, rel=1e-8)

    def test_factored_quadratic(self):
        """(x+1)(x-1) = x^2 - 1."""
        assert _compile_and_eval("(x + 1) * (x - 1)", {"x": 5}) == pytest.approx(24, rel=1e-8)

    def test_distribute(self):
        """x*y + x = x(y+1)."""
        assert _compile_and_eval("x * y + x", {"x": 3, "y": 4}) == pytest.approx(15, rel=1e-8)

    def test_reciprocal_subtraction(self):
        """x/y - y/x."""
        assert _compile_and_eval("x / y - y / x", {"x": 6, "y": 3}) == pytest.approx(1.5, rel=1e-8)

    def test_deeply_nested_exp(self):
        """exp(exp(exp(x))) at x=0 = e^e ≈ 15.15."""
        assert _compile_and_eval("exp(exp(exp(x)))", {"x": 0}) == pytest.approx(
            float(mpmath.exp(mpmath.exp(mpmath.exp(0)))), rel=1e-8
        )

    def test_polynomial_degree3(self):
        """x^3 + x^2 + x + 1 at x=2 = 8+4+2+1 = 15."""
        assert _compile_and_eval("x**3 + x**2 + x + 1", {"x": 2}) == pytest.approx(15, rel=1e-8)


# ── Algebraic identities ─────────────────────────────────────────────────────

class TestAlgebraicIdentities:
    """Verify algebraic identities hold through EML compilation."""

    @pytest.mark.parametrize("x_val", [0.5, 1.0, 2.0, 5.0, 10.0])
    def test_exp_ln_identity(self, x_val):
        """exp(ln(x)) = x for positive x."""
        assert _compile_and_eval("exp(ln(x))", {"x": x_val}) == pytest.approx(x_val, rel=1e-8)

    @pytest.mark.parametrize("x_val", [-3.0, -1.0, 0.0, 1.0, 3.0])
    def test_ln_exp_identity(self, x_val):
        """ln(exp(x)) = x."""
        assert _compile_and_eval("ln(exp(x))", {"x": x_val}) == pytest.approx(x_val, rel=1e-8)

    @pytest.mark.parametrize("x_val", [1.0, 2.0, 3.0, 7.0])
    def test_neg_neg_identity(self, x_val):
        """-(-x) = x."""
        assert _compile_and_eval("-(-x)", {"x": x_val}) == pytest.approx(x_val, rel=1e-8)

    def test_add_commutative(self):
        """x + y = y + x."""
        r1 = _compile_and_eval("x + y", {"x": 3.7, "y": 2.1})
        r2 = _compile_and_eval("y + x", {"x": 3.7, "y": 2.1})
        assert r1 == pytest.approx(r2, rel=1e-8)

    def test_mul_commutative(self):
        """x * y = y * x."""
        r1 = _compile_and_eval("x * y", {"x": 3.7, "y": 2.1})
        r2 = _compile_and_eval("y * x", {"x": 3.7, "y": 2.1})
        assert r1 == pytest.approx(r2, rel=1e-8)

    def test_add_associative(self):
        """(x + y) + z = x + (y + z) via substitution."""
        # Use x=2, y=3, z stored as a constant
        r1 = _compile_and_eval("(x + y) + 5", {"x": 2, "y": 3})
        r2 = _compile_and_eval("x + (y + 5)", {"x": 2, "y": 3})
        assert r1 == pytest.approx(r2, rel=1e-8)
        assert r1 == pytest.approx(10, rel=1e-8)

    def test_distributive(self):
        """x * (y + z) = x*y + x*z where z=2."""
        r1 = _compile_and_eval("x * (y + 2)", {"x": 3, "y": 4})
        r2 = _compile_and_eval("x * y + x * 2", {"x": 3, "y": 4})
        assert r1 == pytest.approx(r2, rel=1e-8)
        assert r1 == pytest.approx(18, rel=1e-8)


# ── RPN validation ───────────────────────────────────────────────────────────

class TestRPNValidation:
    """Ensure all compiled programs produce valid RPN."""

    @pytest.mark.parametrize("expr", [
        "exp(x)", "ln(x)", "-x", "inv(x)", "sqr(x)",
        "x + y", "x - y", "x * y", "x / y", "x ** y",
        "exp(x) + ln(y)", "x ** 2 + 2 * x + 1",
        "(x + y) * (x - y)", "x ** 3",
        "2", "0", "-3", "e",
    ])
    def test_compiled_rpn_is_valid(self, expr):
        r = compile_expression(expr, "x")
        assert r.ok, f"'{expr}' failed: {r.warnings}"
        toks = tokenize(r.rpn)
        vr = validate(toks)
        assert vr.ok, f"'{expr}' invalid RPN: {vr.message}"
        assert vr.final_depth == 1


# ── Compiler error handling ──────────────────────────────────────────────────

class TestCompilerErrors:
    """Test that unsupported expressions are handled gracefully."""

    def test_unsupported_sqrt(self):
        r = compile_expression("sqrt(x)", "x")
        assert not r.ok
        assert "sqrt" in r.unsupported

    def test_unsupported_sin(self):
        r = compile_expression("sin(x)", "x")
        assert not r.ok
        assert "sin" in r.unsupported

    def test_unsupported_cos(self):
        r = compile_expression("cos(x)", "x")
        assert not r.ok

    def test_unsupported_pi(self):
        r = compile_expression("pi", "x")
        assert not r.ok

    def test_unsupported_abs(self):
        """abs() should report 'recognized but unsupported', not 'unknown'."""
        r = compile_expression("abs(x)", "x")
        assert not r.ok
        assert "abs" in r.unsupported
        assert any("recognized" in w for w in r.warnings)

    def test_unknown_function(self):
        r = compile_expression("foo(x)", "x")
        assert not r.ok

    def test_syntax_error(self):
        r = compile_expression("x +* y", "x")
        assert not r.ok

    def test_large_integer_cap(self):
        """Integers > 20 should be rejected to prevent token explosion."""
        r = compile_expression("100", "x")
        assert not r.ok
        assert "100" in r.unsupported

    def test_large_negative_integer_cap(self):
        r = compile_expression("-50", "x")
        assert not r.ok


class TestBinaryFunctionCalls:
    """Test binary function call syntax: add(x, y), mul(x, y), etc."""

    def test_add_call(self):
        assert _compile_and_eval("add(x, y)", {"x": 5, "y": 3}) == pytest.approx(8, rel=1e-8)

    def test_mul_call(self):
        assert _compile_and_eval("mul(x, y)", {"x": 5, "y": 3}) == pytest.approx(15, rel=1e-8)

    def test_sub_call(self):
        assert _compile_and_eval("sub(x, y)", {"x": 5, "y": 3}) == pytest.approx(2, rel=1e-8)

    def test_div_call(self):
        assert _compile_and_eval("div(x, y)", {"x": 15, "y": 3}) == pytest.approx(5, rel=1e-8)

    def test_pow_call(self):
        assert _compile_and_eval("pow(x, y)", {"x": 2, "y": 10}) == pytest.approx(1024, rel=1e-8)
