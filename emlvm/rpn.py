from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


# Tokenizer

def tokenize(program: str) -> list[str]:
    """
    Split an EML RPN string into tokens.

    Compact form:   '11xE1EE'   →  ['1','1','x','E','1','E','E']
    Spaced form:    '1 1 x E'   →  same result
    Multi-char var: '{theta} 1 E' → ['{theta}', '1', 'E']  (future)
    """
    tokens: list[str] = []
    i = 0
    while i < len(program):
        ch = program[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "{":
            j = program.index("}", i)
            tokens.append(program[i + 1 : j])
            i = j + 1
        else:
            tokens.append(ch)
            i += 1
    return tokens


# Validation

@dataclass
class ValidationResult:
    ok: bool
    message: str
    variables: set[str]       # variable names referenced
    max_depth: int
    final_depth: int


def validate(tokens: list[str], bound_vars: set[str] | None = None) -> ValidationResult:
    """
    Check that tokens form a valid, balanced EML RPN program.

    A valid program:
      - Never pops from an empty / depth-1 stack (E needs ≥ 2)
      - Ends with exactly 1 value on the stack
      - All referenced variables are in bound_vars (if given)
    """
    depth = 0
    max_depth = 0
    variables: set[str] = set()

    for i, tok in enumerate(tokens):
        if tok == "E":
            if depth < 2:
                return ValidationResult(
                    ok=False,
                    message=f"Stack underflow at position {i} (E needs ≥2 items, have {depth})",
                    variables=variables,
                    max_depth=max_depth,
                    final_depth=depth,
                )
            depth -= 1
        elif tok == "1":
            depth += 1
        else:
            variables.add(tok)
            depth += 1
        max_depth = max(max_depth, depth)

    if depth != 1:
        return ValidationResult(
            ok=False,
            message=f"Program leaves {depth} item(s) on stack (expected 1)",
            variables=variables,
            max_depth=max_depth,
            final_depth=depth,
        )

    if bound_vars is not None:
        unbound = variables - bound_vars
        if unbound:
            return ValidationResult(
                ok=False,
                message=f"Unbound variables: {', '.join(sorted(unbound))}",
                variables=variables,
                max_depth=max_depth,
                final_depth=depth,
            )

    return ValidationResult(
        ok=True,
        message="ok",
        variables=variables,
        max_depth=max_depth,
        final_depth=depth,
    )


# Program stats

def program_stats(tokens: list[str]) -> dict:
    """Return basic metrics about an EML program."""
    n_ops = tokens.count("E")
    n_ones = tokens.count("1")
    n_vars = len(tokens) - n_ops - n_ones
    var_names = sorted({t for t in tokens if t != "E" and t != "1"})
    return {
        "K": len(tokens),
        "operators": n_ops,
        "ones": n_ones,
        "var_tokens": n_vars,
        "variables": var_names,
        "depth": n_ops + 1,   # leaf count for a full binary tree
    }


# Valid RPN generator  (used by `emlvm golf`)

def gen_valid_rpn(num_ops: int, leaves: list[str]) -> Iterator[tuple[str, ...]]:
    """
    Generate all syntactically valid RPN programs with exactly `num_ops`
    E-operators and (num_ops + 1) leaf tokens chosen from `leaves`.

    Total count = Catalan(num_ops) × |leaves|^(num_ops+1).

    Uses backtracking with pruning on stack-depth bounds.
    """
    n_leaves_total = num_ops + 1
    buf: list[str] = []

    def _gen(depth: int, ops_left: int, leaves_left: int) -> Iterator[tuple[str, ...]]:
        # Pruning: can we still land on depth=1?
        min_final = depth - ops_left        # apply all remaining E's
        max_final = depth + leaves_left     # push all remaining leaves
        if not (min_final <= 1 <= max_final):
            return

        if ops_left == 0 and leaves_left == 0:
            if depth == 1:
                yield tuple(buf)
            return

        # Push a leaf
        if leaves_left > 0:
            for leaf in leaves:
                buf.append(leaf)
                yield from _gen(depth + 1, ops_left, leaves_left - 1)
                buf.pop()

        # Apply E (requires depth ≥ 2)
        if ops_left > 0 and depth >= 2:
            buf.append("E")
            yield from _gen(depth - 1, ops_left - 1, leaves_left)
            buf.pop()

    yield from _gen(0, num_ops, n_leaves_total)


def gen_programs_up_to_k(max_k: int, leaves: list[str]) -> Iterator[tuple[str, ...]]:
    """
    Yield all valid RPN programs with K ≤ max_k.
    Valid K values are 1, 3, 5, ... (always odd for complete binary trees).
    K=1 is a single leaf (trivial program).
    """
    # K=1: trivial, single leaf
    for leaf in leaves:
        yield (leaf,)
    # K=3,5,7,...  ↔  num_ops = 1,2,3,...
    k = 3
    while k <= max_k:
        num_ops = (k - 1) // 2
        yield from gen_valid_rpn(num_ops, leaves)
        k += 2
