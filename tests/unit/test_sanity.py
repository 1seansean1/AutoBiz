"""Sanity test to verify pytest is working."""

import pytest


@pytest.mark.unit
@pytest.mark.P0
@pytest.mark.deterministic
def test_sanity() -> None:
    """Verify pytest execution works."""
    assert True, "Sanity check should always pass"


@pytest.mark.unit
@pytest.mark.P0
@pytest.mark.deterministic
def test_import() -> None:
    """Verify autobiz package can be imported."""
    import autobiz

    assert autobiz.__version__ == "0.1.0"
