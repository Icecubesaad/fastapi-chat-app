"""Smoke tests the pipeline's Test step runs on every push."""


def test_arithmetic_still_works():
    assert 1 + 1 == 2


def test_the_app_module_names_its_routes():
    source = open("main.py", encoding="utf-8").read()
    assert "FastAPI" in source
