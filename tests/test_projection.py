"""Tests for lattice.projection."""

from lattice.projection import projection


def test_projection_returns_dict():
    result = projection(vendor_id="V-001", status="active")
    assert result == {"vendor_id": "V-001", "status": "active"}


def test_projection_empty():
    assert projection() == {}
