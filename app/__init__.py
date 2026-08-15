"""LLM Cockpit.

The version lives here rather than being read from pyproject.toml: the frozen
bundle ships no pyproject, so reading it would work in a checkout and fail in
the packaged app. tests/test_version.py keeps the two in step.
"""

__version__ = "0.1.0"
