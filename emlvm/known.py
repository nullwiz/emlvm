from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class KnownFormula:
    name: str                    # short identifier
    program: Optional[str]       # RPN string, or None if TBD
    description: str             # math expression it computes
    variables: list[str]         # variable names used
    k: Optional[int]             # K = program length (from paper if known)
    source: str                  # 'paper', 'derived', 'search', 'tbd'
    notes: str = ""


LIBRARY: dict[str, KnownFormula] = {
    "e": KnownFormula(
        name="e",
        program="11E",
        description="Euler's number  e = exp(1)",
        variables=[],
        k=3,
        source="paper",
        notes="First result found by the bootstrap search (Fig. 1).",
    ),
    "zero": KnownFormula(
        name="zero",
        program="111E1EE",
        description="The constant 0  (= ln 1  via EML)",
        variables=[],
        k=7,
        source="derived",
        notes="Substitute x=1 into the ln(x) program: eml(1, eml(eml(1,1), 1)) = e-(e-0) = 0.",
    ),
    "exp": KnownFormula(
        name="exp",
        program="x1E",
        description="Exponential  exp(x) = eᵡ",
        variables=["x"],
        k=3,
        source="paper",
        notes="eml(x, 1) = exp(x) - ln(1) = exp(x).",
    ),
    "ln": KnownFormula(
        name="ln",
        program="11xE1EE",
        description="Natural logarithm  ln(x)",
        variables=["x"],
        k=7,
        source="paper",
        notes="Explicitly given as the worked example in §4.1 of the paper.",
    ),
    "id": KnownFormula(
        name="id",
        program="11x1EE1EE",
        description="Identity  f(x) = x  (the shortest non-trivial EML identity)",
        variables=["x"],
        k=9,
        source="derived",
        notes=(
            "ln(exp(x)) = x.  Compose ln ∘ exp: substitute x→exp(x)=x1E "
            "into ln program 11xE1EE → inner x becomes x1E, producing 11x1EE1EE."
        ),
    ),
    "ee": KnownFormula(
        name="ee",
        program="11E1E",
        description="Tower constant  e^e ≈ 15.1543",
        variables=[],
        k=5,
        source="derived",
        notes=(
            "exp(e) = eml(e, 1) = eml(eml(1,1), 1).  "
            "Substituting the e-program '11E' into exp-program: '11E' + '1E' = '11E1E'."
        ),
    ),
    "eee": KnownFormula(
        name="eee",
        program="11E1E1E",
        description="Tower constant  e^(e^e) ≈ 3,814,280",
        variables=[],
        k=7,
        source="derived",
        notes="exp(e^e) = eml(e^e, 1).  Chain: '11E1E' + '1E' = '11E1E1E'.",
    ),
    "expexp": KnownFormula(
        name="expexp",
        program="x1E1E",
        description="Double exponential  exp(exp(x)) = e^(eˣ)",
        variables=["x"],
        k=5,
        source="derived",
        notes=(
            "Compose exp∘exp: substitute x→exp(x)='x1E' into outer exp-program 'x1E'. "
            "Replace inner 'x' with 'x1E': 'x1E' + '1E' = 'x1E1E'."
        ),
    ),
    "lnln": KnownFormula(
        name="lnln",
        program="1111xE1EEE1EE",
        description="Double logarithm  ln(ln(x))  [x > 1]",
        variables=["x"],
        k=13,
        source="derived",
        notes=(
            "Compose ln∘ln: substitute inner ln-tokens into outer ln template. "
            "ln template [1,1,x,E,1,E,E] with x→[1,1,x,E,1,E,E]: "
            "gives [1,1,1,1,x,E,1,E,E,E,1,E,E] = '1111xE1EEE1EE'.  Domain: x > 1."
        ),
    ),
    "expm1": KnownFormula(
        name="expm1",
        program="x11EE",
        description="exp(x) - 1",
        variables=["x"],
        k=5,
        source="derived",
        notes="eml(x, eml(1,1)) = eml(x, e) = exp(x) - ln(e) = exp(x) - 1.",
    ),
    "eminusx": KnownFormula(
        name="eminusx",
        program="1x1EE",
        description="e - x",
        variables=["x"],
        k=5,
        source="derived",
        notes="eml(1, eml(x,1)) = eml(1, exp(x)) = e - ln(exp(x)) = e - x.",
    ),
    "oneminus": KnownFormula(
        name="oneminus",
        program="111E1EEx1EE",
        description="1 - x  (first EML program producing negative reals)",
        variables=["x"],
        k=11,
        source="derived",
        notes=(
            "eml(0, exp(x)) = exp(0) - ln(exp(x)) = 1 - x. "
            "Zero computed as ln(1) via '111E1EE', then exp(x) via 'x1E', then one E."
        ),
    ),
    "edivx": KnownFormula(
        name="edivx",
        program="111E1EExE1E",
        description="e / x",
        variables=["x"],
        k=11,
        source="derived",
        notes=(
            "exp(1 - ln(x)) = e * exp(-ln(x)) = e/x. "
            "Computed as eml(eml(0, x), 1) where 0 from '111E1EE': "
            "eml(0,x) = 1-ln(x), then eml(1-ln(x),1) = exp(1-ln(x)) = e/x."
        ),
    ),
    "neg": KnownFormula(
        name="neg",
        program=None,
        description="Negation  −x",
        variables=["x"],
        k=15,
        source="tbd",
        notes="K=15 from paper Table 4. Requires extended reals (±∞ intermediates). Run `emlvm golf neg --max-k 15`.",
    ),
    "inv": KnownFormula(
        name="inv",
        program=None,
        description="Reciprocal  1/x",
        variables=["x"],
        k=15,
        source="tbd",
        notes="K=15 from paper Table 4. Run `emlvm golf inv --max-k 15` to find it.",
    ),
    "mul": KnownFormula(
        name="mul",
        program=None,
        description="Multiplication  x·y",
        variables=["x", "y"],
        k=19,
        source="tbd",
        notes="K=19 from paper Table 4. Run `emlvm golf mul --max-k 21` to find it.",
    ),
    "add": KnownFormula(
        name="add",
        program=None,
        description="Addition  x + y",
        variables=["x", "y"],
        k=27,
        source="tbd",
        notes="K≥27 from paper Table 4. Run `emlvm golf add --max-k 29` to find it.",
    ),
}


# ── Aliases ────────────────────────────────────────────────────────────────
ALIASES: dict[str, str] = {
    "exp(x)": "exp",
    "e^x":    "exp",
    "ln(x)":  "ln",
    "log":    "ln",
    "log(x)": "ln",
    "identity": "id",
    "x":       "id",
    "-x":      "neg",
    "neg(x)":  "neg",
    "1/x":     "inv",
    "inv(x)":  "inv",
    "x*y":     "mul",
    "mul(x,y)":"mul",
    "x+y":     "add",
    "add(x,y)":"add",
    "0":       "zero",
    # new aliases
    "e^e":     "ee",
    "ee":      "ee",
    "e^e^e":   "eee",
    "eee":     "eee",
    "exp(exp(x))": "expexp",
    "expexp":  "expexp",
    "ln(ln(x))": "lnln",
    "lnln":    "lnln",
}


def lookup(name: str) -> Optional[KnownFormula]:
    """Look up a formula by name or alias."""
    key = ALIASES.get(name, name)
    return LIBRARY.get(key)


def all_formulas() -> list[KnownFormula]:
    return list(LIBRARY.values())
