from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Optional


# Template programs  (variable placeholder is always lowercase 'x')

UNARY: dict[str, Optional[list[str]]] = {
    "exp":   ["x", "1", "E"],
    "ln":    ["1", "1", "x", "E", "1", "E", "E"],
    "id":    ["1", "1", "x", "1", "E", "E", "1", "E", "E"],
    "neg":   ["1", "1", "1", "1", "1", "E", "1", "E", "E", "E", "E", "x", "1", "E", "E"],
    "inv":   ["1", "1", "1", "1", "1", "E", "1", "E", "E", "E", "E", "x", "E", "1", "E"],
    "sqr":   ["1", "1", "1", "1", "x", "E", "E", "1", "E", "E", "x", "E", "1", "E", "E", "1", "E"],
    "sqrt":  None,   # K=43, find with: emlvm golf sqrt
    "sin":   None,   # K≥75, very long
    "cos":   None,   # K≥75
    "sinh":  None,
    "cosh":  None,
}

# Binary operation templates (use 'x' for left operand, 'y' for right)
BINARY: dict[str, Optional[list[str]]] = {
    "sub":  ["1", "1", "x", "E", "1", "E", "E", "y", "1", "E", "E"],
    "add":  ["1", "1", "1", "1", "x", "1", "E", "E", "E", "1", "E", "E",
             "y", "1", "E", "E", "1", "E", "E"],
    "mul":  ["1", "1", "1", "1", "x", "E", "E", "1", "E", "E", "y", "E", "1", "E", "E", "1", "E"],
    "div":  ["1", "1", "1", "1", "x", "E", "1", "E", "E", "E", "1", "E", "E",
             "1", "1", "y", "E", "1", "E", "E", "1", "E", "E", "1", "E"],
    "pow":  ["1", "1", "1", "1", "y", "E", "E", "1", "E", "E",
             "1", "1", "x", "E", "1", "E", "E", "E", "1", "E", "E", "1", "E", "1", "E"],
}

CONSTANTS: dict[str, list[str]] = {
    "e":    ["1", "1", "E"],               # eml(1,1) = e
    "zero": ["1", "1", "1", "E", "1", "E", "E"],  # = 0
    "one":  ["1"],
}

# Map Python ast function names to canonical keys
FUNC_ALIASES: dict[str, str] = {
    "exp": "exp", "ln": "ln", "log": "ln",
    "neg": "neg", "negate": "neg",
    "inv": "inv", "reciprocal": "inv",
    "id": "id", "identity": "id",
    "sqr": "sqr", "square": "sqr",
    "sqrt": "sqrt",
    "sin": "sin", "cos": "cos", "tan": "tan",
    "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
    "abs": None,  # unsupported
    # Binary function call aliases (resolved via BINARY templates)
    "add": "add", "sub": "sub", "mul": "mul", "div": "div", "pow": "pow",
}


# Compositional substitution

def _substitute(program: list[str], var: str, replacement: list[str]) -> list[str]:
    result = []
    for tok in program:
        if tok == var:
            result.extend(replacement)
        else:
            result.append(tok)
    return result


def _substitute_multi(
    program: list[str], replacements: dict[str, list[str]]
) -> list[str]:
    """Simultaneously substitute multiple variables to avoid cross-contamination."""
    result = []
    for tok in program:
        if tok in replacements:
            result.extend(replacements[tok])
        else:
            result.append(tok)
    return result


# Compile result

@dataclass
class CompileResult:
    tokens: Optional[list[str]] = None
    rpn: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.tokens is not None

    @property
    def k(self) -> Optional[int]:
        return len(self.tokens) if self.tokens else None


# Compiler — AST walker

