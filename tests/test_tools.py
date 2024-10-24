import pytest

from ptyx_mcq.tools.extend_literal_eval import extended_literal_eval
from ptyx_mcq.tools.io_tools import is_ptyx_file, get_file_with_extension
from .toolbox import TEST_DIR


def test_extend_literal_eval():
    assert extended_literal_eval("set()") == set()

    class A(list):
        def __eq__(self, other):
            return isinstance(other, A) and super().__eq__(other)

    a = extended_literal_eval("A((1, 2, inf))", {"A": A, "inf": float("inf")})
    assert type(a) is A
    assert a == A([1, 2, float("inf")])
    assert not (a == [1, 2, float("inf")])  # Do not test with !=, since it is not reimplemented.


def test_is_ptyx_file():
    assert is_ptyx_file(TEST_DIR / "data/ptyx-files/minimal-working-example/minimal-working-example.ptyx")
    assert not is_ptyx_file(TEST_DIR / "data/ptyx-files/minimal-working-example/minimal-working-example.tex")


def test_get_file_with_extension():
    path = TEST_DIR / "data/test-conflict-solver/no-conflict/no-conflict.ptyx.mcq.config.json"
    assert get_file_with_extension(path.parent, extension=".ptyx.mcq.config.json") == path
    assert get_file_with_extension(path, extension=".ptyx.mcq.config.json") == path
    with pytest.raises(FileNotFoundError):
        assert get_file_with_extension(path, extension=".ptyx") == path
    with pytest.raises(FileNotFoundError):
        assert get_file_with_extension(path.parent, extension=".ptyx") == path
