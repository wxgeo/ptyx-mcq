import pytest

from ptyx_mcq.tools.config_parser import recursively_update_dict


def test_dict_updater():
    d1 = {"main": {"nested": {"a": 0, "b": 1}, "flat": [True, False]}}
    d2 = {"main": {"nested": {"b": 5}, "flat": [True]}}
    recursively_update_dict(d1, d2)
    assert d1 == {"main": {"nested": {"a": 0, "b": 5}, "flat": [True]}}
    # Different value type (float instead of int).
    d3 = {"main": {"nested": {"b": 4.8}}}
    with pytest.raises(ValueError):
        # noinspection PyTypeChecker
        recursively_update_dict(d1, d3)
    # noinspection PyTypeChecker
    recursively_update_dict(d1, d3, verify_types=False)
    assert d1 == {"main": {"nested": {"a": 0, "b": 4.8}, "flat": [True]}}
