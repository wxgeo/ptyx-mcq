import shutil
from pathlib import Path

import pytest
from ptyx.latex_generator import Compiler

# noinspection PyProtectedMember
from ptyx_mcq.make.include_directives_parsing import (
    parse_code,
    Directive,
    ChangeDirectory,
    AddPath,
    IncludesUpdater,
    update_file,
    resolve_includes_from_file,
    UnsafeUpdate,
)
from tests import ASSETS_DIR


def _dir(directory: str, is_disabled=False, comment=""):
    return ChangeDirectory(path=Path(directory), is_disabled=is_disabled, comment=comment)


def _file(file: str, is_disabled=False, comment=""):
    return AddPath(path=Path(file), is_disabled=is_disabled, comment=comment)


DATA_DIR = ASSETS_DIR / "ptyx-files"


def test_include_parser():
    content = (DATA_DIR / "with-exercises/new_include_syntax.ptyx").read_text(encoding="utf8")
    directives = [line for line in parse_code(content) if isinstance(line, Directive)]
    assert directives == [
        _file("exercises/ex1.ex", is_disabled=True),
        _file("exercises/ex2.ex"),
        _dir("other_exercises/a subfolder with a space in its name"),
        _file("ex3.ex"),
        _dir("other_exercises"),
        _file("ex4 has spaces in its name, and other str@#g€ things too !.ex"),
        _file("some/invalid/path.ex"),
    ]


def test_include_false_positives():
    content = (DATA_DIR / "with-exercises/new.ptyx").read_text(encoding="utf8")
    directives = [line for line in parse_code(content) if isinstance(line, Directive)]
    assert directives == [
        _file("questions/**/*.ex"),
    ]


def test_update_include():
    ptyx_file = DATA_DIR / "with-exercises/new_include_syntax.ptyx"
    updater = IncludesUpdater(ptyx_file)
    updater.update_file_content()
    assert updater.includes == {
        _dir("other_exercises/a subfolder with a space in its name"): [
            _file("ex3.ex"),
            _file("ex5 - smallgraphlib import.ex", comment="new"),
        ],
        _dir("other_exercises"): [
            _file("ex4 has spaces in its name, and other str@#g€ things too !.ex"),
            _file("some/invalid/path.ex", comment="missing", is_disabled=True),
        ],
    }
    assert set(updater.local_includes) == {
        _file("exercises/ex1.ex", is_disabled=True),
        _file("exercises/ex2.ex"),
        _file("example_with_verbatim/ex/2.ex", comment="new"),
        _file("example_with_verbatim/ex/1.ex", comment="new"),
        _file("example_with_verbatim/ex/3.ex", comment="new"),
        _file("questions/question1.ex", comment="new"),
        _file("questions/question2.ex", comment="new"),
        _file("questions/question3.ex", comment="new"),
        _file("questions/question4.ex", comment="new"),
        _file("short questions/question1.ex", comment="new"),
        _file("short questions/question2.ex", comment="new"),
        _file("short questions/question3.ex", comment="new"),
        _file("short questions/question4.ex", comment="new"),
    }
    assert not updater.is_updating_safe


