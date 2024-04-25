

from ptyx_mcq.scan.data_gestion.conflict_handling import NamesReviewer
from ptyx_mcq.scan.data_gestion.conflict_handling.data_check import Action
from ptyx_mcq.scan.data_gestion.document_data import DocumentData
from ptyx_mcq.tools.config_parser import DocumentId, StudentName

# NamesReviewer.CORRECT_Y_N = "Is it correct? (Y/n)"
# NamesReviewer.ASK_FOR_NAME = "Student name or ID (or / to skip this document):"
# NamesReviewer.PRESS_ENTER = "-- Press ENTER --"

STUDENT_NAMES = ["Robert Le Hardi", "Jules Le Preux", "Edouard Le Couard", "Jules de chez Smith"]


def fail_on_input(text=""):
    assert False, f"Unexpected input request: {text!r}"


def test_no_conflict(monkeypatch, patched_conflict_solver):
    """No interaction should occur if there is no conflict."""
    monkeypatch.setattr("builtins.input", fail_on_input)
    patched_conflict_solver.run()
    data = patched_conflict_solver.data
    assert sorted(data) == [1, 2, 3, 4], data


def test_missing_name(patched_conflict_solver, custom_input) -> None:
    """Test interactions if a name is missing."""
    doc_data: DocumentData = patched_conflict_solver.data[DocumentId(1)]
    student_name = doc_data.name
    assert student_name == "Robert Le Hardi"
    doc_data.name = StudentName("")

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            (NamesReviewer.PRESS_ENTER, ""),
            # No name provided: ask again
            (NamesReviewer.ASK_FOR_NAME, ""),
            # Invalid student id provided: ask again
            (NamesReviewer.ASK_FOR_NAME, "22"),
            # Custom name: ok (this behavior may change in the future...)
            (NamesReviewer.ASK_FOR_NAME, "Any name"),
            # Ask for confirmation; answer "n", so ask again
            # Valid student name
            (NamesReviewer.ASK_FOR_NAME, "Robert Le Hardi"),
            # Ask for confirmation; answer "n", so ask again.
            (NamesReviewer.CORRECT_Y_N, "n"),
            # Valid student id
            (NamesReviewer.ASK_FOR_NAME, "22205649"),
            # Ask for confirmation; answer "Y", so quit (success)
            (NamesReviewer.CORRECT_Y_N, "Y"),
        ],
    )

    patched_conflict_solver.run()

    assert patched_conflict_solver.data[DocumentId(1)].name == student_name

    # There should be no remaining question.
    assert custom_input.is_empty(), custom_input.remaining()

    assert doc_data is patched_conflict_solver.data[DocumentId(1)]

    # Test that student name is memorized now.
    doc_data.name = StudentName("")
    custom_input.set_scenario([])

    patched_conflict_solver.run()
    assert patched_conflict_solver.data[DocumentId(1)].name == student_name

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_missing_name2(patched_conflict_solver, custom_input) -> None:
    """Test interactions if a name is missing."""
    doc_data: DocumentData = patched_conflict_solver.data[DocumentId(1)]
    student_name = doc_data.name
    assert student_name == "Robert Le Hardi"
    doc_data.name = StudentName("")

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, student_name),
            (NamesReviewer.CORRECT_Y_N, "Y"),
        ],
    )

    patched_conflict_solver.run()
    assert patched_conflict_solver.data[DocumentId(1)].name == student_name

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_several_missing_names(patched_conflict_solver, custom_input) -> None:
    """Test interaction if several names are missing.

    In particular, several missing names should not be detected as duplicates!
    """
    data = patched_conflict_solver.data

    backup_names: dict[int, StudentName] = {}

    for n in (1, 2, 3):
        doc_id = DocumentId(n)
        assert data[doc_id].name != StudentName("")
        backup_names[n] = data[doc_id].name
        data[doc_id].name = StudentName("")

    assert data[DocumentId(4)].name == StudentName("Jules de chez Smith")

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, backup_names[1]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, backup_names[2]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, backup_names[3]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
        ],
    )

    patched_conflict_solver.run()
    for n in (1, 2, 3):
        assert patched_conflict_solver.data[DocumentId(n)].name == backup_names[n]

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_missing_names_navigation(patched_conflict_solver, custom_input) -> None:
    """Test interaction if several names are missing.

    In particular, several missing names should not be detected as duplicates!
    """
    data = patched_conflict_solver.data

    backup_names: dict[int, StudentName] = {}

    for n in (1, 2, 3, 4):
        doc_id = DocumentId(n)
        assert data[doc_id].name != StudentName("")
        backup_names[n] = data[doc_id].name
        data[doc_id].name = StudentName("")

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            "DOC1 - WRONG NAME",
            (NamesReviewer.PRESS_ENTER, ""),
            # set (wrong) 1st document name, automatically go to 2nd
            (NamesReviewer.ASK_FOR_NAME, backup_names[3]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            # ----------------
            "DOC2 - BACK TO 1",
            (NamesReviewer.PRESS_ENTER, ""),
            # back to 1st document
            (NamesReviewer.ASK_FOR_NAME, Action.BACK),
            # ----------------
            "DOC1 - RIGHT NAME",
            (NamesReviewer.PRESS_ENTER, ""),
            # set 1st document name, automatically go to 2nd
            (NamesReviewer.ASK_FOR_NAME, backup_names[1]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            # ----------------
            "DOC2 - WRONG NAME",
            (NamesReviewer.PRESS_ENTER, ""),
            # set (wrong) 2nd document name, automatically go to 3rd
            (NamesReviewer.ASK_FOR_NAME, backup_names[4]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            # ----------------
            "DOC3 - RIGHT NAME",
            (NamesReviewer.PRESS_ENTER, ""),
            # set 3rd document name, automatically go to 4th
            (NamesReviewer.ASK_FOR_NAME, backup_names[3]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            # ----------------
            "DOC4 - BACK TO 3",
            (NamesReviewer.PRESS_ENTER, ""),
            # back to 3rd document
            (NamesReviewer.ASK_FOR_NAME, Action.BACK),
            # ----------------
            "DOC3 - BACK TO 2",
            (NamesReviewer.PRESS_ENTER, ""),
            # back to 2nd document
            (NamesReviewer.ASK_FOR_NAME, Action.BACK),
            # ----------------
            "DOC2 - RIGHT NAME",
            (NamesReviewer.PRESS_ENTER, ""),
            # set 2nd document name, automatically go to 3rd
            (NamesReviewer.ASK_FOR_NAME, backup_names[2]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            # ----------------
            "DOC3 - GO TO 4",
            (NamesReviewer.PRESS_ENTER, ""),
            # go directly to 4th document
            (NamesReviewer.ASK_FOR_NAME, Action.NEXT),
            # ----------------
            "DOC4 - RIGHT NAME",
            (NamesReviewer.PRESS_ENTER, ""),
            # set 4th document name
            (NamesReviewer.ASK_FOR_NAME, backup_names[4]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
        ],
    )

    patched_conflict_solver.run()
    for n in (1, 2, 3):
        assert patched_conflict_solver.data[DocumentId(n)].name == backup_names[n]

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_missing_names_autocomplete(patched_conflict_solver, custom_input) -> None:
    """Test name suggestion."""
    data = patched_conflict_solver.data
    id_names = [
        ("22205649", "Robert Le Hardi"),
        ("22302844", "Jules Le Preux"),
        ("22212706", "Edouard Le Couard"),
        ("22306921", "Jules de chez Smith"),
    ]

    for n in range(len(id_names)):
        assert data[DocumentId(n + 1)].name == StudentName(id_names[n][1])
        data[DocumentId(n + 1)].name = StudentName("")
        # assert data[DocumentId(n + 1)].student_id == StudentId(id_names[n][0])

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, "Rob"),
            (NamesReviewer.ASK_FOR_NAME, "ok"),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, "223028"),
            (NamesReviewer.ASK_FOR_NAME, "OK"),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, "Couard"),
            (NamesReviewer.ASK_FOR_NAME, "OK"),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, "12306921"),
            (NamesReviewer.ASK_FOR_NAME, "Ok"),
            (NamesReviewer.CORRECT_Y_N, "Y"),
        ],
    )

    patched_conflict_solver.run()

    for n in range(len(id_names)):
        assert data[DocumentId(n + 1)].name == StudentName(id_names[n][1])

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_missing_name_skip_doc(patched_conflict_solver, custom_input) -> None:
    """Skip a document."""
    doc_data: DocumentData = patched_conflict_solver.data[DocumentId(1)]
    student_name = doc_data.name
    assert student_name == "Robert Le Hardi"
    doc_data.name = StudentName("")

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successives expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, "/"),
        ],
    )

    patched_conflict_solver.run()
    assert DocumentId(1) not in patched_conflict_solver.data

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_duplicate_name(patched_conflict_solver, custom_input):
    """Skip a document."""
    student_names = {i: patched_conflict_solver.data[DocumentId(i)].name for i in (1, 2, 3, 4)}
    assert list(student_names.values()) == STUDENT_NAMES

    # Create duplicate name conflict: give the same name to documents 1 and 2.
    patched_conflict_solver.data[DocumentId(2)].name = student_names[1]

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successives expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            "I) Resolve the conflict between doc 1 and doc 2",
            "I.1) DOC 1",
            (NamesReviewer.PRESS_ENTER, ""),
            # Give invalid student id: ask again
            (NamesReviewer.ASK_FOR_NAME, "0"),
            # Don't change name
            (NamesReviewer.ASK_FOR_NAME, Action.NEXT),
            # Confirm ("yes" should be the default answer)
            # (NamesReviewer.CORRECT_Y_N, ""),
            "I.1) DOC 2",
            (NamesReviewer.PRESS_ENTER, ""),
            # Create another conflict(give the student name of the doc number 3 too)
            (NamesReviewer.ASK_FOR_NAME, student_names[3]),
            # Confirm.
            (NamesReviewer.CORRECT_Y_N, ""),
            "II) Resolve the newly created conflict between doc 2 and doc 3.",
            "II.1) DOC 2",
            (NamesReviewer.PRESS_ENTER, ""),
            # Give the right name this time.
            (NamesReviewer.ASK_FOR_NAME, student_names[2]),
            # Confirm.
            (NamesReviewer.CORRECT_Y_N, ""),
            "II.2) DOC 3",
            (NamesReviewer.PRESS_ENTER, ""),
            # Keep current name.
            (NamesReviewer.ASK_FOR_NAME, "ok"),
            # Confirm.
            (NamesReviewer.CORRECT_Y_N, ""),
        ],
    )

    patched_conflict_solver.run()
    assert sorted(patched_conflict_solver.data) == [1, 2, 3, 4]

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"
