"""Готовая изоляция тестов, в том числе для стартового дефекта ЛР5."""
import importlib
import pytest


@pytest.fixture(autouse=True)
def independent_runtime():
    from app.services import assembly
    from app import api
    importlib.reload(assembly)
    importlib.reload(api)
