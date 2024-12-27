from ptyx_mcq.scan.data.conflict_gestion.data_check.cl_fix import (
    ClAnswersReviewer as AnswersReviewer,
)
from ptyx_mcq.scan.data.documents import DocumentData
from ptyx_mcq.scan.data.questions import RevisionStatus
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    OriginalQuestionNumber,
    ApparentAnswerNumber,
    OriginalAnswerNumber,
    ApparentQuestionNumber,
    real2apparent,
    PageNum,
)
from tests.test_conflict_solver.answers_check_data import (
    ANSWERS_CHECK_DATA,
    UNCHECKED,
    CHECKED,
    PROBABLY_CHECKED,
    PROBABLY_UNCHECKED,
    ANSWERED,
)


def test_check_review(patched_conflict_solver, custom_input) -> None:
    """Test to change check status."""
    # Shortcuts:
    doc_id = DocumentId(1)
    page = PageNum(1)
    doc_data: DocumentData = patched_conflict_solver.data[doc_id]
    detection_status = doc_data.pages[page].detection_status
    answered = doc_data.pages[page].answered
    revision_status = doc_data.pages[page].revision_status

    # Original values after automatic evaluation.
    assert detection_status == {
        (4, 1): UNCHECKED,
        (4, 2): UNCHECKED,
        (4, 3): CHECKED,
        (4, 4): UNCHECKED,
        (4, 5): UNCHECKED,
        (4, 6): UNCHECKED,
        (20, 1): UNCHECKED,
        (20, 2): UNCHECKED,
        (20, 3): UNCHECKED,
        (20, 4): CHECKED,
        (20, 5): CHECKED,
        (20, 6): UNCHECKED,
        (20, 7): UNCHECKED,
        (25, 1): UNCHECKED,
        (25, 2): UNCHECKED,
        (25, 3): CHECKED,
        (25, 4): UNCHECKED,
        (25, 5): UNCHECKED,
        (25, 6): UNCHECKED,
        (25, 7): UNCHECKED,
        (25, 8): UNCHECKED,
        (25, 9): UNCHECKED,
    }

    # Modify some detection values, to pretend something went wrong.
    # Let's modify answers 1, 2, 3 and 6 for question 4.
    original_question_num = OriginalQuestionNumber(4)
    a1, a2, a3, a6 = original_answers_numbers = tuple(OriginalAnswerNumber(i) for i in (1, 2, 3, 6))
    assert answered == {4: {3}, 20: {4, 5}, 25: {3}}
    answered[original_question_num].add(OriginalAnswerNumber(6))
    assert answered == {4: {3, 6}, 20: {4, 5}, 25: {3}}
    modified_detection_status = (PROBABLY_CHECKED, PROBABLY_CHECKED, PROBABLY_UNCHECKED, CHECKED)
    for original_answer_num, detected_as in zip(original_answers_numbers, modified_detection_status):
        detection_status[(original_question_num, original_answer_num)] = detected_as

    # Since the questions and answers were shuffled when generating the document,
    # we have to retrieve the apparent question number (i.e. the one which appears on the document).
    # The same holds for the answers.
    question: ApparentQuestionNumber
    # noinspection PyTypeChecker
    answers: dict[OriginalAnswerNumber, ApparentAnswerNumber | None] = {}
    for i in original_answers_numbers:
        question, answers[i] = real2apparent(
            original_question_num, i, patched_conflict_solver.scan_data.config, doc_id=doc_id
        )

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    # noinspection PyUnboundLocalVariable
    custom_input.set_scenario(
        [
            (AnswersReviewer.ENTER_COMMAND, ""),
            (AnswersReviewer.IS_CORRECT, "n"),
            (AnswersReviewer.SELECT_QUESTION, str(question)),
            (AnswersReviewer.EDIT_ANSWERS, f"+{answers[a1]} +{answers[a2]} -{answers[a3]}"),
            (AnswersReviewer.SELECT_QUESTION, "0"),
            (AnswersReviewer.IS_CORRECT, "y"),
        ],
    )

    patched_conflict_solver.run()

    assert answered[OriginalQuestionNumber(4)] == {1, 2, 6}

    expected_revision_status = (
        RevisionStatus.MARKED_AS_CHECKED,
        RevisionStatus.MARKED_AS_CHECKED,
        RevisionStatus.MARKED_AS_UNCHECKED,
    )

    for original_answer_num, status in zip(original_answers_numbers, expected_revision_status):
        assert revision_status[(original_question_num, original_answer_num)] == status

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