def test_successive_calls(tmp_path):
    # Generate a basic directory structure:
    # questions
    #      ├── 1.ex
    #      └── 2.ex
    (questions := tmp_path / "questions").mkdir(exist_ok=True)
    for i in (1, 2):
        with open(questions / f"{i}.ex", "w") as f:
            f.write(f"({i}.ex content)")

    # Generate the ptyx file:
    ptyx_file = tmp_path / "include.ptyx"
    content = """#LOAD{mcq}#SEED{123456}
<<<<<<<<<<<<<<<<<
-- questions/1.ex
-- questions/2.ex
>>>>>>>>>>>>>>>>>
"""
    with open(ptyx_file, "w") as f:
        f.write(content)

    # Test the inclusion of the `.ex` files:
    assert (
        resolve_includes_from_file(ptyx_file)
        == f"""#LOAD{{mcq}}#SEED{{123456}}
<<<<<<<<<<<<<<<<<
*
#INCLUDE_START{{{tmp_path/"questions/1.ex"}}}{{2}}
#QUESTION_NAME{{1.ex}}
(1.ex content)
#INCLUDE_END

*
#INCLUDE_START{{{tmp_path/"questions/2.ex"}}}{{3}}
#QUESTION_NAME{{2.ex}}
(2.ex content)
#INCLUDE_END

>>>>>>>>>>>>>>>>>
"""
    )

    # Generate new .ex files, and test updating.
    for i in (3, 4):
        with open(questions / f"{i}.ex", "w") as f:
            f.write(f"({i}.ex content)")
    update_file(ptyx_file)
    updated_content = """#LOAD{mcq}#SEED{123456}
<<<<<<<<<<<<<<<<<
-- questions/1.ex
-- questions/2.ex
@new: -- questions/3.ex
@new: -- questions/4.ex
>>>>>>>>>>>>>>>>>
"""
    assert ptyx_file.read_text() == updated_content

    # Calling `update_file()` without any new .ex file should leave the ptyx file unchanged.
    update_file(ptyx_file)
    assert ptyx_file.read_text() == updated_content

    # Testing with an invalid path:
    content = """#LOAD{mcq}#SEED{123456}
<<<<<<<<<<<<<<<<<
-- questions/1.ex
-- questions/2.ex
-- invalid_path.ex
>>>>>>>>>>>>>>>>>
"""
    with open(ptyx_file, "w") as f:
        f.write(content)
    with pytest.raises(FileNotFoundError) as exc_info:
        resolve_includes_from_file(ptyx_file)
    assert str(exc_info.value) == f"File 'invalid_path.ex' not found in folder `{tmp_path}`!"
    update_file(ptyx_file)
    assert (
        ptyx_file.read_text()
        == """#LOAD{mcq}#SEED{123456}
<<<<<<<<<<<<<<<<<
@missing: !-- invalid_path.ex
-- questions/1.ex
-- questions/2.ex
@new: -- questions/3.ex
@new: -- questions/4.ex
>>>>>>>>>>>>>>>>>
"""
    )

    # Test `clean` option.
    update_file(ptyx_file, clean=True)
    assert (
        ptyx_file.read_text()
        == """#LOAD{mcq}#SEED{123456}
<<<<<<<<<<<<<<<<<
-- questions/1.ex
-- questions/2.ex
-- questions/3.ex
-- questions/4.ex
>>>>>>>>>>>>>>>>>
"""
    )


def test_update_empty_ex_list(tmp_path):
    ex_path = DATA_DIR / "with-exercises/exercises"
    mcq_path = tmp_path / "mcq"
    mcq_path.mkdir(parents=True)
    content = f"""
#LOAD{{mcq}}#SEED{{945544}}
<<<<
-- DIR: {str(ex_path)}
>>>>"""
    ptyx_path = mcq_path / "mcq.ptyx"
    with open(ptyx_path, "w") as ptyx_file:
        ptyx_file.write(content)
    update_file(ptyx_path)
    assert (
        ptyx_path.read_text()
        == f"""
#LOAD{{mcq}}#SEED{{945544}}
<<<<
-- DIR: {str(ex_path)}
@new: -- ex1.ex
@new: -- ex2.ex
>>>>
"""
    )


def test_unsafe_update(tmp_path):
    # Copy the files needed for the test:
    # <tmp_path>
    #     ├── new_include_syntax.ptyx
    #     └── exercises
    #             ├── 1.ex
    #             └── 2.ex
    root = DATA_DIR / "with-exercises"
    shutil.copy(root / "new_include_syntax.ptyx", tmp_path)
    (tmp_path / "exercises").mkdir()
    for i in (1, 2):
        shutil.copy(root / f"exercises/ex{i}.ex", tmp_path / "exercises")
        shutil.copy(root / f"exercises/ex{i}.ex", tmp_path / "exercises")
    ptyx_path = tmp_path / "new_include_syntax.ptyx"

    # Update is unsafe.
    with pytest.raises(UnsafeUpdate) as exc_info:
        update_file(ptyx_path)
    assert exc_info.value.args[0] == f"Update of {tmp_path}/new_include_syntax.ptyx does not seem safe."

    # But we can force it.
    update_file(ptyx_path, force=True)
    str_directives = [str(line) for line in parse_code(ptyx_path.read_text()) if isinstance(line, Directive)]
    assert str_directives == [
        "!-- exercises/ex1.ex",
        "-- exercises/ex2.ex",
        "@missing: !-- DIR: other_exercises",
        "@missing: !-- ex4 has spaces in its name, and other str@#g€ things too !.ex",
        "@missing: !-- some/invalid/path.ex",
        "@missing: !-- DIR: other_exercises/a subfolder with a space in its name",
        "@missing: !-- ex3.ex",
    ]


