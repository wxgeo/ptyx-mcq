import shutil
import tempfile
from pathlib import Path

import pytest
from ptyx.latex_generator import Compiler

from ptyx_mcq.tools.include_parser import IncludeParser, IncludeStatus

TEST_DIR = Path(__file__).parent.resolve()


def test_include_parser():
    with open(TEST_DIR / "ptyx-files/new_include_syntax.ptyx") as f:
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
        ptyx_file = root / "new_include_syntax.ptyx"
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

def test_successive_calls():
    root = Path("/tmp/mcq/include")
    root.mkdir(parents=True, exist_ok=True)
    questions = root / "questions"
    questions.mkdir(exist_ok=True)
    for i in (1, 2):
        with open(questions / f"{i}.ex", "w") as f:
            f.write(f"({i}.ex content)")
    ptyx_file = root / "include.ptyx"
    content = """#LOAD{mcq}#SEED{123456}
<<<<<<<<<<<<<<<<<
-- questions/1.ex
-- questions/2.ex
>>>>>>>>>>>>>>>>>
"""
    with open(ptyx_file, "w") as f:
        f.write(content)
    parser = IncludeParser(root)
    assert parser.parse(content) == """#LOAD{mcq}#SEED{123456}
<<<<<<<<<<<<<<<<<


*
#PRINT{\x1b[36mIMPORTING\x1b[0m "/tmp/mcq/include/questions/\x1b[36m1.ex\x1b[0m"}
(1.ex content)




*
#PRINT{\x1b[36mIMPORTING\x1b[0m "/tmp/mcq/include/questions/\x1b[36m2.ex\x1b[0m"}
(2.ex content)


>>>>>>>>>>>>>>>>>
"""
    for i in (3, 4):
        with open(questions / f"{i}.ex", "w") as f:
            f.write(f"({i}.ex content)")
    parser.update(ptyx_file)
    updated_content = """#LOAD{mcq}#SEED{123456}
<<<<<<<<<<<<<<<<<
-- ROOT: .
-- questions/1.ex
-- questions/2.ex
#-- AUTOMATICALLY_ADDED:
-- questions/3.ex
#-- AUTOMATICALLY_ADDED:
-- questions/4.ex
>>>>>>>>>>>>>>>>>
"""
    assert ptyx_file.read_text() == updated_content
    parser.update(ptyx_file)
    assert ptyx_file.read_text() == updated_content
    content = """#LOAD{mcq}#SEED{123456}
<<<<<<<<<<<<<<<<<
-- questions/1.ex
-- questions/2.ex
-- invalid_path.ex
>>>>>>>>>>>>>>>>>
"""
    with open(ptyx_file, "w") as f:
        f.write(content)
    with pytest.raises(Exception) as exc_info:
        parser.parse(ptyx_file.read_text(), strict=True)
    assert str(exc_info.value) == "No file corresponding to 'invalid_path.ex' in '/tmp/mcq/include'!"
    parser.update(ptyx_file)
    assert ptyx_file.read_text() == """#LOAD{mcq}#SEED{123456}
<<<<<<<<<<<<<<<<<
-- ROOT: .
-- questions/1.ex
-- questions/2.ex
#-- AUTOMATICALLY_ADDED:
-- questions/3.ex
#-- AUTOMATICALLY_ADDED:
-- questions/4.ex
>>>>>>>>>>>>>>>>>
"""


@pytest.mark.xfail
def test_latex_code():
    # Bug: "#" in file name results in a #PRINT{...#...} and #PRINT{} doesn't handle correctly hashtags.
    path = TEST_DIR / "ptyx-files/new_include_syntax.ptyx"
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
