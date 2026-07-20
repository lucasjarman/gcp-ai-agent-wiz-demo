import ast

import pytest

from sandbox_runner import SafetyValidator


def test_validator_allows_statistics():
    SafetyValidator().visit(ast.parse("import statistics\nstatistics.mean(data)"))


def test_validator_blocks_operating_system_access():
    with pytest.raises(ValueError, match="not allowed"):
        SafetyValidator().visit(ast.parse("import os\nos.listdir('/')"))


def test_validator_blocks_dunder_attributes():
    with pytest.raises(ValueError, match="not allowed"):
        SafetyValidator().visit(ast.parse("data.__class__"))
