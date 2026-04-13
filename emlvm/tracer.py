from __future__ import annotations

from typing import Optional

import mpmath
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from .vm import StepRecord, fmt_num


# Colour palette
C_OP    = "bold magenta"
C_ONE   = "bold cyan"
C_VAR   = "bold yellow"
C_RES   = "bold green"
C_WARN  = "bold red"
C_DIM   = "dim white"
C_HEAD  = "bold white"
C_STACK = "blue"


# Header banner

LOGO = """\
[bold magenta] ███████╗███╗   ███╗██╗      ██╗   ██╗███╗   ███╗[/]
[bold magenta] ██╔════╝████╗ ████║██║      ██║   ██║████╗ ████║[/]
[bold magenta] █████╗  ██╔████╔██║██║      ██║   ██║██╔████╔██║[/]
[bold magenta] ██╔══╝  ██║╚██╔╝██║██║      ╚██╗ ██╔╝██║╚██╔╝██║[/]
[bold magenta] ███████╗██║ ╚═╝ ██║███████╗  ╚████╔╝ ██║ ╚═╝ ██║[/]
[bold magenta] ╚══════╝╚═╝     ╚═╝╚══════╝   ╚═══╝  ╚═╝     ╚═╝[/]"""


def render_header(
    console: Console,
    program: str,
    variables: dict,
    subtitle: str = "",
) -> None:
    var_str = "  ".join(
        f"[{C_VAR}]{k}[/] = [{C_RES}]{fmt_num(v)}[/]"
        for k, v in variables.items()
    )
    body = (
        f"[{C_DIM}]eml(x,y) = exp(x) − ln(y)[/]\n\n"
        f"Program  [{C_ONE}]{program}[/]\n"
        + (f"Vars     {var_str}\n" if var_str else "")
        + (f"[{C_DIM}]{subtitle}[/]" if subtitle else "")
    )
    console.print(
        Panel(body, title="[bold magenta]EMLVM[/]", border_style="magenta", padding=(0, 2))
    )


# Format stack

def fmt_stack(stack: list) -> str:
    if not stack:
        return "[dim]∅[/]"
    parts = []
    for i, v in enumerate(stack):
        color = C_RES if i == len(stack) - 1 else C_STACK
        parts.append(f"[{color}]{fmt_num(v)}[/]")
    return " │ ".join(parts) + "  [dim]← top[/]"


# Trace table

def render_trace_table(history: list[StepRecord], console: Console) -> None:
    tbl = Table(
        box=box.ROUNDED,
        border_style="dim magenta",
        header_style="bold white on #1a1a2e",
        show_lines=True,
    )
    tbl.add_column("#",      style=C_DIM,  width=3,  justify="right")
    tbl.add_column("Token",  style=C_HEAD, width=6,  justify="center")
    tbl.add_column("Action",               width=48)
    tbl.add_column("Stack (bottom → top)", min_width=28)

    for r in history:
        # Token colour
        if r.token == "E":
            tok_text = Text("E", style=C_OP)
        elif r.token == "1":
            tok_text = Text("1", style=C_ONE)
        else:
            tok_text = Text(r.token, style=C_VAR)

        # Warning marker
        note = f"  [red][warn] {r.warning}[/]" if r.warning else ""
        action_text = Text.from_markup(r.action + note)

        tbl.add_row(
            str(r.step),
            tok_text,
            action_text,
            Text.from_markup(fmt_stack(r.stack_after)),
        )

    console.print(tbl)


# Disassembly listing

def render_disasm(
    tokens: list[str],
    history: list[StepRecord],
    console: Console,
) -> None:
    tbl = Table(
        box=box.SIMPLE_HEAD,
        border_style="dim",
        header_style="bold white",
        show_lines=False,
        padding=(0, 1),
    )
    tbl.add_column("Addr",  style=C_DIM,  width=5, justify="right")
    tbl.add_column("Tok",   width=5,  justify="center")
    tbl.add_column("Instruction")
    tbl.add_column("Stack depth", justify="right", width=12)

    for i, tok in enumerate(tokens):
        if i < len(history):
            r = history[i]
            depth = str(len(r.stack_after))
            action = r.action
            warn = f"  [warn] {r.warning}" if r.warning else ""
        else:
            depth = "?"
            action = "—"
            warn = ""

        if tok == "E":
            tok_t = Text("E", style=C_OP)
        elif tok == "1":
            tok_t = Text("1", style=C_ONE)
        else:
            tok_t = Text(tok, style=C_VAR)

        tbl.add_row(str(i), tok_t, action + warn, depth)

    console.print(tbl)


# Final result

def render_result(value: mpmath.mpc, mode: str, console: Console) -> None:
    re = float(mpmath.re(value))
    im = float(mpmath.im(value))

    if mode == "real" or (mode == "auto" and abs(im) < 1e-8 * max(1, abs(re))):
        display = f"[{C_RES}]{re:.15g}[/]"
    else:
        display = f"[{C_RES}]{fmt_num(value, digits=15)}[/]"

    console.print(
        Panel(
            f"  {display}",
            title="[bold green]Result[/]",
            border_style="green",
            padding=(0, 2),
        )
    )
