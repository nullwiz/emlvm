"""
EMLVM CLI — all commands.

Usage examples:
  emlvm run   '11xE1EE' --var x=2
  emlvm trace '11xE1EE' --var x=2
  emlvm step  '11xE1EE' --var x=2
  emlvm disasm '11xE1EE'
  emlvm tree  '11xE1EE'
  emlvm known
  emlvm check '11xE1EE' --expect ln --var x=2
  emlvm golf  neg --max-k 15
  emlvm wezterm '11xE1EE' --var x=2
"""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import mpmath
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich import box

from . import known as lib
from .rpn import gen_programs_up_to_k, program_stats, tokenize, validate
from .tracer import (
    render_disasm,
    render_header,
    render_result,
    render_trace_table,
    C_RES, C_WARN, C_DIM, C_OP, C_VAR, C_ONE,
)
from .tree import build_rich_tree, build_tree
from .vm import EMLMachine, fmt_num

console = Console()

app = typer.Typer(
    name="emlvm",
    help=(
        "[bold magenta]EMLVM[/] — single-instruction EML stack machine\n\n"
        "  [cyan]eml(x, y) = exp(x) − ln(y)[/]\n\n"
        "Combined with the constant [cyan]1[/], this single operator generates "
        "every elementary function."
    ),
    rich_markup_mode="rich",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VarOpt = Annotated[
    list[str],
    typer.Option("--var", "-v", help="Variable binding: [cyan]x=2.5[/]  (repeatable)"),
]
PrecOpt = Annotated[int, typer.Option("--prec", help="mpmath decimal precision")]
ModeOpt = Annotated[
    str,
    typer.Option("--mode", help="Output mode: [cyan]auto[/] | [cyan]real[/] | [cyan]complex[/]"),
]


def _parse_vars(var_strings: list[str]) -> dict[str, mpmath.mpc]:
    out: dict[str, mpmath.mpc] = {}
    for vs in var_strings:
        if "=" not in vs:
            console.print(f"[red]Bad --var syntax:[/] expected [cyan]name=value[/], got [yellow]{vs!r}[/]")
            raise typer.Exit(1)
        name, _, value = vs.partition("=")
        try:
            out[name.strip()] = mpmath.mpc(value.strip())
        except Exception:
            console.print(f"[red]Cannot parse value[/] [yellow]{value!r}[/] as a number.")
            raise typer.Exit(1)
    return out


def _load_program(program: str, var: list[str], prec: int):
    """Tokenize + validate. Returns (tokens, variables_dict) or exits."""
    tokens = tokenize(program)
    variables = _parse_vars(var)
    v = validate(tokens, bound_vars=set(variables.keys()))
    if not v.ok:
        console.print(f"[red]Invalid program:[/] {v.message}")
        raise typer.Exit(1)
    return tokens, variables




@app.command()
def run(
    program: Annotated[str, typer.Argument(help="RPN program, e.g. [cyan]'11xE1EE'[/]")],
    var:  VarOpt  = [],
    prec: PrecOpt = 50,
    mode: ModeOpt = "auto",
) -> None:
    """Evaluate an EML program and print the result."""
    tokens, variables = _load_program(program, var, prec)
    render_header(console, program, variables, subtitle="mode: run")
    machine = EMLMachine(tokens, variables, prec=prec)
    result = machine.run()
    render_result(result, mode, console)




@app.command()
def trace(
    program: Annotated[str, typer.Argument(help="RPN program")],
    var:  VarOpt  = [],
    prec: PrecOpt = 50,
    mode: ModeOpt = "auto",
) -> None:
    """Show a full step-by-step execution trace with stack state."""
    tokens, variables = _load_program(program, var, prec)
    render_header(console, program, variables, subtitle="mode: trace")
    machine = EMLMachine(tokens, variables, prec=prec)
    machine.run()
    render_trace_table(machine.history, console)
    render_result(machine.stack[-1], mode, console)




@app.command()
def step(
    program: Annotated[str, typer.Argument(help="RPN program")],
    var:  VarOpt  = [],
    prec: PrecOpt = 50,
    mode: ModeOpt = "auto",
) -> None:
    """Interactive step-through debugger. Press [Enter] to advance, [q] to quit."""
    tokens, variables = _load_program(program, var, prec)
    render_header(console, program, variables, subtitle="mode: step  —  [Enter] advance  [q] quit")
    machine = EMLMachine(tokens, variables, prec=prec)

    while not machine.done:
        record = machine.step()
        if record is None:
            break
        render_trace_table([record], console)
        if machine.done:
            break
        try:
            key = console.input(f"  [dim](step {record.step + 1}/{len(tokens)})[/] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Interrupted.[/]")
            raise typer.Exit(0)
        if key.strip().lower() == "q":
            raise typer.Exit(0)

    if machine.stack:
        render_result(machine.stack[-1], mode, console)




@app.command()
def disasm(
    program: Annotated[str, typer.Argument(help="RPN program")],
    var:  VarOpt  = [],
    prec: PrecOpt = 50,
) -> None:
    """Annotated disassembly listing. Runs the program to populate action text."""
    tokens, variables = _load_program(program, var, prec)
    stats = program_stats(tokens)
    render_header(
        console, program, variables,
        subtitle=f"K={stats['K']}  ops={stats['operators']}  max-depth≈{stats['depth']}",
    )
    machine = EMLMachine(tokens, variables, prec=prec)
    machine.run()
    render_disasm(tokens, machine.history, console)




@app.command()
def tree(
    program: Annotated[str, typer.Argument(help="RPN program")],
) -> None:
    """Render the EML expression tree. [cyan]x →[/] = exp input, [cyan]y →[/] = ln input."""
    tokens = tokenize(program)
    v = validate(tokens)
    if not v.ok:
        console.print(f"[red]Invalid program:[/] {v.message}")
        raise typer.Exit(1)

    root = build_tree(tokens)
    stats = program_stats(tokens)
    rich_tree = build_rich_tree(
        root,
        title=f"EML Tree  [dim]({program})[/]  K={stats['K']}",
    )
    console.print(
        Panel(rich_tree, border_style="magenta", padding=(1, 3))
    )




@app.command()
def known(
    pattern: Annotated[Optional[str], typer.Argument(help="Filter by name substring")] = None,
) -> None:
    """List all known EML programs from the built-in library."""
    formulas = lib.all_formulas()
    if pattern:
        formulas = [f for f in formulas if pattern.lower() in f.name.lower()
                    or pattern.lower() in f.description.lower()]

    tbl = Table(
        box=box.ROUNDED,
        border_style="dim magenta",
        header_style="bold white on #1a1a2e",
        show_lines=True,
        title="[bold magenta]EML Formula Library[/]",
    )
    tbl.add_column("Name",        style="bold cyan",   width=8)
    tbl.add_column("Program",     style="bold yellow",  width=14)
    tbl.add_column("K",           style=C_DIM,          width=5, justify="right")
    tbl.add_column("Description", min_width=24)
    tbl.add_column("Source",      width=9)

    src_style = {"paper": "green", "derived": "cyan", "tbd": "red", "search": "yellow"}

    for f in formulas:
        prog = f.program or "[dim]TBD[/]"
        k    = str(f.k) if f.k else "?"
        src  = f"[{src_style.get(f.source, 'white')}]{f.source}[/]"
        tbl.add_row(f.name, prog, k, f.description, src)

    console.print(tbl)
    console.print(
        f"\n[dim]  Source legend: "
        "[green]paper[/] = cited in arXiv 2603.21852  "
        "[cyan]derived[/] = manually derived  "
        "[red]tbd[/] = run [bold]emlvm golf <name>[/] to find[/]\n"
    )




@app.command()
def check(
    program: Annotated[str, typer.Argument(help="RPN program")],
    expect:  Annotated[str, typer.Option("--expect", "-e", help="Expected function name (e.g. ln) or value")],
    var:  VarOpt  = [],
    prec: PrecOpt = 50,
    tol:  Annotated[float, typer.Option("--tol", help="Tolerance for numeric match")] = 1e-10,
) -> None:
    """Verify that a program matches a known formula or a numeric value."""
    tokens, variables = _load_program(program, var, prec)
    machine = EMLMachine(tokens, variables, prec=prec)
    result = machine.run()
    actual = mpmath.re(result)

    # Python oracles for TBD formulas
    ORACLES = {
        "neg": lambda v: -list(v.values())[0],
        "inv": lambda v: mpmath.mpc(1) / list(v.values())[0],
        "mul": lambda v: list(v.values())[0] * list(v.values())[1],
        "add": lambda v: list(v.values())[0] + list(v.values())[1],
    }

    # Resolve expected value
    formula = lib.lookup(expect)
    if formula and formula.program:
        ref_tokens = tokenize(formula.program)
        ref_machine = EMLMachine(ref_tokens, variables, prec=prec)
        expected = mpmath.re(ref_machine.run())
        expect_label = f"{formula.description} = {float(expected):.10g}"
    elif formula and formula.name in ORACLES:
        expected = mpmath.re(ORACLES[formula.name](variables))
        expect_label = f"{formula.description} = {float(expected):.10g}"
    else:
        try:
            expected = mpmath.mpf(expect)
            expect_label = f"{float(expected):.10g}"
        except Exception:
            console.print(f"[red]Cannot resolve expected value:[/] {expect!r}")
            raise typer.Exit(1)

    diff = abs(actual - expected)
    ok = diff < mpmath.mpf(tol)

    render_header(console, program, variables, subtitle="mode: check")
    console.print(f"  Computed : [{C_RES}]{float(actual):.15g}[/]")
    console.print(f"  Expected : [{C_RES}]{expect_label}[/]")
    console.print(f"  |diff|   : [{C_DIM}]{float(diff):.3e}[/]")

    if ok:
        console.print(Panel("[bold green][ok]  MATCH[/]", border_style="green"))
    else:
        console.print(Panel(f"[bold red][fail]  MISMATCH  (diff = {float(diff):.3e})[/]", border_style="red"))
        raise typer.Exit(1)




@app.command()
def golf(
    target: Annotated[str, typer.Argument(
        help="Target: library name (e.g. [cyan]neg[/]) or a numeric value"
    )],
    var:    VarOpt = [],
    max_k:  Annotated[int,   typer.Option("--max-k",  help="Max K to search")] = 15,
    all_:   Annotated[bool,  typer.Option("--all",    help="Show all matches")] = False,
    prec:   PrecOpt = 50,
) -> None:
    """
     Exhaustive search for the shortest EML program matching a target.

    Uses the Schanuel-heuristic: evaluate at algebraically independent
    transcendental test points and compare numerically.

    Examples:
      emlvm golf neg --max-k 15
      emlvm golf 0
      emlvm golf 3.14159265
    """
    mpmath.mp.dps = prec

    # ── Resolve target function ──────────────────────────────────────────
    formula = lib.lookup(target)
    variables = _parse_vars(var)

    # Transcendental test points (Euler-Mascheroni, Glaisher-Kinkelin, ...)
    TEST_POINTS = {
        "x": mpmath.euler,       # γ ≈ 0.5772
        "y": mpmath.mpf("1.28242712910062263687534256887"),  # Glaisher A
    }

    # Python oracles for TBD formulas — used when formula.program is None
    ORACLES: dict[str, callable] = {
        "neg": lambda v: -v["x"],
        "inv": lambda v: mpmath.mpc(1) / v["x"],
        "mul": lambda v: v["x"] * v["y"],
        "add": lambda v: v["x"] + v["y"],
        "sub": lambda v: v["x"] - v["y"],
        "sqrt": lambda v: mpmath.sqrt(v["x"]),
        "sqr":  lambda v: v["x"] ** 2,
        "half": lambda v: v["x"] / 2,
        "sin":  lambda v: mpmath.sin(v["x"]),
        "cos":  lambda v: mpmath.cos(v["x"]),
        "pi":   lambda v: mpmath.pi,
        "zero": lambda v: mpmath.mpc(0),
    }

    def get_target_val(test_vars: dict) -> Optional[mpmath.mpc]:
        """Return the target value at the test point."""
        if formula and formula.program:
            ref_toks = tokenize(formula.program)
            m = EMLMachine(ref_toks, test_vars, prec=prec)
            return m.run()
        # TBD formula with known oracle
        if formula and formula.name in ORACLES:
            return ORACLES[formula.name](test_vars)
        # Numeric target
        try:
            return mpmath.mpc(target)
        except Exception:
            return None

    # Determine variable names needed
    if formula:
        leaf_vars = formula.variables
        description = formula.description
        known_k = formula.k
    else:
        leaf_vars = sorted(variables.keys()) or []
        description = target
        known_k = None

    leaves = ["1"] + leaf_vars
    test_vars = {k: TEST_POINTS.get(k, mpmath.mpc(variables.get(k, mpmath.mpc(2)))) for k in leaf_vars}
    target_val = get_target_val(test_vars)

    if target_val is None:
        console.print(f"[red]Cannot resolve target:[/] {target!r}")
        raise typer.Exit(1)

    console.print(
        Panel(
            f"Target : [cyan]{description}[/]\n"
            f"Leaves : [yellow]{' '.join(leaves)}[/]\n"
            f"Max K  : [dim]{max_k}[/]\n"
            f"Test   : " + "  ".join(f"[yellow]{k}[/]=[green]{fmt_num(v)}[/]" for k, v in test_vars.items()),
            title="[bold magenta]EMLVM Golf[/]",
            border_style="magenta",
        )
    )

    found: list[tuple[int, str]] = []

    # ── numpy fast screen (handles IEEE754 ±∞ in complex, unlike cmath) ────
    import math
    import numpy as np
    from .rpn import gen_valid_rpn

    # Two algebraically independent transcendental test points
    TEST_POINTS_2 = {
        "x": mpmath.mpf("1.28242712910062263687534256887"),  # Glaisher A
        "y": mpmath.euler,
    }
    test_vars2 = {k: TEST_POINTS_2.get(k, mpmath.mpc(3)) for k in leaf_vars}
    target_val2 = get_target_val(test_vars2)

    # numpy complex128 versions (C speed, proper ±∞ handling)
    fast_vars  = {k: np.complex128(complex(v)) for k, v in test_vars.items()}
    fast_vars2 = {k: np.complex128(complex(v)) for k, v in test_vars2.items()}
    fast_target  = np.complex128(complex(target_val))
    fast_target2 = np.complex128(complex(target_val2)) if target_val2 is not None else None

    def fast_eval(toks: list[str], fvars: dict) -> np.complex128:
        stk: list[np.complex128] = []
        for t in toks:
            if t == "1":
                stk.append(np.complex128(1.0))
            elif t == "E":
                y = stk.pop(); x = stk.pop()
                stk.append(np.exp(x) - np.log(y))
            else:
                stk.append(fvars[t])
        return stk[-1]

    SCREEN_TOL = 1e-7
    VERIFY_TOL = mpmath.mpf(10) ** (-prec // 2)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Searching…", total=None)

        for k in range(1, max_k + 1, 2):
            count = 0

            if k == 1:
                programs = [(leaf,) for leaf in leaves]
            else:
                num_ops = (k - 1) // 2
                programs = gen_valid_rpn(num_ops, leaves)

            for prog_tuple in programs:
                count += 1
                if count % 20000 == 0:
                    progress.update(task, description=f"[cyan]K={k}  checked={count:,}[/]")

                toks = list(prog_tuple)
                try:
                    with np.errstate(all="ignore"):   # allow inf/nan without warnings
                        res = fast_eval(toks, fast_vars)
                    if not np.isfinite(res.real) or not np.isfinite(res.imag):
                        # Allow programs that produce ±inf as intermediates but
                        # yield finite final values — verified via mpmath below
                        pass
                    if abs(res - fast_target) > SCREEN_TOL:
                        continue
                    # Second test point
                    if fast_target2 is not None:
                        with np.errstate(all="ignore"):
                            res2 = fast_eval(toks, fast_vars2)
                        if abs(res2 - fast_target2) > SCREEN_TOL:
                            continue
                    # Full mpmath verify
                    m = EMLMachine(toks, test_vars, prec=prec)
                    result = m.run()
                    if abs(result - target_val) < VERIFY_TOL:
                        m2 = EMLMachine(toks, test_vars2, prec=prec)
                        result2 = m2.run()
                        if target_val2 is None or abs(result2 - target_val2) < VERIFY_TOL:
                            prog_str = "".join(prog_tuple)
                            found.append((k, prog_str))
                            progress.stop()
                            console.print(f"\n[bold green][ok]  Found K={k}:[/]  [yellow]{prog_str}[/]")
                            if not all_:
                                break
                            progress.start()
                except Exception:
                    continue

            if found and not all_:
                break

    if found:
        console.print("\n[bold green]Results:[/]")
        for k_found, prog_str in found:
            console.print(f"  K={k_found}  [bold yellow]{prog_str}[/]")
        console.print(
            "\n[dim]Verify with:[/]  "
            f"[cyan]emlvm check '{found[0][1]}' --expect {target} "
            + "  ".join(f"--var {k}=…" for k in leaf_vars) + "[/]"
        )
        console.print(
            f"[dim]Trace with:[/]   "
            f"[cyan]emlvm trace '{found[0][1]}' "
            + "  ".join(f"--var {k}=2" for k in leaf_vars) + "[/]"
        )
    else:
        console.print(
            f"\n[yellow]No program found up to K={max_k}.[/]\n"
            f"  → Try [cyan]--max-k {max_k + 4}[/]\n"
            f"  → numpy screens IEEE754 ±∞ intermediates correctly."
        )




@app.command()
def plot(
    program: Annotated[str,  typer.Argument(help="EML RPN program to plot")],
    xvar:    Annotated[str,  typer.Option("--xvar",    help="Variable to sweep")] = "x",
    xrange:  Annotated[str,  typer.Option("--range",   help="x range  start:end")] = "0.1:10",
    steps:   Annotated[int,  typer.Option("--steps",   help="Sample points")] = 80,
    compare: Annotated[Optional[str], typer.Option("--compare", help="Compare vs known formula")] = None,
    log_x:   Annotated[bool, typer.Option("--log-x",  help="Logarithmic x axis")] = False,
    prec:    PrecOpt = 30,
) -> None:
    """ Plot an EML function as a terminal graph."""
    try:
        import plotext as plt
    except ImportError:
        console.print("[red]plotext not installed.[/]  Run: [cyan]pip install plotext[/]")
        raise typer.Exit(1)
    import math as _math

    tokens = tokenize(program)
    v = validate(tokens, bound_vars={xvar})
    if not v.ok:
        console.print(f"[red]{v.message}[/]"); raise typer.Exit(1)

    try:
        x_start, x_end = map(float, xrange.split(":"))
    except ValueError:
        console.print("[red]Bad --range.[/]  Use [cyan]start:end[/] e.g. [cyan]0.01:10[/]")
        raise typer.Exit(1)

    if log_x:
        lx0, lx1 = _math.log(x_start), _math.log(x_end)
        xs = [_math.exp(lx0 + (lx1 - lx0) * i / steps) for i in range(steps + 1)]
    else:
        xs = [x_start + (x_end - x_start) * i / steps for i in range(steps + 1)]

    def _eval_at(toks, xv):
        try:
            m = EMLMachine(toks, {xvar: mpmath.mpc(xv)}, prec=prec)
            return float(mpmath.re(m.run()))
        except Exception:
            return float("nan")

    ys_eml = [_eval_at(tokens, xv) for xv in xs]

    ys_ref: list[float] = []
    if compare:
        formula = lib.lookup(compare)
        if formula and formula.program:
            ref_toks = tokenize(formula.program)
            ys_ref = [_eval_at(ref_toks, xv) for xv in xs]
        else:
            console.print(f"[yellow]Warning:[/] '{compare}' has no EML program yet.")

    plt.clear_figure()
    plt.theme("dark")
    pairs = [(x, y) for x, y in zip(xs, ys_eml) if _math.isfinite(y)]
    if pairs:
        px, py = zip(*pairs)
        plt.plot(list(px), list(py), label=program, color="magenta")
    if ys_ref:
        rpairs = [(x, y) for x, y in zip(xs, ys_ref) if _math.isfinite(y)]
        if rpairs:
            rx, ry = zip(*rpairs)
            plt.plot(list(rx), list(ry), label=compare, color="cyan")

    plt.title(f"EML: {program}  ({xvar} ∈ [{x_start}, {x_end}])")
    plt.xlabel(xvar)
    plt.ylabel(f"f({xvar})")
    plt.show()
    console.print(f"\n[dim]Trace:[/] [cyan]emlvm trace '{program}' --var {xvar}=2[/]")




@app.command(name="compile")
def compile_(
    expression: Annotated[str,   typer.Argument(help="Math expression, e.g. [cyan]exp(ln(x))[/]")],
    input_var:  Annotated[str,   typer.Option("--var",    help="Input variable")] = "x",
    show_tree:  Annotated[bool,  typer.Option("--tree",   help="Render EML tree")] = False,
    verify_out: Annotated[bool,  typer.Option("--verify", help="Evaluate at test point")] = True,
    test_val:   Annotated[float, typer.Option("--at",     help="Test value")] = 2.0,
    target:     Annotated[str,   typer.Option("--target", help="Compilation target: rpn or dag")] = "rpn",
) -> None:
    """
     Compile a mathematical expression to EML RPN.

    Applies compositional substitution: f(g(x)) → replace x in P_f with P_g tokens.

    Examples:
      emlvm compile 'exp(x)'
      emlvm compile 'ln(exp(x))'
      emlvm compile 'exp(ln(exp(x)))'
    """
    from .compiler import compile_expression

    render_header(console, expression, {}, subtitle="mode: compile")
    cr = compile_expression(expression, input_var=input_var)

    for w in cr.warnings:
        console.print(f"  [yellow][warn][/]  {w}")

    if not cr.ok:
        console.print(Panel("[red]Compilation failed[/]", border_style="red"))
        if cr.unsupported:
            console.print(
                f"  Unsupported: {', '.join(set(cr.unsupported))}\n"
                f"  Discover them with [cyan]emlvm golf <name>[/]"
            )
        raise typer.Exit(1)

    if target == "dag":
        from .tree import build_tree, compute_dag
        root = build_tree(cr.tokens)
        insts = compute_dag(root)
        console.print(f"\n  Input      : [cyan]{expression}[/]")
        console.print(f"  Target     : [bold magenta]DAG[/]")
        for ins in insts:
            console.print(f"    [yellow]{ins}[/]")
        console.print(f"  Registers  : [dim]{len(insts)}[/]")
    else:
        console.print(f"\n  Input      : [cyan]{expression}[/]")
        console.print(f"  EML RPN    : [bold yellow]{cr.rpn}[/]")
        console.print(f"  K (length) : [dim]{cr.k}[/]  (E-operators: {cr.rpn.count('E')})")

    if show_tree:
        root = build_tree(cr.tokens)
        rt = build_rich_tree(root, title=f"EML Tree  [{cr.rpn}]")
        console.print(Panel(rt, border_style="magenta", padding=(1, 3)))

    has_var = any(t not in ("1", "E") for t in cr.tokens)
    if verify_out and has_var:
        try:
            m = EMLMachine(cr.tokens, {input_var: mpmath.mpc(test_val)}, prec=50)
            result = float(mpmath.re(m.run()))
            console.print(
                f"\n  Test @{input_var}={test_val}: [dim]{expression}[/] = [{C_RES}]{result:.12g}[/]"
            )
        except Exception:
            pass

    console.print(f"\n  [dim]Trace:[/] [cyan]emlvm trace '{cr.rpn}' --var {input_var}={test_val}[/]")
    if has_var:
        console.print(f"  [dim]Plot:[/]  [cyan]emlvm plot '{cr.rpn}' --xvar {input_var} --range 0.1:5[/]")




@app.command()
def dag(
    program: Annotated[str, typer.Argument(help="RPN program to compile to DAG")],
) -> None:
    """Convert an EML program into a Directed Acyclic Graph (DAG) of register operations."""
    from .tree import build_tree, compute_dag
    tokens = tokenize(program)
    v = validate(tokens)
    if not v.ok:
        console.print(f"[red]Invalid program:[/] {v.message}")
        raise typer.Exit(1)
        
    root = build_tree(tokens)
    insts = compute_dag(root)
    render_header(console, program, {}, subtitle=f"mode: dag (compression/CSE)  ops: {len(insts)}")
    
    for ins in insts:
        console.print(f"  [yellow]{ins}[/]")




@app.command()
def derive(
    program: Annotated[str, typer.Argument(help="RPN program to symbolically differentiate")],
    var: Annotated[str, typer.Option("--var", help="Variable to differentiate with respect to")] = "x",
) -> None:
    """Output the symbolic derivative of an EML program using SymPy."""
    from .sym_eval import sym_derive
    tokens = tokenize(program)
    v = validate(tokens, bound_vars={var})
    if not v.ok:
        console.print(f"[red]Invalid program:[/] {v.message}")
        raise typer.Exit(1)
        
    render_header(console, program, {}, subtitle="mode: derive")
    try:
        orig, deriv = sym_derive(tokens, var=var)
        console.print(f"  Original : [cyan]{orig}[/]")
        console.print(f"  d/d{var}     : [bold yellow]{deriv}[/]")
    except Exception as e:
        console.print(f"[red]Derivation failed:[/] {e}")




@app.command()
def verify(
    prec: PrecOpt = 50,
    tol:  Annotated[float, typer.Option("--tol", help="Match tolerance")] = 1e-12,
) -> None:
    """
     Verify every known EML program against Python reference values.

    Evaluates each program at two independent transcendental test points
    (Euler-Mascheroni γ and Glaisher-Kinkelin A).
    """
    ORACLES = {
        "e":      lambda v: mpmath.e,
        "zero":   lambda v: mpmath.mpc(0),
        "exp":    lambda v: mpmath.exp(v["x"]),
        "ln":     lambda v: mpmath.log(v["x"]),
        "id":     lambda v: v["x"],
        "neg":    lambda v: -v["x"],
        "inv":    lambda v: mpmath.mpc(1) / v["x"],
        # Derived constants / compositions
        "ee":     lambda v: mpmath.power(mpmath.e, mpmath.e),
        "eee":    lambda v: mpmath.power(mpmath.e, mpmath.power(mpmath.e, mpmath.e)),
        "expexp": lambda v: mpmath.exp(mpmath.exp(v["x"])),
        "lnln":   lambda v: mpmath.log(mpmath.log(v["x"])),
    }

    # Default test points (algebraically independent transcendentals)
    TEST_PTS = [
        {"x": mpmath.euler,
         "y": mpmath.mpf("1.28242712910062263687534256887")},
        {"x": mpmath.mpf("1.28242712910062263687534256887"),
         "y": mpmath.euler},
    ]
    # lnln requires x > 1 (and then ln(x) > 0 for the second log)
    TEST_PTS_LNLN = [
        {"x": mpmath.e,    "y": mpmath.mpf("1.28242712910062263687534256887")},
        {"x": mpmath.e**2, "y": mpmath.euler},
    ]
    FORMULA_TEST_PTS: dict[str, list] = {
        "lnln": TEST_PTS_LNLN,
    }

    tbl = Table(
        box=box.ROUNDED,
        border_style="dim magenta",
        header_style="bold white on #1a1a2e",
        show_lines=True,
        title="[bold magenta]EML Library Verification[/]",
    )
    tbl.add_column("Name",    style="bold cyan",   width=8)
    tbl.add_column("Program", style="bold yellow",  width=20)
    tbl.add_column("K",       style=C_DIM,         width=5,  justify="right")
    tbl.add_column("@γ",                            width=18, justify="right")
    tbl.add_column("@A",                            width=18, justify="right")
    tbl.add_column("Status",                        width=10)

    all_pass = True

    for f in lib.all_formulas():
        if f.program is None:
            tbl.add_row(f.name, "[dim]TBD[/]", str(f.k or "?"), "—", "—", "[dim]tbd[/]")
            continue

        oracle = ORACLES.get(f.name)
        if oracle is None:
            tbl.add_row(f.name, f.program, str(f.k or "?"), "—", "—", "[dim]no oracle[/]")
            continue

        row_vals, ok = [], True
        pts = FORMULA_TEST_PTS.get(f.name, TEST_PTS)
        for pt in pts:
            pvars = {k: pt[k] for k in f.variables} if f.variables else {}
            expected = oracle(pt)
            try:
                m = EMLMachine(tokenize(f.program), pvars, prec=prec)
                got = m.run()
                diff = float(abs(got - expected))
                row_vals.append(f"{float(mpmath.re(got)):.10g}")
                if diff > tol:
                    ok = False; all_pass = False
            except Exception as ex:
                row_vals.append(f"[red]ERR[/]"); ok = False; all_pass = False

        status = "[bold green][ok] PASS[/]" if ok else "[bold red][fail] FAIL[/]"
        tbl.add_row(
            f.name, f.program, str(f.k or "?"),
            row_vals[0] if row_vals else "—",
            row_vals[1] if len(row_vals) > 1 else "—",
            status,
        )

    console.print(tbl)
    if all_pass:
        console.print(Panel("[bold green]All known programs verified [ok][/]", border_style="green"))
    else:
        console.print(Panel("[bold red]Some programs failed verification![/]", border_style="red"))
        raise typer.Exit(1)




@app.command()
def wezterm(
    program: Annotated[str, typer.Argument(help="RPN program")],
    var: VarOpt = [],
) -> None:
    """ Launch a 3-pane WezTerm session: disasm | trace | tree."""
    from . import wezterm_support
    wezterm_support.launch_session(program, var)




@app.command()
def sym(
    program: Annotated[str,  typer.Argument(help="EML RPN program")],
    latex:   Annotated[bool, typer.Option("--latex", help="Print LaTeX form")] = False,
) -> None:
    """
     Symbolically evaluate an EML program via SymPy.

    Proves algebraically what function a program computes, e.g.:

      11xE1EE   →  log(x)
      11x1EE1EE →  x          (identity!)
      x1E1E     →  exp(exp(x))

    Uses SymPy's simplify/powsimp/expand_log pipeline.
    """
    from .sym_eval import sym_trace, pretty_result, latex_result

    tokens = tokenize(program)
    v = validate(tokens)
    if not v.ok:
        console.print(f"[red]Invalid program:[/] {v.message}")
        raise typer.Exit(1)

    render_header(console, program, {}, subtitle="mode: sym  (SymPy proof)")

    with console.status("[cyan]Running SymPy simplification…[/]"):
        trace = sym_trace(tokens, simp_intermediates=True)

    if not trace.ok:
        console.print("[red]Symbolic evaluation failed.[/]")
        raise typer.Exit(1)

    # Pretty output
    sym_str = pretty_result(trace)
    raw_str = str(trace.raw)
    simplified_str = str(trace.simplified)

    console.print(f"\n  Program     : [bold yellow]{program}[/]  (K={len(tokens)})")
    console.print(f"  Variables   : [cyan]{', '.join(trace.variables) or '(none)'}[/]")
    console.print(f"\n  Raw result  : [dim]{raw_str[:80]}{'…' if len(raw_str) > 80 else ''}[/]")
    console.print(
        Panel(
            f"[bold green]{sym_str}[/]",
            title="[bold magenta]Symbolic Result[/]",
            border_style="magenta",
            padding=(0, 2),
        )
    )

    if latex:
        console.print(f"\n  LaTeX: [dim]{latex_result(trace)}[/]")

    # Suggest identify if non-trivial
    console.print(f"\n  [dim]Cross-check:[/] [cyan]emlvm identify '{program}'[/]")




@app.command()
def algebra(
    program: Annotated[str, typer.Argument(help="EML RPN program")],
) -> None:
    """
     Step-by-step symbolic execution trace via SymPy.

    Like `emlvm trace` but shows symbolic algebra instead of numbers,
    revealing the mathematical reasoning inside each step.

    Example:  emlvm algebra '11xE1EE'
      shows how the stack evolves from 1, 1, x through to log(x).
    """
    from .sym_eval import sym_trace, _simplify
    import sympy as sp

    tokens = tokenize(program)
    v = validate(tokens)
    if not v.ok:
        console.print(f"[red]Invalid program:[/] {v.message}")
        raise typer.Exit(1)

    render_header(console, program, {}, subtitle="mode: algebra  (symbolic trace)")

    with console.status("[cyan]Building symbolic trace…[/]"):
        trace = sym_trace(tokens, simp_intermediates=True)

    # Build the table
    tbl = Table(
        box=box.SIMPLE_HEAD,
        border_style="dim",
        header_style="bold white on #1a1a2e",
        show_lines=False,
        pad_edge=False,
    )
    tbl.add_column("Step", style=C_DIM,                 width=5,  justify="right")
    tbl.add_column("Tok",  style="bold magenta",         width=5,  justify="center")
    tbl.add_column("Action",                             width=28)
    tbl.add_column("Stack top (simplified)",             min_width=30)

    for step in trace.steps:
        top = step.top
        if top is None:
            top_str = "—"
        else:
            # Use pretty sympy string, keep compact
            top_str = str(sp.simplify(top))
            if len(top_str) > 50:
                top_str = top_str[:49] + "…"
        tbl.add_row(
            str(step.step),
            step.token,
            f"[dim]{step.action}[/]",
            f"[{C_RES}]{top_str}[/]",
        )

    console.print(tbl)

    if trace.simplified is not None:
        console.print(
            Panel(
                f"[bold green]{trace.simplified}[/]",
                title="[bold magenta]Final Simplified Result[/]",
                border_style="magenta",
                padding=(0, 2),
            )
        )
    console.print(
        f"\n  [dim]Numeric check:[/] [cyan]emlvm trace '{program}' --var x=2[/]"
    )




@app.command()
def equiv(
    program_a: Annotated[str, typer.Argument(help="First EML program")],
    program_b: Annotated[str, typer.Argument(help="Second EML program")],
    numeric:   Annotated[bool, typer.Option("--numeric", help="Force numeric-only check")] = False,
    prec:      PrecOpt = 50,
) -> None:
    """
      Check whether two EML programs compute the same function.

    First tries SymPy symbolic equality (a formal proof when it works),
    then confirms numerically at three independent test points.

    Examples:
      emlvm equiv '11x1EE1EE' 'x'          # ln(exp(x)) = identity?
      emlvm equiv 'x1E1E' '11xE1EE'        # exp² vs ln?
      emlvm equiv '11xE1EE1E' '11x1EE1EE'  # both identity?
    """
    from .sym_eval import sym_equiv

    toks_a = tokenize(program_a)
    toks_b = tokenize(program_b)

    for prog, toks in [(program_a, toks_a), (program_b, toks_b)]:
        v = validate(toks)
        if not v.ok:
            console.print(f"[red]Invalid program '{prog}':[/] {v.message}")
            raise typer.Exit(1)

    console.print(
        Panel(
            f"A : [bold yellow]{program_a}[/]  (K={len(toks_a)})\n"
            f"B : [bold yellow]{program_b}[/]  (K={len(toks_b)})",
            title="[bold magenta]EMLVM Equivalence Check[/]",
            border_style="magenta",
        )
    )

    # 1. Symbolic check
    sym_ok = None
    sym_a = sym_b = None
    if not numeric:
        with console.status("[cyan]SymPy symbolic check…[/]"):
            try:
                sym_ok, sym_a, sym_b = sym_equiv(toks_a, toks_b)
                console.print(f"  Symbolic A → [cyan]{sym_a}[/]")
                console.print(f"  Symbolic B → [cyan]{sym_b}[/]")
                if sym_ok:
                    console.print("  [bold green][ok] Symbolically equal (algebraic proof)[/]")
                else:
                    console.print("  [dim]Symbolic difference detected — also checking numerically[/]")
            except Exception as e:
                console.print(f"  [dim yellow]Symbolic check skipped ({e})[/]")

    # 2. Numeric check at three independent transcendental test points
    TEST_PTS_ALL = [
        {"x": mpmath.euler,
         "y": mpmath.mpf("1.28242712910062263687534256887")},
        {"x": mpmath.mpf("1.28242712910062263687534256887"),
         "y": mpmath.euler},
        {"x": mpmath.pi / 4,
         "y": mpmath.sqrt(mpmath.mpf(2))},
    ]

    all_vars = sorted(
        {t for t in toks_a + toks_b if t not in ("1", "E")}
    )
    test_pts = [{k: v for k, v in pt.items() if k in all_vars}
                for pt in TEST_PTS_ALL]

    import numpy as np
    tol = mpmath.mpf(10) ** (-prec // 2)
    num_ok = True

    num_tbl = Table(box=box.SIMPLE_HEAD, border_style="dim", show_header=True,
                    header_style="bold white on #1a1a2e")
    num_tbl.add_column("Pt", width=3)
    num_tbl.add_column("vars",     width=22)
    num_tbl.add_column("A",        width=22, justify="right")
    num_tbl.add_column("B",        width=22, justify="right")
    num_tbl.add_column("match",    width=8)

    for i, pt in enumerate(test_pts):
        if not pt and all_vars:
            continue
        try:
            ma = EMLMachine(toks_a, pt, prec=prec); ra = ma.run()
            mb = EMLMachine(toks_b, pt, prec=prec); rb = mb.run()
            diff = abs(ra - rb)
            match = diff < tol
            if not match:
                num_ok = False
            var_str = "  ".join(f"{k}={float(mpmath.re(v)):.6g}" for k, v in pt.items()) or "(const)"
            num_tbl.add_row(
                str(i + 1),
                var_str,
                f"{float(mpmath.re(ra)):.14g}",
                f"{float(mpmath.re(rb)):.14g}",
                "[bold green][ok][/]" if match else "[bold red][fail][/]",
            )
        except Exception:
            num_tbl.add_row(str(i + 1), "—", "ERR", "ERR", "[dim]?[/]")

    console.print(num_tbl)

    equivalent = (sym_ok is True) or (sym_ok is None and num_ok) or num_ok
    if sym_ok is True:
        verdict = "[bold green]EQUIVALENT[/]  (proved symbolically + confirmed numerically)"
    elif num_ok and sym_ok is None:
        verdict = "[bold green]EQUIVALENT[/]  (confirmed numerically at 3 test points)"
    elif num_ok:
        verdict = "[yellow]NUMERICALLY EQUAL[/]  (symbolic check detected difference — check branch cuts)"
    else:
        verdict = "[bold red]NOT EQUIVALENT[/]"

    console.print(Panel(verdict, border_style="green" if num_ok else "red"))

    if not num_ok:
        raise typer.Exit(1)




@app.command()
def identify(
    program: Annotated[str,  typer.Argument(help="EML RPN program")],
    numeric: Annotated[bool, typer.Option("--numeric", help="Skip SymPy, use numeric only")] = False,
    prec:    PrecOpt = 50,
) -> None:
    """
     Identify what mathematical function an EML program computes.

    Uses SymPy to match against a catalog of known expressions, then
    confirms numerically. Great for understanding discovered golf results.

    Examples:
      emlvm identify 'x1E1E'          # → exp(exp(x))
      emlvm identify '11E1E'           # → e^e  (constant)
      emlvm identify '1111xE1EEE1EE'  # → ln(ln(x))
    """
    from .sym_eval import sym_trace, sym_identify

    tokens = tokenize(program)
    v = validate(tokens)
    if not v.ok:
        console.print(f"[red]Invalid program:[/] {v.message}")
        raise typer.Exit(1)

    render_header(console, program, {}, subtitle="mode: identify")

    # 1. Check library directly  ─────────────────────────────────────────────
    library_match = None
    for f in lib.all_formulas():
        if f.program == program:
            library_match = f
            break

    if library_match:
        console.print(
            Panel(
                f"[bold green][ok] Exact library match:[/]  "
                f"[bold cyan]{library_match.name}[/]  —  {library_match.description}\n"
                f"  Source: {library_match.source}",
                border_style="green",
            )
        )
        return

    # 2. Symbolic catalog scan  ───────────────────────────────────────────────
    sym_matches: list = []
    if not numeric:
        with console.status("[cyan]SymPy catalog scan…[/]"):
            try:
                sym_matches = sym_identify(tokens)
            except Exception as e:
                console.print(f"  [dim yellow]SymPy scan failed: {e}[/]")

    # 3. Numeric scan against extended catalog  ───────────────────────────────
    import mpmath as _mp
    CATALOG_NUM = {
        # constants
        "e":          lambda v: _mp.e,
        "0":          lambda v: _mp.mpc(0),
        "1":          lambda v: _mp.mpc(1),
        "e^e":        lambda v: _mp.power(_mp.e, _mp.e),
        "e^(e^e)":    lambda v: _mp.power(_mp.e, _mp.power(_mp.e, _mp.e)),
        "ln(2)":      lambda v: _mp.log(2),
        "π":          lambda v: _mp.pi,
        # unary
        "exp(x)":     lambda v: _mp.exp(v.get("x", _mp.euler)),
        "ln(x)":      lambda v: _mp.log(v.get("x", _mp.euler)),
        "x":          lambda v: v.get("x", _mp.euler),
        "-x":         lambda v: -v.get("x", _mp.euler),
        "1/x":        lambda v: _mp.mpc(1) / v.get("x", _mp.euler),
        "x²":         lambda v: v.get("x", _mp.euler) ** 2,
        "√x":         lambda v: _mp.sqrt(v.get("x", _mp.euler)),
        "exp(exp(x))": lambda v: _mp.exp(_mp.exp(v.get("x", _mp.euler))),
        "ln(ln(x))":  lambda v: _mp.log(_mp.log(v.get("x", _mp.mpf("1.5")))),
    }

    TEST_PTS_ID = [
        {"x": mpmath.euler,
         "y": mpmath.mpf("1.28242712910062263687534256887")},
        {"x": mpmath.mpf("1.28242712910062263687534256887"),
         "y": mpmath.euler},
        {"x": mpmath.pi / 4,
         "y": mpmath.sqrt(mpmath.mpf(2))},
    ]

    all_vars = sorted({t for t in tokens if t not in ("1", "E")})
    tol = mpmath.mpf(10) ** (-prec // 3)

    num_matches: list[str] = []
    prog_vals = []
    for pt in TEST_PTS_ID:
        pvars = {k: pt[k] for k in all_vars if k in pt}
        try:
            m = EMLMachine(tokens, pvars, prec=prec)
            prog_vals.append(m.run())
        except Exception:
            prog_vals.append(None)

    for fname, oracle in CATALOG_NUM.items():
        matched_all = True
        for pt, pval in zip(TEST_PTS_ID, prog_vals):
            if pval is None:
                matched_all = False
                break
            try:
                ref = oracle(pt)
                if float(abs(pval - ref)) > float(tol):
                    matched_all = False
                    break
            except Exception:
                matched_all = False
                break
        if matched_all:
            num_matches.append(fname)

    # 4. Display results  ─────────────────────────────────────────────────────
    console.print(f"\n  Program: [bold yellow]{program}[/]  K={len(tokens)}")

    if prog_vals and prog_vals[0] is not None:
        console.print(f"  At x=γ:  [{C_RES}]{float(mpmath.re(prog_vals[0])):.12g}[/]")
        if len(prog_vals) > 1 and prog_vals[1] is not None:
            console.print(f"  At x=A:  [{C_RES}]{float(mpmath.re(prog_vals[1])):.12g}[/]")

    if sym_matches:
        console.print(f"\n  [bold green]SymPy matches:[/]")
        for name, expr in sym_matches[:5]:
            console.print(f"    [bold cyan]{name}[/]  →  {expr}")

    if num_matches:
        console.print(f"\n  [bold green]Numeric matches:[/]")
        for name in num_matches:
            console.print(f"    [bold cyan]{name}[/]")

    if not sym_matches and not num_matches:
        console.print(
            "\n  [yellow]No catalog match found.[/]\n"
            "  Try [cyan]emlvm sym[/] for the raw symbolic expression,\n"
            "  or refine by running [cyan]emlvm verify[/] after adding to known.py."
        )
    else:
        console.print(
            f"\n  [dim]Verify:[/]  [cyan]emlvm sym '{program}'[/]"
        )


@app.command()
def puzzle() -> None:
    """Start the interactive mathematical EMLVM campaign."""
    from .puzzle import play_campaign_interactive
    play_campaign_interactive()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
