from ptyx_mcq.scan.data.conflict_gestion.data_check.cl_fix import (
    ClAnswersReviewer as AnswersReviewer,
)
from ptyx_mcq.scan.data.questions import CbxState, Answer
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    OriginalQuestionNumber,
    ApparentAnswerNumber,
    OriginalAnswerNumber,
    ApparentQuestionNumber,
    real2apparent,
    PageNum,
    Configuration,
    apparent2real,
)

# from tests.test_conflict_solver.answers_check_data import (
#     ANSWERS_CHECK_DATA,
#     UNCHECKED,
#     CHECKED,
#     PROBABLY_CHECKED,
#     PROBABLY_UNCHECKED,
#     ANSWERED,
# )
from tests.toolbox import ASSETS_DIR


def manual_reviewed_cbx_states():
    folder = ASSETS_DIR / "test-conflict-solver/no-conflict-v2"
    config = Configuration.load(folder / "ie2.ptyx.mcq.config.json")
    states: dict[DocumentId, dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], CbxState]] = {}
    with open(folder / "manual_cbx_review.txt") as f:
        for line in f:
            if line.startswith("["):
                doc_id = DocumentId(int(line.strip()[1:-1]))
                states[doc_id] = {}
                print("#", doc_id)
            elif not line.startswith("#") and line.strip():
                q_num, answers_states = line.split(":")
                q0 = ApparentQuestionNumber(int(q_num))
                for a_num, digit in enumerate(answers_states.strip(), start=1):
                    state = CbxState.CHECKED if digit == "1" else CbxState.UNCHECKED
                    a0 = ApparentAnswerNumber(int(a_num))
                    print((q0, a0), state)
                    q, a = apparent2real(q0, a0, config, doc_id)
                    states[doc_id][(q, a)] = state
    return states


CBX_STATES = manual_reviewed_cbx_states()


# noinspection PyUnboundLocalVariable
def test_check_review(patched_conflict_solver, custom_input) -> None:
    """Test to change check status."""

    config = patched_conflict_solver.scan_data.config

    for doc in patched_conflict_solver.scan_data:
        # Test the values after the automatic evaluation of the checkboxes states.
        assert doc.detection_status == CBX_STATES[doc.doc_id]

    Q = OriginalQuestionNumber
    A = OriginalAnswerNumber
    answers = doc.questions[Q(1)].answers

    def ans(n: int) -> Answer:
        return answers[A(n)]

    assert not ans(1).checked
    assert not ans(1).needs_review
    assert ans(1).analyzed
    assert not ans(1).reviewed

    assert not ans(2).checked
    assert not ans(2).needs_review
    assert ans(2).analyzed
    assert not ans(2).reviewed

    assert not doc.checkboxes_need_review

    # Modify some checkboxes states in the last document, to pretend something went wrong.
    modifications = {
        A(1): CbxState.PROBABLY_CHECKED,
        A(2): CbxState.PROBABLY_UNCHECKED,
        A(3): CbxState.PROBABLY_UNCHECKED,
        A(4): CbxState.PROBABLY_CHECKED,
    }
    for a, state in modifications.items():
        answers[a]._initial_state = state

    assert doc.checkboxes_need_review

    assert ans(1).checked
    assert ans(1).needs_review
    assert ans(1).analyzed
    assert not ans(1).reviewed

    assert not ans(2).checked
    assert ans(2).needs_review
    assert ans(2).analyzed
    assert not ans(2).reviewed

    # Since the questions and answers were shuffled when generating the document,
    # we have to retrieve the apparent question number (i.e. the one which appears on the document).
    # The same holds for the answers.
    conv = {}
    for a in modifications:
        q_num, a_num = real2apparent(Q(1), a, config, doc.doc_id)
        assert a_num is not None
        conv[a] = a_num

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    # noinspection PyUnboundLocalVariable
    custom_input.set_scenario(
        [
            (AnswersReviewer.ENTER_COMMAND, ""),
            (AnswersReviewer.IS_CORRECT, "n"),
            (AnswersReviewer.SELECT_QUESTION, str(q_num)),
            (AnswersReviewer.EDIT_ANSWERS, f"-{conv[A(1)]} +{conv[A(2)]} -{conv[A(4)]}"),
            (AnswersReviewer.SELECT_QUESTION, "0"),
            (AnswersReviewer.IS_CORRECT, "y"),
        ],
    )

    patched_conflict_solver.run()

    assert ans(1).unchecked
    assert ans(2).checked
    assert ans(3).unchecked
    assert ans(4).unchecked

    assert ans(1).reviewed
    assert ans(2).reviewed
    assert not ans(3).reviewed
    assert ans(4).reviewed

    assert not doc.checkboxes_need_review

    # There should be no remaining question.
    assert custom_input.is_empty(), custom_input.remaining()


