from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import sympy as sp


@dataclass
class SymStep:
    step: int
    token: str
    stack_before: list[sp.Expr]
    stack_after: list[sp.Expr]
    action: str = ""

    @property
    def top(self) -> Optional[sp.Expr]:
        return self.stack_after[-1] if self.stack_after else None


@dataclass
class SymTrace:
    steps: list[SymStep] = field(default_factory=list)
    raw: Optional[sp.Expr] = None
    simplified: Optional[sp.Expr] = None
    variables: dict[str, sp.Symbol] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.simplified is not None


def _simplify(expr: sp.Expr) -> sp.Expr:
    try:
        s = sp.expand_log(expr, force=True)
        s = sp.powsimp(s, force=True)
        return sp.simplify(s)
    except Exception:
        return expr


def sym_trace(tokens: list[str], simp_intermediates: bool = True) -> SymTrace:
    var_names = sorted({t for t in tokens if t not in ("1", "E")})
    variables: dict[str, sp.Symbol] = {t: sp.Symbol(t, positive=True) for t in var_names}
    stk: list[sp.Expr] = []
    steps: list[SymStep] = []

    for i, tok in enumerate(tokens):
        before = list(stk)
        if tok == "1":
            stk.append(sp.Integer(1))
            action = "push  1"
        elif tok == "E":
            if len(stk) < 2:
                raise ValueError(f"Stack underflow at token {i}")
            y = stk.pop(); x = stk.pop()
            raw = sp.exp(x) - sp.log(y)
            stk.append(_simplify(raw) if simp_intermediates else raw)
            action = f"eml({_fmt(x)}, {_fmt(y)})"
        else:
            stk.append(variables[tok])
            action = f"push  {tok}"
        steps.append(SymStep(step=i, token=tok, stack_before=before, stack_after=list(stk), action=action))

    raw = stk[-1] if stk else None
    return SymTrace(steps=steps, raw=raw, simplified=_simplify(raw) if raw is not None else None, variables=variables)


def _fmt(expr: sp.Expr, max_len: int = 32) -> str:
    s = str(expr)
    return s[:max_len - 1] + "…" if len(s) > max_len else s


def pretty_result(trace: SymTrace) -> str:
    return "(empty)" if trace.simplified is None else sp.pretty(trace.simplified, use_unicode=True)


def latex_result(trace: SymTrace) -> str:
    return "" if trace.simplified is None else sp.latex(trace.simplified)


def sym_equiv(tokens_a: list[str], tokens_b: list[str]) -> tuple[bool, Optional[sp.Expr], Optional[sp.Expr]]:
    ta = sym_trace(tokens_a, simp_intermediates=False)
    tb = sym_trace(tokens_b, simp_intermediates=False)
    if ta.simplified is None or tb.simplified is None:
        return False, ta.simplified, tb.simplified
    diff = sp.simplify(ta.simplified - tb.simplified)
    return bool(diff == sp.Integer(0)), ta.simplified, tb.simplified


def build_catalog() -> dict[str, sp.Expr]:
    x = sp.Symbol("x", positive=True)
    y = sp.Symbol("y", positive=True)
    return {
        "e": sp.E, "0": sp.Integer(0), "1": sp.Integer(1),
        "e^2": sp.E**2, "e^e": sp.E**sp.E,
        "ln(2)": sp.log(sp.Integer(2)), "pi": sp.pi,
        "exp(x)": sp.exp(x), "ln(x)": sp.log(x),
        "x": x, "-x": -x, "1/x": sp.Integer(1)/x,
        "x^2": x**2, "sqrt(x)": sp.sqrt(x),
        "exp(exp(x))": sp.exp(sp.exp(x)),
        "ln(ln(x))": sp.log(sp.log(x)),
        "x*exp(x)": x * sp.exp(x),
        "x+y": x + y, "x*y": x * y, "x^y": x**y,
    }


def sym_identify(tokens: list[str]) -> list[tuple[str, sp.Expr]]:
    trace = sym_trace(tokens, simp_intermediates=False)
    if trace.simplified is None:
        return []
    prog_expr = trace.simplified
    matches = []
    for name, ref in build_catalog().items():
        try:
            if sp.simplify(prog_expr - ref) == sp.Integer(0):
                matches.append((name, ref))
        except Exception:
            continue
            continue
    matches.sort(key=lambda t: len(str(t[1])))
    return matches


def sym_derive(tokens: list[str], var: str = "x") -> tuple[str, str]:
    """Return strings of the simplified program expression and its derivative wrt var."""
    trace = sym_trace(tokens, simp_intermediates=False)
    if trace.simplified is None:
        raise ValueError("Program produced no expression on stack.")
    
    var_sym = trace.variables.get(var)
    if var_sym is None:
        return str(trace.simplified), "0"
        
    deriv = sp.diff(trace.simplified, var_sym)
    return str(trace.simplified), str(sp.simplify(deriv))
