"""Tests for lattice.intent."""

import pytest

from lattice.intent import Intent


def test_attribute_access():
    intent = Intent({"vendor_name": "Acme", "region": "US"})
    assert intent.vendor_name == "Acme"
    assert intent.region == "US"


def test_missing_field_raises():
    intent = Intent({"vendor_name": "Acme"})
    with pytest.raises(AttributeError, match="no field 'missing'"):
        _ = intent.missing


def test_to_dict():
    intent = Intent({"a": 1, "b": 2})
    assert intent.to_dict() == {"a": 1, "b": 2}


def test_repr():
    intent = Intent({"x": 10})
    assert "x=10" in repr(intent)
