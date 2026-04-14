"""Tests for the RPN tokenizer, validator, and generator."""
from __future__ import annotations

import pytest

from emlvm.rpn import tokenize, validate, program_stats, gen_valid_rpn


class TestTokenize:
    def test_compact(self):
        assert tokenize("11E") == ["1", "1", "E"]

    def test_compact_with_var(self):
        assert tokenize("x1E") == ["x", "1", "E"]

    def test_spaced(self):
        assert tokenize("1 1 E") == ["1", "1", "E"]

    def test_complex_program(self):
        assert tokenize("11xE1EE") == ["1", "1", "x", "E", "1", "E", "E"]

    def test_multi_var(self):
        assert tokenize("xy1EE") == ["x", "y", "1", "E", "E"]

    def test_empty(self):
        assert tokenize("") == []

    def test_braces(self):
        assert tokenize("{theta} 1 E") == ["theta", "1", "E"]


class TestValidate:
    def test_valid_simple(self):
        vr = validate(["1", "1", "E"])
        assert vr.ok

    def test_valid_single_leaf(self):
        vr = validate(["1"])
        assert vr.ok
        assert vr.final_depth == 1

    def test_underflow(self):
        vr = validate(["E"])
        assert not vr.ok
        assert "underflow" in vr.message.lower()

    def test_too_many_items(self):
        vr = validate(["1", "1"])
        assert not vr.ok
        assert "2" in vr.message

    def test_unbound_variable(self):
        vr = validate(["x", "1", "E"], bound_vars={"y"})
        assert not vr.ok
        assert "x" in vr.message

    def test_bound_variable(self):
        vr = validate(["x", "1", "E"], bound_vars={"x"})
        assert vr.ok

    def test_variables_detected(self):
        vr = validate(["x", "y", "E"])
        assert vr.ok
        assert vr.variables == {"x", "y"}

    def test_max_depth(self):
        # 1 1 1 E E: max depth is 3
        vr = validate(["1", "1", "1", "E", "E"])
        assert vr.ok
        assert vr.max_depth == 3

    @pytest.mark.parametrize("program", [
        "11E", "x1E", "11xE1EE", "111E1EE",
        "11111E1EEEEx1EE", "11xE1EEy1EE",
    ])
    def test_known_programs_valid(self, program):
        toks = tokenize(program)
        vr = validate(toks)
        assert vr.ok, f"{program}: {vr.message}"


class TestProgramStats:
    def test_e_program(self):
        s = program_stats(["1", "1", "E"])
        assert s["K"] == 3
        assert s["operators"] == 1
        assert s["ones"] == 2
        assert s["var_tokens"] == 0

    def test_exp_program(self):
        s = program_stats(["x", "1", "E"])
        assert s["K"] == 3
        assert s["variables"] == ["x"]

    def test_two_var(self):
        s = program_stats(tokenize("11xE1EEy1EE"))
        assert s["variables"] == ["x", "y"]


class TestGenValidRPN:
    def test_one_op(self):
        """K=3: C(1) * 2^2 = 1 * 4 = 4 programs with leaves [1, x]."""
        progs = list(gen_valid_rpn(1, ["1", "x"]))
        assert len(progs) == 4
        # All should be 3 tokens
        assert all(len(p) == 3 for p in progs)

    def test_two_ops(self):
        """K=5: C(2) * 2^3 = 2 * 8 = 16 programs with leaves [1, x]."""
        progs = list(gen_valid_rpn(2, ["1", "x"]))
        assert len(progs) == 16

    def test_all_valid(self):
        """Every generated program should pass validation."""
        for num_ops in range(1, 5):
            for prog in gen_valid_rpn(num_ops, ["1", "x"]):
                vr = validate(list(prog))
                assert vr.ok, f"Invalid: {''.join(prog)}: {vr.message}"