def test_check_review_navigation(patched_conflict_solver, custom_input) -> None:
    """Test to change check status."""
    config = patched_conflict_solver.scan_data.config

    doc = patched_conflict_solver.scan_data.index[DocumentId(17)]

    # Modify some checkboxes states in the last document, to pretend something went wrong.
    modifications: dict[PageNum, dict[ApparentQuestionNumber, dict[ApparentAnswerNumber, CbxState]]] = {
        PageNum(1): {
            ApparentQuestionNumber(1): {
                ApparentAnswerNumber(1): CbxState.PROBABLY_UNCHECKED,
                ApparentAnswerNumber(2): CbxState.PROBABLY_UNCHECKED,
            },
            ApparentQuestionNumber(2): {
                ApparentAnswerNumber(4): CbxState.PROBABLY_UNCHECKED,
            },
        },
        PageNum(2): {
            ApparentQuestionNumber(3): {
                ApparentAnswerNumber(1): CbxState.PROBABLY_CHECKED,
                ApparentAnswerNumber(2): CbxState.PROBABLY_CHECKED,
            },
        },
        PageNum(4): {
            ApparentQuestionNumber(14): {
                ApparentAnswerNumber(2): CbxState.PROBABLY_CHECKED,
                ApparentAnswerNumber(5): CbxState.PROBABLY_CHECKED,
            },
        },
    }

    for page_num in modifications:
        for q_num in modifications[page_num]:
            for a_num, state in modifications[page_num][q_num].items():
                # Since the questions and answers were shuffled when generating the document,
                # we have to retrieve the apparent question number (i.e. the one which appears on the document).
                # The same holds for the answers.
                q, a = apparent2real(q_num, a_num, config, doc.doc_id)
                doc.questions[q].answers[a]._initial_state = state
                # Memorize the conversion between apparent and real questions and answers numbers:

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    # noinspection PyUnboundLocalVariable
    custom_input.set_scenario(
        [
            "Page 1",
            (AnswersReviewer.ENTER_COMMAND, ">"),
            "Page 2",
            (AnswersReviewer.ENTER_COMMAND, ">"),
            "Page 4",
            (AnswersReviewer.ENTER_COMMAND, ">"),
            "Last page reached: restart review.",
            "So, we're back to page 1.",
            "(This behaviour may change in the future,",
            "maybe we should just stay on last page instead when navigating?)",
            (AnswersReviewer.ENTER_COMMAND, "<"),
            "Stay on page 1, since there is no page before.",
            (AnswersReviewer.ENTER_COMMAND, ""),
            (AnswersReviewer.IS_CORRECT, ""),
            (AnswersReviewer.SELECT_QUESTION, "2"),
            (AnswersReviewer.EDIT_ANSWERS, "-4"),
            (AnswersReviewer.SELECT_QUESTION, "1"),
            (AnswersReviewer.EDIT_ANSWERS, "+1 +2"),
            (AnswersReviewer.SELECT_QUESTION, "1"),
            (AnswersReviewer.EDIT_ANSWERS, "+3 -1"),
            (AnswersReviewer.SELECT_QUESTION, "0"),
            (AnswersReviewer.IS_CORRECT, "y"),
            "Page 2",
            (AnswersReviewer.ENTER_COMMAND, ">"),
            "Page 4",
            (AnswersReviewer.ENTER_COMMAND, ""),
            (AnswersReviewer.IS_CORRECT, "y"),
            "Last page reached: restart review.",
            "So, we go back to page 2 (this is the only remaining unreviewed page).",
            (AnswersReviewer.ENTER_COMMAND, ""),
            (AnswersReviewer.IS_CORRECT, "n"),
            (AnswersReviewer.SELECT_QUESTION, "3"),
            (AnswersReviewer.EDIT_ANSWERS, "-2  -1 "),
            "Finally, add it again.",
            (AnswersReviewer.SELECT_QUESTION, "3"),
            (AnswersReviewer.EDIT_ANSWERS, "+1"),
            (AnswersReviewer.SELECT_QUESTION, "0"),
            (AnswersReviewer.IS_CORRECT, "y"),
        ],
    )

    final_states: dict[PageNum, dict[ApparentQuestionNumber, dict[ApparentAnswerNumber, bool]]] = {
        PageNum(1): {
            ApparentQuestionNumber(1): {
                ApparentAnswerNumber(1): False,
                ApparentAnswerNumber(2): True,
                ApparentAnswerNumber(3): True,
            },
            ApparentQuestionNumber(2): {ApparentAnswerNumber(4): False},
        },
        PageNum(3): {
            ApparentQuestionNumber(3): {
                ApparentAnswerNumber(1): True,
                ApparentAnswerNumber(2): False,
            },
        },
        PageNum(4): {
            ApparentQuestionNumber(14): {
                ApparentAnswerNumber(2): True,
                ApparentAnswerNumber(5): True,
            },
        },
    }
    patched_conflict_solver.run()
    # There should be no remaining question.
    assert custom_input.is_empty(), custom_input.remaining()

    for page_num in final_states:
        for q_num in final_states[page_num]:
            for a_num, is_checked in final_states[page_num][q_num].items():
                # Since the questions and answers were shuffled when generating the document,
                # we have to retrieve the apparent question number (i.e. the one which appears on the document).
                # The same holds for the answers.
                q, a = apparent2real(q_num, a_num, config, doc.doc_id)
                assert doc.questions[q].answers[a].checked == is_checked
