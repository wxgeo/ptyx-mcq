import shutil

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


def test_is_ptyx_file(tmp_path):
    # pTyX files must be accepted
    ptyx_file = TEST_DIR / "data/ptyx-files/minimal-working-example/minimal-working-example.ptyx"
    assert ptyx_file.is_file()
    assert is_ptyx_file(ptyx_file)
    # LateX files must be rejected
    latex_file = ptyx_file.with_suffix(".tex")
    assert latex_file.is_file()
    assert not is_ptyx_file(latex_file)
    # Non-existent files must be rejected
    nonexistent_file = ptyx_file.with_suffix(".nonexistent")
    assert not nonexistent_file.is_file()
    assert not is_ptyx_file(nonexistent_file)
    # pTyX files with incorrect extensions must yet be accepted
    incorrect_extension_file = tmp_path / "wrong-extension.extension"
    shutil.copy(ptyx_file, incorrect_extension_file)
    assert incorrect_extension_file.is_file()
    assert is_ptyx_file(incorrect_extension_file)


def test_get_file_with_extension():
    path = TEST_DIR / "data/test-conflict-solver/no-conflict/no-conflict.ptyx.mcq.config.json"
    assert get_file_with_extension(path.parent, extension=".ptyx.mcq.config.json") == path
    assert get_file_with_extension(path, extension=".ptyx.mcq.config.json") == path
    with pytest.raises(FileNotFoundError):
        assert get_file_with_extension(path, extension=".ptyx") == path
    with pytest.raises(FileNotFoundError):
        assert get_file_with_extension(path.parent, extension=".ptyx") == path
