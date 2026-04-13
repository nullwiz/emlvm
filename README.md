# EMLVM — Single-Instruction EML Virtual Machine

```
eml(x, y)  =  exp(x)  −  ln(y)
```

> **One operator for every elementary function.**
>
> Based on the paper *"All Elementary Functions from a Single Operator"*
> (arXiv 2603.21852).  Just like NAND generates all Boolean logic, the EML
> Sheffer operator `eml(x,y) = exp(x) − ln(y)` — combined with the constant
> `1` — generates every elementary mathematical function via composition.

---

## What is this?

EMLVM is a CLI stack machine that executes programs whose only real instruction
is `E` (the EML operator).  Programs are written in RPN (postfix) notation with
three token types:

| Token | Meaning           | Example |
|-------|-------------------|---------|
| `1`   | Push constant 1   | `1` → stack: [1] |
| `x`   | Push variable x   | `x` → stack: [x] |
| `E`   | Pop x, y → push `exp(x) − ln(y)` | `1 1 E` → e |

EMLVM lets you *run*, *trace*, *debug*,
*plot*, and *symbolically prove* these programs in the terminal.

---

## Installation

```bash
git clone https://github.com/nullwiz/emlvm
cd emlvm
pip install -e .
```

**Dependencies:** `typer`, `rich`, `mpmath`, `numpy`, `plotext`, `sympy`

---

## The Bootstrap: how all functions arise from one operator

Starting from nothing but `eml` and `1`:

```
Level 0  (axiom)     eml(x, y) = exp(x) − ln(y)

Level 1  (constant)  e = eml(1, 1) = exp(1) − ln(1) = e − 0
                     RPN: 11E    K=3

Level 2  (compound)  exp(x) = eml(x, 1) = exp(x) − 0
                     RPN: x1E   K=3

                     e^e = eml(e, 1) = exp(e) − 0       [plug 11E into exp]
                     RPN: 11E1E  K=5

                     exp(exp(x)) = eml(eml(x,1), 1)     [compose exp◦exp]
                     RPN: x1E1E  K=5

Level 3  (log)       ln(x) = eml(1, eml(eml(1,x), 1))
                     i.e.  eml(1, e^e/x) = e − ln(e^e/x) = e − (e − ln x) = ln x
                     RPN: 11xE1EE  K=7

Level 4  (identity)  id(x) = exp(ln(x)) = x             [compose exp◦ln]
                     RPN: 11x1EE1EE  K=9

Level 5+             neg(x) = −x                        K=15  [golf search]
                     inv(x) = 1/x                        K=15  [golf search]
                     mul(x,y) = x·y                      K=19  [golf search]
                     add(x,y) = x+y                      K=27  [golf search]
```

`emlvm algebra '11xE1EE'` shows SymPy proving *each algebraic step* live in
your terminal.

---

## Command Reference

### Run & Debug

```bash
# Run a program
emlvm run '11xE1EE' --var x=2

# Numeric step-by-step execution trace
emlvm trace '11xE1EE' --var x=2

# Interactive single-stepper (press Enter to advance)
emlvm step '11xE1EE' --var x=2

# Annotated disassembly
emlvm disasm '11xE1EE'

# Expression tree
emlvm tree '11xE1EE'
```

**Sample trace output:**
```
 Step   Tok    Action              Stack
    0    1     push 1              [1]
    1    1     push 1              [1, 1]
    2    x     push x=2.0          [1, 1, 2]
    3    E     eml(1, 2) = e−ln2   [1, 0.3069…]
    4    1     push 1              [1, 0.3069…, 1]
    5    E     eml(0.306…, 1)      [1, 1.3591…]
    6    E     eml(1, 1.3591…)     [0.6931…]

 Result: 0.693147…  ≡ ln(2) ✓
```

---

### Library

```bash
# Show all known programs
emlvm known

# Verify every known program against Python's math library
emlvm verify
```

**Current library:**

| Name    | Program         | K  | Computes         |
|---------|-----------------|----|------------------|
| `e`     | `11E`           | 3  | Euler's number   |
| `exp`   | `x1E`           | 3  | exp(x)           |
| `ee`    | `11E1E`         | 5  | e^e ≈ 15.154     |
| `expexp`| `x1E1E`         | 5  | exp(exp(x))      |
| `zero`  | `111E1EE`       | 7  | 0                |
| `eee`   | `11E1E1E`       | 7  | e^(e^e) ≈ 3.8M   |
| `ln`    | `11xE1EE`       | 7  | ln(x)            |
| `id`    | `11x1EE1EE`     | 9  | x (identity)     |
| `lnln`  | `1111xE1EEE1EE` | 13 | ln(ln(x)), x > 1 |
| `neg`   | TBD             | 15 | −x               |
| `inv`   | TBD             | 15 | 1/x              |
| `mul`   | TBD             | 19 | x·y              |
| `add`   | TBD             | 27 | x+y              |

---

### Symbolic Algebra (SymPy) ✨

SymPy **proves** algebraically what a program computes.

```bash
# Prove a program symbolically
emlvm sym '11xE1EE'
#  → log(x)

emlvm sym '11x1EE1EE'
#  → x   (the identity — proved purely from exp/log algebra!)

# Step-by-step algebraic trace
emlvm algebra '11xE1EE'
```