def test_latex_code(tmp_path):
    """Bug: `#` in file name results in a #PRINT{...#...},
    but #PRINT{} doesn't handle correctly hashtags."""
    # Generate the files needed for the test:
    # <tmp_path>
    #     ├── test.ptyx
    #     └── s#me str@nge ├old€r N@Me
    #             ├── s#me stüpiɖ ├il€ N@Me.ex
    (ptyx_path := tmp_path / "test.ptyx").write_text(
        """
#LOAD{mcq}
#SEED{5}
<<<
-- **/*.ex
>>>  
"""
    )
    (folder := tmp_path / "s#me str@nge ├old€r N@Me").mkdir()
    (ex_file := folder / "s#me stüpiɖ ├il€ N@Me.ex").write_text(
        """
"Hello world!" is a:
- question
+ exclamation
- 42
"""
    )
    assert parse_code(ptyx_path.read_text()) == [
        "",
        "#LOAD{mcq}",
        "#SEED{5}",
        "<<<",
        AddPath(Path("**/*.ex"), is_disabled=False, comment=""),
        ">>>  ",
    ]
    assert (
        resolve_includes_from_file(ptyx_file=ptyx_path)
        == f"""
#LOAD{{mcq}}
#SEED{{5}}
<<<
*
#INCLUDE_START{{{ex_file}}}{{4}}
#QUESTION_NAME{{s##me stüpiɖ ├il€ N@Me.ex}}
"Hello world!" is a:
- question
+ exclamation
- 42
#INCLUDE_END

>>>  
"""
    )
    c = Compiler()
    latex = c.parse(path=ptyx_path)
    for line in latex.split("\n"):
        assert not line.startswith("-- "), line
        assert not line.startswith("!-- "), line
    assert "Hello world!" in latex


def test_includes_outside_mcq(tmp_path):
    (tmp_path / "header.txt").write_text("Introduction...")
    (tmp_path / "footer.txt").write_text("Conclusion.")
    # Generate the ptyx file:
    ptyx_file = tmp_path / "include.ptyx"
    root = DATA_DIR / "with-exercises"
    ptyx_file.write_text(
        f"""
#LOAD{{mcq}}#SEED{{123456}}
-- header.txt
-- DIR: {root}/short questions
<<<<<<<<<<<<<<<<<
-- question1.ex
-- question2.ex
>>>>>>>>>>>>>>>>>
-- DIR: .
-- footer.txt
"""
    )
    update_file(ptyx_file)
    assert (
        ptyx_file.read_text()
        == f"""
#LOAD{{mcq}}#SEED{{123456}}
-- header.txt
-- DIR: {root}/short questions
<<<<<<<<<<<<<<<<<
-- DIR: {root}/short questions
-- question1.ex
-- question2.ex
@new: -- question3.ex
@new: -- question4.ex
>>>>>>>>>>>>>>>>>
-- DIR: .
-- footer.txt
"""
    )
    assert (
        resolve_includes_from_file(ptyx_file)
        == f"""
#LOAD{{mcq}}#SEED{{123456}}
#INCLUDE_START{{{tmp_path / "header.txt"}}}{{2}}
Introduction...
#INCLUDE_END

<<<<<<<<<<<<<<<<<
*
#INCLUDE_START{{{root/"short questions/question1.ex"}}}{{6}}
#QUESTION_NAME{{question1.ex}}
q1

+ 1
- 2
#INCLUDE_END

*
#INCLUDE_START{{{root/"short questions/question2.ex"}}}{{7}}
#QUESTION_NAME{{question2.ex}}
q2

- 1
+ 2
#INCLUDE_END

*
#INCLUDE_START{{{root/"short questions/question3.ex"}}}{{8}}
#QUESTION_NAME{{question3.ex}}
q3

- 1
- 2
+ 3
#INCLUDE_END

*
#INCLUDE_START{{{root/"short questions/question4.ex"}}}{{9}}
#QUESTION_NAME{{question4.ex}}
q4

- 1
- 2
- 3
+ 4
#INCLUDE_END

>>>>>>>>>>>>>>>>>
#INCLUDE_START{{{tmp_path/"footer.txt"}}}{{12}}
Conclusion.
#INCLUDE_END

"""
    )
