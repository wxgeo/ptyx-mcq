from pathlib import Path
from ptyx_mcq.tools.include_parser import IncludeParser

TEST_DIR = Path(__file__).parent.resolve()


def test_include_parser():
    with open(TEST_DIR / "ptyx-files/test_new_include_syntax.ptyx") as f:
        content = f.read()
    parser = IncludeParser(TEST_DIR / "ptyx-files")
    parser.parse(content)
    assert parser.includes == {
        f"{TEST_DIR}/ptyx-files": {
            "exercises/ex1.txt": False,
            "exercises/ex2.txt": True,
        },
        f"{TEST_DIR}/ptyx-files/other_exercises/a subfolder with a space in its name": {
            "ex3.txt": True
        },
        f"{TEST_DIR}/ptyx-files/other_exercises": {
            "ex4 has spaces in its name, and other str@#g€ things too !.txt": True
        },
    }
