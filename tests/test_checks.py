"""Tests V6 : checks déterministes isolés."""

import pytest

from app.evals import checks
from app.evals.checks import CheckError


def test_non_empty():
    assert checks.run_check("non_empty", "hi", None).passed
    assert not checks.run_check("non_empty", "   ", None).passed
    assert not checks.run_check("non_empty", "", None).passed


def test_json_valid():
    assert checks.run_check("json_valid", '{"ok": true}', None).passed
    assert checks.run_check("json_valid", "[1, 2, 3]", None).passed
    assert not checks.run_check("json_valid", "pas du json", None).passed


def test_contains():
    assert checks.run_check("contains:ok", "tout est ok ici", None).passed
    assert not checks.run_check("contains:zzz", "abc", None).passed
    # argument peut contenir des deux-points (split sur le premier seulement)
    assert checks.run_check("contains:a:b", "x a:b y", None).passed


def test_regex():
    assert checks.run_check(r"regex:\d{3}", "abc123", None).passed
    assert not checks.run_check(r"regex:^\d+$", "abc", None).passed


def test_equals():
    assert checks.run_check("equals:OK", "  OK  ", None).passed
    assert not checks.run_check("equals:OK", "ko", None).passed


def test_min_max_length():
    assert checks.run_check("min_length:3", "abcd", None).passed
    assert not checks.run_check("min_length:5", "abc", None).passed
    assert checks.run_check("max_length:3", "ab", None).passed
    assert not checks.run_check("max_length:2", "abcd", None).passed


def test_latency_lt():
    assert checks.run_check("latency_lt:1000", "x", 500.0).passed
    assert not checks.run_check("latency_lt:100", "x", 500.0).passed
    # latence inconnue → échoue proprement
    assert not checks.run_check("latency_lt:100", "x", None).passed


def test_unknown_check_raises():
    with pytest.raises(CheckError):
        checks.validate_spec("bogus_check")


def test_missing_argument_raises():
    with pytest.raises(CheckError):
        checks.validate_spec("contains")


def test_non_numeric_argument_raises():
    with pytest.raises(CheckError):
        checks.validate_spec("latency_lt:abc")