**Sample algebra trace:**
```
 Step  Tok   Action              Stack top
    0   1    push  1             1
    1   1    push  1             1
    2   x    push  x             x
    3   E    eml(1, x)           E - log(x)       ← e − ln(x)
    4   1    push  1             1
    5   E    eml(E−log(x), 1)   exp(E)/x          ← e^e / x
    6   E    eml(1, exp(E)/x)   log(x)            ← e − (e − ln x) = ln(x)  ✓

 Final: log(x)
```

```bash
# LaTeX output (for papers / notebooks)
emlvm sym '11xE1EE' --latex
#  → \log{\left(x \right)}
```

---

### Equivalence & Identification

```bash
# Are two programs equivalent? (SymPy proof + numeric confirmation)
emlvm equiv '11xE1EE1E' 'x'
#  ✓ EQUIVALENT  (ln(exp(x)) = identity, proved symbolically)

emlvm equiv 'x1E' '11xE1EE'
#  ✗ NOT EQUIVALENT  (exp vs ln)

# What function does a program compute?
emlvm identify 'x1E1E'
#  → exp(exp(x))

emlvm identify '11E1E'
#  → e^e  (exact library match)
```

---

### Compiler

Converts standard mathematical notation to EML RPN via compositional substitution.

```bash
emlvm compile 'exp(x)'
#  EML RPN: x1E    K=3

emlvm compile 'ln(exp(x))'
#  EML RPN: 11x1EE1EE    K=9   → identity!

emlvm compile 'exp(ln(exp(x)))'
#  EML RPN: 11x1EE1EE1E   K=11  → exp(x) again

emlvm compile 'exp(x)' --tree   # show EML expression tree
```

The composition rule: if `P_f` is the program for `f` and `P_g` for `g`, then
`f(g(x))` is found by substituting every `x` token in `P_f` with all tokens of `P_g`.

---

### Golf Search

Find the shortest EML program for any target function.

```bash
# Find exp(x) automatically
emlvm golf exp --max-k 9

# Search for negation (K=15, uses extended reals ±∞)
emlvm golf neg --max-k 17

# Find constants
emlvm golf e --max-k 5
```

The search uses a Schanuel-heuristic dual-point evaluation with numpy for
IEEE754 ±∞ handling (needed for programs that pass through infinity as intermediates).

---

### Plot

Terminal function graphs via `plotext`:

```bash
emlvm plot '11xE1EE' --range 0.1:5
emlvm plot 'x1E1E' --range 0:3 --steps 100
emlvm plot '11xE1EE' --range 0.1:5 --log-x   # log scale
emlvm plot '11xE1EE' --compare ln             # overlay known ln
```

---

### Check

Verify a program matches a known function:

```bash
emlvm check '11xE1EE' --expect ln --var x=2
emlvm check '11E' --expect e
```

---

### WezTerm Layout

```bash
emlvm wezterm '11xE1EE' --var x=2
```

Opens three panes simultaneously:
```
┌──────────────────┬──────────────────┐
│   DISASSEMBLY    │   STEP TRACE     │
│   11xE1EE        │   stack states   │
├──────────────────┴──────────────────┤
│         EXPRESSION TREE             │
└─────────────────────────────────────┘
```

---

## Workflow: Discovering New Programs

```bash
# 1. Golf for a new function  (this runs for a few minutes)
emlvm golf inv --max-k 17

# 2. Trace the discovered program to understand it
emlvm trace 'DISCOVERED_PROGRAM' --var x=3

# 3. Symbolically prove what it computes
emlvm sym 'DISCOVERED_PROGRAM'

# 4. Cross-check against catalog
emlvm identify 'DISCOVERED_PROGRAM'

# 5. Plot it
emlvm plot 'DISCOVERED_PROGRAM' --range 0.1:5
```

---

## Mathematical Background

The EML operator satisfies the **Sheffer property**: a single binary operator
that, together with a constant, generates a *functionally complete* system over
$\mathbb{C}$.

Key algebraic identities:

```
eml(x, 1)           = exp(x)          [ln(1) = 0]
eml(1, x)           = e − ln(x)       [exp(1) = e]
eml(1, eml(e−ln x, 1)) = e − ln(e^e/x) = e − e + ln(x) = ln(x)
eml(a, exp(a))       = exp(a) − a     [interesting fixed-point relation]
```

The composition rule makes every elementary function reachable:
1. Start with `eml` and `1`
2. `e`, `0`, `exp`, `ln` are K≤7
3. All arithmetic (neg, inv, mul, add) follows via K≤27
4. All trig functions follow from arithmetic + exp/ln (Euler's formula)

---

## Contributing

To add a newly discovered formula:

1. Run `emlvm golf <name> --max-k <k>`
2. Verify: `emlvm check 'PROG' --expect <ref> --var x=2`
3. Prove: `emlvm sym 'PROG'` and `emlvm identify 'PROG'`
4. Add to `emlvm/known.py` in the `LIBRARY` dict
5. It will automatically appear in `emlvm known` and `emlvm verify`

---

## Citation

```bibtex
@misc{eml2025,
  title   = {All Elementary Functions from a Single Operator},
  author  = {[Author]},
  year    = {2025},
  url     = {https://arxiv.org/abs/2603.21852}
}
```

---

*Built for exploration at the intersection of computation theory and classical analysis.*
*Run `emlvm --help` for full command reference.*
