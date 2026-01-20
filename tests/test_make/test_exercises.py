from ptyx_mcq.make.exercises_parsing import generate_exercise_latex_code_for_preview

from tests.test_make.toolbox import normalize_text
from tests import ASSETS_DIR


def get_content(name: str) -> str:
    return (ASSETS_DIR / "single-exercises" / name).read_text(encoding="utf8")


def test_conditional_answer():
    code = get_content("conditional-answer/conditional-answer.ex")
    latex = get_content("conditional-answer/conditional-answer.tex")
    assert normalize_text(generate_exercise_latex_code_for_preview(code=code)) == normalize_text(latex)


def test_load_specific_packages():
    code = get_content("specific-packages/specific-packages.ex")
    latex = get_content("specific-packages/specific-packages.tex")
    assert normalize_text(generate_exercise_latex_code_for_preview(code=code)) == normalize_text(latex)
