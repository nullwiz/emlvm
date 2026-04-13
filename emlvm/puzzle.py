from __future__ import annotations

import sympy as sp
from dataclasses import dataclass
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from .rpn import tokenize, validate
from .sym_eval import sym_trace, pretty_result
from .tracer import C_RES, C_DIM, C_WARN

console = Console()

x, y = sp.symbols("x y", positive=True)

@dataclass
class Puzzle:
    level: int
    name: str
    target: sp.Expr
    description: str
    allowed_vars: list[str]

PUZZLES = [
    Puzzle(1, "exp", sp.exp(x), "Implement exp(x) = e^x", ["x"]),
    Puzzle(2, "ln", sp.log(x), "Implement ln(x)", ["x"]),
    Puzzle(3, "e", sp.exp(1), "Find the constant e", []),
    Puzzle(4, "sub", x - y, "Implement subtraction: x - y\nHint: eml(ln(x), exp(y))", ["x", "y"]),
    Puzzle(5, "minus_1", sp.Integer(-1), "Find the constant -1", []),
    Puzzle(6, "two", sp.Integer(2), "Find the constant 2", []),
    Puzzle(7, "neg", -x, "Implement unary minus: -x", ["x"]),
    Puzzle(8, "add", x + y, "Implement addition: x + y", ["x", "y"]),
    Puzzle(9, "inv", sp.Integer(1) / x, "Implement multiplicative inverse: 1 / x", ["x"]),
    Puzzle(10, "mul", x * y, "Implement multiplication: x * y", ["x", "y"]),
]

def check_puzzle(puzzle: Puzzle, rpn_string: str) -> tuple[bool, str, Optional[sp.Expr]]:
    """Validates the input string against the Puzzle target exactly."""
    tokens = tokenize(rpn_string)
    
    v = validate(tokens, bound_vars=set(puzzle.allowed_vars))
    if not v.ok:
        return False, f"[red]Invalid program:[/] {v.message}", None
    
    try:
        trace = sym_trace(tokens, simp_intermediates=False)
        if trace.simplified is None:
            return False, "[red]Failed to compute symbolic trace.[/]", None
            
        diff = sp.simplify(trace.simplified - puzzle.target)
        if diff == sp.Integer(0):
            return True, "", trace.simplified
        
        return False, f"Expected {str(puzzle.target)}, got {str(trace.simplified)}", trace.simplified
    except Exception as e:
        return False, f"[red]Execution error:[/] {e}", None

def play_campaign_interactive():
    try:
        import readline
    except ImportError:
        pass
    
    console.clear()
    console.print(Panel(
        "[bold magenta]Welcome to EMLVM Puzzle Campaign[/]\n\n"
        "Your goal is to build up a variety of functions using [bold cyan]ONLY[/] the operator [bold magenta]E[/]\n"
        "and the constant [bold cyan]1[/]. You must write raw Reverse Polish Notation (RPN) strings.\n\n"
        "The stack processes from left to right. E pops y, then x, and evaluates exp(x) - ln(y).",
        border_style="magenta"
    ))
    
    for puz in PUZZLES:
        valid_leaves = ["1", "E"] + puz.allowed_vars
        
        while True:
            console.print("\n" + "="*50)
            console.print(f"[bold cyan]Level {puz.level}:[/] {puz.description}")
            console.print(f"[dim]Available tokens:[/] [yellow]{', '.join(valid_leaves)}[/]")
            
            try:
                ans = Prompt.ask("\n[bold magenta]>[/] Enter RPN string (or 'q' to quit)")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Quitting...[/]")
                return
            
            ans = ans.strip()
            if ans.lower() == 'q':
                return
            if not ans:
                continue
                
            success, msg, _ = check_puzzle(puz, ans)
            if success:
                console.print(Panel("[bold green]CORRECT![/]", expand=False, border_style="green"))
                break
            else:
                console.print(Panel(f"[bold red]Incorrect![/]\n{msg}", expand=False, border_style="red"))
                
    console.print(Panel(
        "[bold green]Campaign Complete![/]\n\n"
        "You've mastered the EML mathematical topological spaces.",
        border_style="green"
    ))
