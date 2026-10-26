"""Boundary tests: Algo Manus must not contain executable Dhan order capability."""

from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"

FORBIDDEN_IDENTIFIERS = (
    "place_order",
    "modify_order",
    "cancel_order",
    "place_super_order",
    "place_forever_order",
)

FORBIDDEN_IMPORTS = (
    "dhanhq.orders",
    "dhanhq.super_order",
    "dhanhq.forever_order",
)


def python_files():
    return sorted(SRC_ROOT.rglob("*.py"))


def test_source_tree_exists():
    assert SRC_ROOT.exists()
    assert any(python_files())


@pytest.mark.parametrize("identifier", FORBIDDEN_IDENTIFIERS)
def test_no_dhan_order_function_definitions(identifier):
    offenders = []
    for path in python_files():
        text = path.read_text(encoding="utf-8")
        if f"def {identifier}(" in text:
            offenders.append(str(path))
    assert not offenders, f"Forbidden Dhan order function defined: {identifier} in {offenders}"


@pytest.mark.parametrize("module", FORBIDDEN_IMPORTS)
def test_no_dhan_order_module_imports(module):
    offenders = []
    for path in python_files():
        text = path.read_text(encoding="utf-8")
        if f"import {module}" in text or f"from {module}" in text:
            offenders.append(str(path))
    assert not offenders, f"Forbidden Dhan order module imported: {module} in {offenders}"


def test_no_scheduler_or_worker_entrypoints():
    forbidden = (
        "APScheduler",
        "BackgroundScheduler",
        "Celery",
        "RQ",
        "while True:",
    )
    offenders = []
    for path in python_files():
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in text:
                offenders.append(f"{path}: {marker}")
    assert not offenders, f"Forbidden scheduler/worker pattern found: {offenders}"
