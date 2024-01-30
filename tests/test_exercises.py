from ptyx_mcq.make.exercises_parsing import generate_exercise_latex_code_for_preview

from .toolbox import TEST_DIR, has_same_rstripped_lines


def get_content(name: str) -> str:
    return (TEST_DIR / "data/single-exercises" / name).read_text(encoding="utf8")


def test_conditional_answer():
    code = get_content("conditional-answer/conditional-answer.ex")
    latex = get_content("conditional-answer/conditional-answer.tex")
    print(generate_exercise_latex_code_for_preview(code=code))
    assert has_same_rstripped_lines(generate_exercise_latex_code_for_preview(code=code), latex)