class _Compiler(ast.NodeVisitor):
    def __init__(self, input_var: str):
        self.var = input_var
        self.warnings: list[str] = []
        self.unsupported: list[str] = []

    def compile(self, expr_str: str) -> Optional[list[str]]:
        # Pre-process common notations
        s = expr_str.strip()
        # caret to Python power
        s = s.replace("^", "**")

        try:
            tree = ast.parse(s, mode="eval")
        except SyntaxError as e:
            self.warnings.append(f"Parse error: {e}")
            return None

        return self._node(tree.body)

    # ------------------------------------------------------------------

    def _node(self, node: ast.expr) -> Optional[list[str]]:
        if isinstance(node, ast.Name):
            return self._name(node.id)
        if isinstance(node, ast.Constant):
            return self._const(node.value)
        if isinstance(node, ast.UnaryOp):
            return self._unary_op(node)
        if isinstance(node, ast.Call):
            return self._call(node)
        if isinstance(node, ast.BinOp):
            return self._bin_op(node)
        self.warnings.append(f"Unsupported expression type: {type(node).__name__}")
        return None

    def _name(self, name: str) -> Optional[list[str]]:
        if name == self.var:
            return [name]
        if name == "e":
            return CONSTANTS["e"].copy()
        if name in ("pi", "π"):
            self.unsupported.append("π")
            self.warnings.append("π is computable in EML but requires K=193 (not in compiler yet).")
            return None
        # Treat as another input variable (multi-var programs)
        if len(name) == 1 and name.islower() and name != "E":
            return [name]
        self.warnings.append(f"Unknown symbol: '{name}'")
        return None

    def _const(self, val) -> Optional[list[str]]:
        if val == 1 or val == 1.0:
            return ["1"]
        if val == 0 or val == 0.0:
            return CONSTANTS["zero"].copy()
        if isinstance(val, int) and val >= 2:
            if val > 20:
                self.unsupported.append(str(val))
                self.warnings.append(
                    f"Integer {val} too large for naive compilation (K grows as ~18n). "
                    f"Try expressing it via exp/ln."
                )
                return None
            # Build integer n as 1 + 1 + ... + 1  (n times) using add
            result = ["1"]
            for _ in range(val - 1):
                result = _substitute(BINARY["add"], "x", result)
                result = _substitute(result, "y", ["1"])
            return result
        if isinstance(val, int) and val <= -1:
            if val < -20:
                self.unsupported.append(str(val))
                self.warnings.append(
                    f"Integer {val} too large for naive compilation. "
                    f"Try expressing it via exp/ln."
                )
                return None
            # Build negative integer: neg(|val|)
            pos = self._const(-val)
            if pos is None:
                return None
            return _substitute(UNARY["neg"], "x", pos)
        self.unsupported.append(str(val))
        self.warnings.append(
            f"Constant {val} requires a dedicated EML program (not in compiler). "
            f"Try expressing it via exp/ln or integer arithmetic."
        )
        return None

    def _unary_op(self, node: ast.UnaryOp) -> Optional[list[str]]:
        inner = self._node(node.operand)
        if inner is None:
            return None
        if isinstance(node.op, ast.USub):
            return self._apply_unary("neg", inner)
        if isinstance(node.op, ast.UAdd):
            return inner
        self.warnings.append(f"Unsupported unary op: {type(node.op).__name__}")
        return None

    def _call(self, node: ast.Call) -> Optional[list[str]]:
        if not isinstance(node.func, ast.Name):
            self.warnings.append("Only named function calls are supported.")
            return None
        func_name = node.func.id
        canonical = FUNC_ALIASES.get(func_name)

        # Explicitly unsupported (mapped to None in FUNC_ALIASES)
        if func_name in FUNC_ALIASES and canonical is None:
            self.unsupported.append(func_name)
            self.warnings.append(
                f"'{func_name}' is recognized but not yet supported in EML."
            )
            return None

        if canonical is None and func_name not in UNARY:
            self.warnings.append(f"Unknown function: '{func_name}'")
            return None
        canonical = canonical or func_name

        if len(node.args) == 1:
            inner = self._node(node.args[0])
            if inner is None:
                return None
            return self._apply_unary(canonical, inner)

        if len(node.args) == 2:
            return self._apply_binary_call(canonical, node.args)

        self.warnings.append(
            f"Function '{func_name}' called with {len(node.args)} args (expected 1 or 2)."
        )
        return None

    def _apply_binary_call(self, func: str, args: list) -> Optional[list[str]]:
        """Handle binary function call syntax like add(x, y), mul(x, y)."""
        template = BINARY.get(func)
        if template is None:
            self.unsupported.append(func)
            self.warnings.append(
                f"Binary function '{func}' EML program TBD. "
                f"Run: emlvm golf {func} to discover the program."
            )
            return None
        left = self._node(args[0])
        if left is None:
            return None
        right = self._node(args[1])
        if right is None:
            return None
        return _substitute_multi(template, {"x": left, "y": right})

    def _bin_op(self, node: ast.BinOp) -> Optional[list[str]]:
        op_map = {
            ast.Mult: "mul",
            ast.Add:  "add",
            ast.Sub:  "sub",
            ast.Div:  "div",
            ast.Pow:  "pow",
        }
        name = op_map.get(type(node.op))
        if name is None:
            self.warnings.append(f"Unsupported binary op: {type(node.op).__name__}")
            return None

        template = BINARY.get(name)
        if template is None:
            self.warnings.append(
                f"Binary op '{name}' EML program TBD. "
                f"Run: emlvm golf {name} to discover the program."
            )
            self.unsupported.append(name)
            return None

        left = self._node(node.left)
        if left is None:
            return None
        right = self._node(node.right)
        if right is None:
            return None

        return _substitute_multi(template, {"x": left, "y": right})

    def _apply_unary(self, func: str, inner: list[str]) -> Optional[list[str]]:
        prog = UNARY.get(func)
        if prog is None:
            k_hint = {"neg": 15, "inv": 15, "sqr": "?", "sqrt": 43}.get(func, "?")
            self.unsupported.append(func)
            self.warnings.append(
                f"{func}(x) EML program TBD (K≈{k_hint}). "
                f"Run: emlvm golf {func} --max-k {k_hint if isinstance(k_hint, int) else 21}"
            )
            return None
        return _substitute(prog, "x", inner)


# Public API

def compile_expression(expr_str: str, input_var: str = "x") -> CompileResult:
    """
    Compile a mathematical expression to EML RPN tokens.

    Examples
    --------
    >>> compile_expression("exp(x)").rpn
    'x1E'
    >>> compile_expression("exp(ln(x))").rpn
    '11xE1EE1E'
    >>> compile_expression("ln(exp(x))").rpn
    '11x1EE1EE'
    """
    compiler = _Compiler(input_var=input_var)
    tokens = compiler.compile(expr_str)
    result = CompileResult(
        tokens=tokens,
        rpn="".join(tokens) if tokens else None,
        warnings=compiler.warnings,
        unsupported=compiler.unsupported,
    )
    return result
