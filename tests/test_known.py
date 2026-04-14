"""Tests for known EML formulas — verify each program evaluates correctly."""
from __future__ import annotations

import mpmath
import pytest

from emlvm.known import LIBRARY
from emlvm.rpn import tokenize, validate
from emlvm.vm import EMLMachine


# Reference oracles for each known formula
ORACLES: dict[str, callable] = {
    "e":        lambda v: mpmath.e,
    "zero":     lambda v: mpmath.mpc(0),
    "exp":      lambda v: mpmath.exp(v["x"]),
    "ln":       lambda v: mpmath.log(v["x"]),
    "id":       lambda v: v["x"],
    "ee":       lambda v: mpmath.exp(mpmath.e),
    "eee":      lambda v: mpmath.exp(mpmath.exp(mpmath.e)),
    "expexp":   lambda v: mpmath.exp(mpmath.exp(v["x"])),
    "lnln":     lambda v: mpmath.log(mpmath.log(v["x"])),
    "expm1":    lambda v: mpmath.exp(v["x"]) - 1,
    "eminusx":  lambda v: mpmath.e - v["x"],
    "oneminus": lambda v: 1 - v["x"],
    "edivx":    lambda v: mpmath.e / v["x"],
    "neg":      lambda v: -v["x"],
    "inv":      lambda v: mpmath.mpc(1) / v["x"],
    "sub":      lambda v: v["x"] - v["y"],
    "mul":      lambda v: v["x"] * v["y"],
    "add":      lambda v: v["x"] + v["y"],
    "div":      lambda v: v["x"] / v["y"],
    "pow":      lambda v: v["x"] ** v["y"],
    "sqr":      lambda v: v["x"] ** 2,
}

# Test point values (algebraically independent transcendentals)
# x must be > e for lnln(x) to be defined in reals
TEST_VARS = {
    "x": mpmath.pi,          # pi ~ 3.1416 (> e, so ln(ln(x)) is real)
    "y": mpmath.mpf("1.28242712910062263687534256887"),  # Glaisher A
}


def _formulas_with_programs():
    """Yield (name, formula) for formulas that have programs."""
    for name, f in LIBRARY.items():
        if f.program is not None and name in ORACLES:
            yield name, f


@pytest.mark.parametrize(
    "name,formula",
    list(_formulas_with_programs()),
    ids=[n for n, _ in _formulas_with_programs()],
)
def test_known_formula_evaluates_correctly(name, formula):
    """Each known formula should evaluate to match its oracle."""
    mpmath.mp.dps = 50
    toks = tokenize(formula.program)

    # Validate RPN structure
    vr = validate(toks)
    assert vr.ok, f"{name}: invalid RPN: {vr.message}"

    # Check K matches
    assert len(toks) == formula.k, f"{name}: K mismatch: {len(toks)} != {formula.k}"

    # Build variable bindings
    vars_dict = {v: TEST_VARS[v] for v in formula.variables}

    # Run and compare
    m = EMLMachine(toks, vars_dict, prec=50)
    result = m.run()
    expected = ORACLES[name](vars_dict)

    # Compare real and imaginary parts
    tol = mpmath.mpf(10) ** -20
    diff = abs(result - expected)
    assert diff < tol, (
        f"{name}: result={result}, expected={expected}, diff={diff}"
    )
