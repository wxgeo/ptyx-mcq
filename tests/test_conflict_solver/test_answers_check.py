from ptyx_mcq.scan.data.conflict_gestion.data_check.cl_fix import (
    ClAnswersReviewer as AnswersReviewer,
)
from ptyx_mcq.scan.data.documents import Document
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
    modified = {
        A(1): CbxState.PROBABLY_CHECKED,
        A(2): CbxState.PROBABLY_UNCHECKED,
        A(3): CbxState.PROBABLY_UNCHECKED,
        A(4): CbxState.PROBABLY_CHECKED,
    }
    for a, state in modified.items():
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
    for a in modified:
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
    # Shortcuts:
    doc_id = DocumentId(1)
    config = patched_conflict_solver.scan_data.config
    doc_data: DocumentData = patched_conflict_solver.data[doc_id]
    detection_status = {page: doc_data.pages[page].detection_status for page in doc_data.pages}
    answered = {page: doc_data.pages[page].answered for page in doc_data.pages}
    revision_status = {page: doc_data.pages[page].revision_status for page in doc_data.pages}

    # Original values after automatic evaluation.
    assert detection_status == ANSWERS_CHECK_DATA
    assert answered == ANSWERED

    # Modified values:
    detection_status[PageNum(1)] |= {(20, 1): PROBABLY_CHECKED, (25, 2): PROBABLY_UNCHECKED}  # type: ignore
    detection_status[PageNum(2)] |= {(3, 1): PROBABLY_CHECKED}  # type:ignore
    detection_status[PageNum(3)] |= {(30, 2): PROBABLY_UNCHECKED}  # type:ignore
    answered[PageNum(1)][OriginalQuestionNumber(20)].add(OriginalAnswerNumber(1))
    assert OriginalAnswerNumber(2) not in answered[PageNum(1)][OriginalQuestionNumber(25)]
    answered[PageNum(2)][OriginalQuestionNumber(3)].add(OriginalAnswerNumber(1))
    answered[PageNum(3)][OriginalQuestionNumber(30)].remove(OriginalAnswerNumber(2))

    # Since the questions and answers were shuffled when generating the document,
    # we have to retrieve the apparent question number (i.e. the one which appears on the document).
    # The same holds for the answers.
    translation = {}
    for q, a in [
        (20, 1),  # on page 1
        (25, 2),  # idem
        (3, 1),  # on page 2
        (30, 2),  # on page 3
    ]:
        q_a = (OriginalQuestionNumber(q), OriginalAnswerNumber(a))
        translation[q_a] = real2apparent(*q_a, config=config, doc_id=doc_id)

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    # noinspection PyUnboundLocalVariable
    q25, a25_2 = translation[(OriginalQuestionNumber(25), OriginalAnswerNumber(2))]
    q3, a3_1 = translation[(OriginalQuestionNumber(3), OriginalAnswerNumber(1))]
    custom_input.set_scenario(
        [
            "Page 1",
            (AnswersReviewer.ENTER_COMMAND, ">"),
            "Page 2",
            (AnswersReviewer.ENTER_COMMAND, ">"),
            "Page 3",
            (AnswersReviewer.ENTER_COMMAND, ">"),
            "Last page reached: restart review.",
            "So, we're back to page 1.",
            "(This behaviour may change in the future,",
            "maybe we should just stay on last page instead when navigating?)",
            (AnswersReviewer.ENTER_COMMAND, "<"),
            "Stay on page 1, since there is no page before.",
            (AnswersReviewer.ENTER_COMMAND, ""),
            (AnswersReviewer.IS_CORRECT, ""),
            (AnswersReviewer.SELECT_QUESTION, f"{q25}"),
            (AnswersReviewer.EDIT_ANSWERS, f"+{a25_2}"),
            (AnswersReviewer.SELECT_QUESTION, "0"),
            (AnswersReviewer.IS_CORRECT, "y"),
            "Page 2",
            (AnswersReviewer.ENTER_COMMAND, ">"),
            "Page 3",
            (AnswersReviewer.ENTER_COMMAND, ""),
            (AnswersReviewer.IS_CORRECT, "y"),
            "Last page reached: restart review.",
            "So, we go back to page 2 (this is the only remaining unreviewed page).",
            (AnswersReviewer.ENTER_COMMAND, ""),
            (AnswersReviewer.IS_CORRECT, "n"),
            (AnswersReviewer.SELECT_QUESTION, f"{q3}"),
            (AnswersReviewer.EDIT_ANSWERS, f"-{a3_1}"),
            "Finally, add it again.",
            (AnswersReviewer.SELECT_QUESTION, f"{q3}"),
            (AnswersReviewer.EDIT_ANSWERS, f"+{a3_1}"),
            (AnswersReviewer.SELECT_QUESTION, "0"),
            (AnswersReviewer.IS_CORRECT, "y"),
        ],
    )

    patched_conflict_solver.run()
    # There should be no remaining question.
    assert custom_input.is_empty(), custom_input.remaining()

    assert (
        revision_status[PageNum(1)][(OriginalQuestionNumber(25), OriginalAnswerNumber(2))]
        == RevisionStatus.MARKED_AS_CHECKED
    )
    assert answered[PageNum(1)][OriginalQuestionNumber(25)] == {2, 3}

    assert (
        revision_status[PageNum(2)][(OriginalQuestionNumber(3), OriginalAnswerNumber(1))]
        == RevisionStatus.MARKED_AS_CHECKED
    )
    assert answered[PageNum(2)][OriginalQuestionNumber(3)] == {1, 2, 6, 7}
