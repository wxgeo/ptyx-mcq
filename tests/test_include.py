import shutil
import tempfile
from pathlib import Path

import pytest
from ptyx.latex_generator import Compiler

from ptyx_mcq.tools.include_parser import IncludeParser, IncludeStatus

TEST_DIR = Path(__file__).parent.resolve()


def test_include_parser():
    with open(TEST_DIR / "ptyx-files/test_new_include_syntax.ptyx") as f:
        content = f.read()
    parser = IncludeParser(TEST_DIR / "ptyx-files")
    parser.parse(content)
    assert parser.includes == {
        f"{TEST_DIR}/ptyx-files": {
            "exercises/ex1.ex": IncludeStatus.DISABLED,
            "exercises/ex2.ex": IncludeStatus.OK,
        },
        f"{TEST_DIR}/ptyx-files/other_exercises/a subfolder with a space in its name": {
            "ex3.ex": IncludeStatus.OK,
        },
        f"{TEST_DIR}/ptyx-files/other_exercises": {
            "ex4 has spaces in its name, and other str@#g€ things too !.ex": IncludeStatus.OK,
            "some/invalid/path.ex": IncludeStatus.NOT_FOUND,
        },
    }


def test_update_include():
    Status = IncludeStatus
    with tempfile.TemporaryDirectory() as tmpdirname:
        root = Path(tmpdirname) / "ptyx-files"
        ptyx_file = root / "test_new_include_syntax.ptyx"
        shutil.copytree(TEST_DIR / "ptyx-files/", root)
        parser = IncludeParser(root)
        parser.update(ptyx_file)
        assert parser.includes == {
            f"{tmpdirname}/ptyx-files": {
                "exercises/ex1.ex": Status.DISABLED,
                "exercises/ex2.ex": Status.OK,
                "other_exercises/a subfolder with a space in its name/ex5 - smallgraphlib import.ex": Status.AUTOMATICALLY_ADDED,
            },
            f"{tmpdirname}/ptyx-files/other_exercises/a subfolder with a space in its name": {
                "ex3.ex": Status.OK
            },
            f"{tmpdirname}/ptyx-files/other_exercises": {
                "ex4 has spaces in its name, and other str@#g€ things too !.ex": Status.OK
            },
        }

@pytest.mark.xfail
def test_latex_code():
    path = TEST_DIR / "ptyx-files/test_new_include_syntax.ptyx"
    c = Compiler()
    latex = c.parse(path=path)
    for line in latex.split():
        assert not line.startswith("-- "), line
        assert not line.startswith("!-- "), line


#         assert f"""
# -- ROOT: {tmpdirname}/ptyx-files
# !-- {tmpdirname}/ptyx-files/exercises/ex1.ex
# -- {tmpdirname}/ptyx-files/exercises/ex2.ex
# # New path detected:
# -- {tmpdirname}/ptyx-files/other_exercises/a subfolder with a space in its name/ex3.ex
# # New path detected:
# -- {tmpdirname}/ptyx-files/other_exercises/a subfolder with a space in its name/ex5 - smallgraphlib import.ex
# # New path detected:
# -- {tmpdirname}/ptyx-files/other_exercises/ex4 has spaces in its name, and other str@#g€ things too !.ex
# """ in content
#
#     assert f"""
# -- ROOT: {tmpdirname}/ptyx-files/other_exercises/a subfolder with a space in its name
# -- {tmpdirname}/ptyx-files/other_exercises/a subfolder with a space in its name/ex3.ex
# # New path detected:
# -- {tmpdirname}/ptyx-files/other_exercises/a subfolder with a space in its name/ex5 - smallgraphlib import.ex
# """in content
#
#     assert f"""
# -- ROOT: {tmpdirname}/ptyx-files/other_exercises
# -- {tmpdirname}/ptyx-files/other_exercises/ex4 has spaces in its name, and other str@#g€ things too !.ex
# # New path detected:
# -- {tmpdirname}/ptyx-files/other_exercises/a subfolder with a space in its name/ex5 - smallgraphlib import.ex
# # New path detected:
# -- {tmpdirname}/ptyx-files/other_exercises/a subfolder with a space in its name/ex5 - smallgraphlib import.ex
# """ in content
#
