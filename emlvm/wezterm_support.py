"""WezTerm split-pane session launcher."""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Optional


def is_available() -> bool:
    """Return True if wezterm CLI is on PATH."""
    return shutil.which("wezterm") is not None


def _wez(*args: str) -> Optional[str]:
    """Run `wezterm cli <args>` and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["wezterm", "cli", *args],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _split(direction: str, percent: int, cmd: list[str]) -> Optional[str]:
    """Split a pane and run cmd in it. Returns new pane-id."""
    flag = "--right" if direction == "right" else "--bottom"
    out = _wez("split-pane", flag, f"--percent={percent}", "--", *cmd)
    return out


def launch_session(program: str, var_args: list[str]) -> None:
    """
    Open a 3-pane WezTerm layout:
      Left  (main)  :  emlvm disasm PROG ...
      Right (40%)   :  emlvm trace  PROG ...
      Bottom (30%)  :  emlvm tree   PROG
    """
    if not is_available():
        print("wezterm CLI not found — install WezTerm or add it to PATH.", file=sys.stderr)
        sys.exit(1)

    base_cmd = [sys.executable, "-m", "emlvm"]
    var_flags: list[str] = []
    for v in var_args:
        var_flags += ["--var", v]

    # Right pane: trace
    _split("right", 45, base_cmd + ["trace", program] + var_flags)
    # Bottom pane of the LEFT pane: tree  (we re-use the original pane focus)
    _split("bottom", 30, base_cmd + ["tree", program])

    # Run disasm in the current (left/original) pane
    subprocess.run(base_cmd + ["disasm", program] + var_flags)
