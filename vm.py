from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import mpmath


# The one true operator

def eml(x: mpmath.mpc, y: mpmath.mpc) -> mpmath.mpc:
    """eml(x, y) = exp(x) − ln(y)  (the EML Sheffer operator)."""
    return mpmath.exp(x) - mpmath.log(y)


# Number formatting

def fmt_num(z: mpmath.mpc, digits: int = 8) -> str:
    """Pretty-print a complex mpmath number."""
    try:
        re = float(mpmath.re(z))
        im = float(mpmath.im(z))
    except Exception:
        return str(z)

    if math.isnan(re) or math.isnan(im):
        return "NaN [warn]"
    if math.isinf(re) and im == 0:
        return ("+" if re > 0 else "−") + "∞"

    tol = max(1e-10, abs(re) * 1e-8, abs(im) * 1e-8)
    if abs(im) < tol:
        return f"{re:.{digits}g}"
    if abs(re) < tol:
        return f"{im:.{digits}g}·i"

    sign = "+" if im >= 0 else "−"
    return f"{re:.{digits}g} {sign} {abs(im):.{digits}g}·i"


def is_anomalous(z: mpmath.mpc) -> Optional[str]:
    """Return a warning string if z has domain issues, else None."""
    try:
        re = float(mpmath.re(z))
        im = float(mpmath.im(z))
    except Exception:
        return "bad value"
    if math.isnan(re) or math.isnan(im):
        return "NaN — domain explosion"
    if math.isinf(re) or math.isinf(im):
        return "±∞ — overflow"
    # Unexpectedly large imaginary part in a "real" context
    if abs(im) > 1e-8 and abs(im) > abs(re) * 1e-6:
        return f"complex result (im = {im:.4g})"
    return None


# Step record

@dataclass
class StepRecord:
    step: int
    token: str
    action: str                  # human-readable description
    stack_before: list           # snapshot before this token
    stack_after: list            # snapshot after
    eml_args: Optional[tuple] = None   # (x, y) if this was an E op
    eml_result: Optional[mpmath.mpc] = None
    warning: Optional[str] = None


# EML Machine

class EMLMachine:
    """
    A stack machine whose only instruction is the EML operator.

    Tokens:
      '1'         → push the constant 1
      'E'         → pop y (top), pop x, push eml(x, y)
      any letter  → push the bound variable value
    """

    def __init__(
        self,
        tokens: list[str],
        variables: dict[str, mpmath.mpc],
        prec: int = 50,
    ) -> None:
        mpmath.mp.dps = prec
        self.tokens = tokens
        self.variables: dict[str, mpmath.mpc] = {
            k: mpmath.mpc(v) for k, v in variables.items()
        }
        self.stack: list[mpmath.mpc] = []
        self.history: list[StepRecord] = []
        self.pc: int = 0

    # ------------------------------------------------------------------

    def step(self) -> Optional[StepRecord]:
        """Advance one token. Returns the StepRecord, or None if done."""
        if self.pc >= len(self.tokens):
            return None

        token = self.tokens[self.pc]
        stack_before = self.stack.copy()
        eml_args = None
        eml_result = None
        warning = None

        if token == "1":
            self.stack.append(mpmath.mpc(1))
            action = "push  1"

        elif token == "E":
            y = self.stack.pop()
            x = self.stack.pop()
            try:
                result = eml(x, y)
            except Exception as exc:
                result = mpmath.mpc("nan")
                warning = str(exc)
            self.stack.append(result)
            eml_args = (x, y)
            eml_result = result
            action = f"eml({fmt_num(x)}, {fmt_num(y)})  →  {fmt_num(result)}"
            if warning is None:
                warning = is_anomalous(result)

        else:
            val = self.variables[token]
            self.stack.append(val)
            action = f"push  {token} = {fmt_num(val)}"

        record = StepRecord(
            step=self.pc,
            token=token,
            action=action,
            stack_before=stack_before,
            stack_after=self.stack.copy(),
            eml_args=eml_args,
            eml_result=eml_result,
            warning=warning,
        )
        self.history.append(record)
        self.pc += 1
        return record

    # ------------------------------------------------------------------

    def run(self) -> mpmath.mpc:
        """Run to completion and return the top of stack."""
        while self.pc < len(self.tokens):
            self.step()
        return self.stack[-1] if self.stack else mpmath.mpc("nan")

    # ------------------------------------------------------------------

    @property
    def done(self) -> bool:
        return self.pc >= len(self.tokens)
