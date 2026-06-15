"""Test suite for calculator.py — designed to expose intentional bugs.

These tests WILL FAIL on the current buggy version of calculator.py.
That's the point. Anvil should detect these failures, diagnose the
root causes, and fix the code so that all tests pass.
"""

import pytest
from calculator import add, subtract, multiply, divide, power, negate, absolute


class TestAdd:
    def test_positive_numbers(self):
        assert add(2, 3) == 5

    def test_negative_numbers(self):
        assert add(-1, -2) == -3

    def test_mixed_signs(self):
        assert add(5, -3) == 2

    def test_zero(self):
        assert add(0, 0) == 0


class TestSubtract:
    def test_positive_numbers(self):
        assert subtract(10, 3) == 7

    def test_negative_result(self):
        assert subtract(3, 10) == -7


class TestMultiply:
    def test_positive_numbers(self):
        assert multiply(3, 4) == 12

    def test_by_zero(self):
        assert multiply(5, 0) == 0

    def test_negative(self):
        assert multiply(-2, 3) == -6


class TestDivide:
    def test_exact_division(self):
        assert divide(10, 2) == 5.0

    def test_fractional(self):
        assert divide(7, 2) == 3.5

    def test_division_by_zero(self):
        """Should raise ZeroDivisionError, not crash the agent."""
        with pytest.raises(ZeroDivisionError):
            divide(10, 0)


class TestPower:
    def test_positive_exponent(self):
        assert power(2, 3) == 8

    def test_zero_exponent(self):
        assert power(5, 0) == 1

    def test_one_exponent(self):
        assert power(7, 1) == 7


class TestNegate:
    def test_positive(self):
        assert negate(5) == -5

    def test_negative(self):
        assert negate(-3) == 3

    def test_zero(self):
        assert negate(0) == 0


class TestAbsolute:
    def test_positive(self):
        assert absolute(5) == 5

    def test_negative(self):
        assert absolute(-5) == 5
