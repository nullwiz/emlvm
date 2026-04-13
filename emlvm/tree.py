from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from rich.tree import Tree as RichTree


# Node types

@dataclass
class LeafNode:
    value: str   # '1' or a variable name

    def __repr__(self) -> str:
        return self.value


@dataclass
class EMLNode:
    left: "AnyNode"   # x  argument → goes to exp(x)
    right: "AnyNode"  # y  argument → goes to ln(y)

    def __repr__(self) -> str:
        return f"eml({self.left!r}, {self.right!r})"


AnyNode = Union[EMLNode, LeafNode]


# Build from RPN

def build_tree(tokens: list[str]) -> AnyNode:
    """
    Convert a validated RPN token list into a binary expression tree.

    Stack convention: E pops y (top) then x (second), builds EMLNode(x, y).
    """
    stack: list[AnyNode] = []
    for tok in tokens:
        if tok == "E":
            right = stack.pop()   # y
            left = stack.pop()    # x
            stack.append(EMLNode(left=left, right=right))
        else:
            stack.append(LeafNode(value=tok))
    return stack[-1]


# Rich rendering

def _add_node(rich_parent: RichTree, node: AnyNode, label: str = "") -> None:
    prefix = f"[dim]{label}[/]  " if label else ""
    if isinstance(node, LeafNode):
        v = node.value
        if v == "1":
            rich_parent.add(f"{prefix}[cyan bold]1[/]")
        else:
            rich_parent.add(f"{prefix}[yellow bold]{v}[/]")
    else:
        branch = rich_parent.add(f"{prefix}[magenta bold]eml[/]")
        _add_node(branch, node.left,  label="x →")
        _add_node(branch, node.right, label="y →")


def build_rich_tree(root: AnyNode, title: str = "EML Expression Tree") -> RichTree:
    """Return a rich Tree object ready to print."""
    tree = RichTree(
        f"[bold white]{title}[/]",
        guide_style="dim white",
    )
    _add_node(tree, root)
    return tree


# ASCII subtree for compact display (e.g. inside a panel)

def tree_to_str(node: AnyNode, prefix: str = "", is_last: bool = True) -> str:
    connector = "└── " if is_last else "├── "
    ext = "    " if is_last else "│   "

    if isinstance(node, LeafNode):
        return prefix + connector + node.value + "\n"

    lines = prefix + connector + "eml\n"
    lines += tree_to_str(node.left,  prefix + ext, is_last=False)
    lines += tree_to_str(node.right, prefix + ext, is_last=True)
    return lines


# DAG Compilation

def compute_dag(root: AnyNode) -> list[str]:
    """
    Computes a DAG representation of the tree using Common Subexpression Elimination.
    Returns a list of string assignments like 'v0 = 1', 'v1 = eml(x, v0)'.
    """
    instructions = []
    sig_to_reg: dict[str, str] = {}
    reg_counter = 0

    def visit(node: AnyNode) -> str:
        nonlocal reg_counter
        
        if isinstance(node, LeafNode):
            sig = f"L:{node.value}"
            if sig not in sig_to_reg:
                reg = f"v{reg_counter}"
                reg_counter += 1
                sig_to_reg[sig] = reg
                instructions.append(f"{reg} = {node.value}")
            return sig_to_reg[sig]
        
        # EMLNode
        l_reg = visit(node.left)
        r_reg = visit(node.right)
        sig = f"E:{l_reg}:{r_reg}"
        
        if sig not in sig_to_reg:
            reg = f"v{reg_counter}"
            reg_counter += 1
            sig_to_reg[sig] = reg
            instructions.append(f"{reg} = eml({l_reg}, {r_reg})")
        return sig_to_reg[sig]

    visit(root)
    return instructions
