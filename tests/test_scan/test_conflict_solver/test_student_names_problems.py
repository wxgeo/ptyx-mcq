from ptyx_mcq.scan.data import Document, Student
from ptyx_mcq.scan.data.conflict_gestion.data_check.cl_fix import (
    ClNamesReviewer as NamesReviewer,
)
from ptyx_mcq.scan.data.conflict_gestion.data_check.fix import Action
from ptyx_mcq.tools.config_parser import DocumentId, StudentName, StudentId

# NamesReviewer.CORRECT_Y_N = "Is it correct? (Y/n)"
# NamesReviewer.ASK_FOR_NAME = "Student name or ID (or / to skip this document):"
# NamesReviewer.PRESS_ENTER = "-- Press ENTER --"

# STUDENT_NAMES = ["Robert Le Hardi", "Jules Le Preux", "Edouard Le Couard", "Jules de chez Smith"]

STUDENTS: dict[DocumentId, Student] = {
    DocumentId(3): Student(id=StudentId("22405328"), name=StudentName("Robert Le Hardy")),
    DocumentId(4): Student(id=StudentId("22401629"), name=StudentName("Jean Sander")),
    DocumentId(17): Student(id=StudentId("22402456"), name=StudentName("John Smith")),
    DocumentId(70): Student(id=StudentId("22403856"), name=StudentName("Martin McGill")),
}


def test_missing_name(patched_conflict_solver, custom_input) -> None:
    """Test interactions if a name is missing."""
    doc_id = DocumentId(17)
    doc: Document = patched_conflict_solver.scan_data.index[doc_id]
    student_name = doc.student_name
    assert student_name == "John Smith"
    doc.student = Student(name=StudentName(""), id=StudentId(""))

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
            (NamesReviewer.ASK_FOR_NAME, "Martin McGill"),
            # Ask for confirmation; answer "n", so ask again.
            (NamesReviewer.CORRECT_Y_N, "n"),
            # Valid student id
            (NamesReviewer.ASK_FOR_NAME, "22402456"),
            # Ask for confirmation; answer "Y", so quit (success)
            (NamesReviewer.CORRECT_Y_N, "Y"),
        ],
    )

    patched_conflict_solver.run()

    assert patched_conflict_solver.scan_data.index[doc_id].student_name == student_name

    # There should be no remaining question.
    assert custom_input.is_empty(), custom_input.remaining()

    assert doc is patched_conflict_solver.scan_data.index[doc_id]

    # Test that student name is memorized now.
    # doc.student.name = StudentName("")
    custom_input.set_scenario([])

    patched_conflict_solver.run()
    assert patched_conflict_solver.scan_data.index[doc_id].student_name == student_name

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_missing_name2(patched_conflict_solver, custom_input) -> None:
    """Test interactions if a name is missing."""
    doc_id = DocumentId(17)
    doc: Document = patched_conflict_solver.scan_data.index[doc_id]
    student_name = doc.student_name
    assert student_name == "John Smith"
    doc.student = Student(name=StudentName(""), id=StudentId(""))

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
    assert patched_conflict_solver.scan_data.index[doc_id].student_name == student_name

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_several_missing_names(patched_conflict_solver, custom_input) -> None:
    """Test interaction if several names are missing.

    In particular, several missing names should not be detected as duplicates!
    """
    index = patched_conflict_solver.scan_data.index

    backup_names: dict[int, StudentName] = {}

    for doc_id in index:
        assert index[doc_id].student_name != StudentName("")
        backup_names[doc_id] = index[doc_id].student_name
        index[doc_id].student = Student(name=StudentName(""), id=StudentId(""))

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, backup_names[3]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, backup_names[4]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, backup_names[17]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, backup_names[70]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
        ],
    )

    patched_conflict_solver.run()
    for doc_id in index:
        assert patched_conflict_solver.scan_data.index[doc_id].student_name == backup_names[doc_id]

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_missing_names_navigation(patched_conflict_solver, custom_input) -> None:
    """Test interaction if several names are missing.

    In particular, several missing names should not be detected as duplicates!
    """
    index = patched_conflict_solver.scan_data.index

    backup_names: dict[int, StudentName] = {}

    for doc_id in index:
        assert index[doc_id].student_name != StudentName("")
        backup_names[doc_id] = index[doc_id].student_name
        index[doc_id].student = Student(name=StudentName(""), id=StudentId(""))

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            "DOC3 - WRONG NAME",
            (NamesReviewer.PRESS_ENTER, ""),
            # set (wrong) 1st document name, then automatically go to the next one.
            (NamesReviewer.ASK_FOR_NAME, backup_names[17]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            # ----------------
            "DOC4 - BACK TO DOC3",
            (NamesReviewer.PRESS_ENTER, ""),
            # back to 1st document
            (NamesReviewer.ASK_FOR_NAME, Action.BACK),
            # ----------------
            "DOC3 - RIGHT NAME",
            (NamesReviewer.PRESS_ENTER, ""),
            # set 1st document name, automatically go to 2nd
            (NamesReviewer.ASK_FOR_NAME, backup_names[3]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            # ----------------
            "DOC4 - WRONG NAME",
            (NamesReviewer.PRESS_ENTER, ""),
            # set (wrong) 2nd document name, then automatically go to the next document.
            (NamesReviewer.ASK_FOR_NAME, backup_names[70]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            # ----------------
            "DOC17 - RIGHT NAME",
            (NamesReviewer.PRESS_ENTER, ""),
            # set 3rd document name, then automatically go to the next document.
            (NamesReviewer.ASK_FOR_NAME, backup_names[17]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            # ----------------
            "DOC70 - BACK TO DOC17",
            (NamesReviewer.PRESS_ENTER, ""),
            # back to 3rd document
            (NamesReviewer.ASK_FOR_NAME, Action.BACK),
            # ----------------
            "DOC17 - BACK TO DOC4",
            (NamesReviewer.PRESS_ENTER, ""),
            # back to 2nd document
            (NamesReviewer.ASK_FOR_NAME, Action.BACK),
            # ----------------
            "DOC4 - RIGHT NAME",
            (NamesReviewer.PRESS_ENTER, ""),
            # set 2nd document name, automatically go to 3rd
            (NamesReviewer.ASK_FOR_NAME, backup_names[4]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            # ----------------
            "DOC17 - GO TO DOC70",
            (NamesReviewer.PRESS_ENTER, ""),
            # go directly to 4th document
            (NamesReviewer.ASK_FOR_NAME, Action.NEXT),
            # ----------------
            "DOC70 - RIGHT NAME",
            (NamesReviewer.PRESS_ENTER, ""),
            # set 4th document name
            (NamesReviewer.ASK_FOR_NAME, backup_names[70]),
            (NamesReviewer.CORRECT_Y_N, "Y"),
        ],
    )

    patched_conflict_solver.run()
    for doc_id in index:
        assert patched_conflict_solver.scan_data.index[doc_id].student_name == backup_names[doc_id]

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_missing_names_autocomplete(patched_conflict_solver, custom_input) -> None:
    """Test name suggestion."""
    index = patched_conflict_solver.scan_data.index

    for doc_id in STUDENTS:
        assert index[doc_id].student == STUDENTS[doc_id]
        assert index[doc_id].student_name == STUDENTS[doc_id].name
        assert index[doc_id].student_id == STUDENTS[doc_id].id
        # Clear all student information.
        index[doc_id].student = Student(name=StudentName(""), id=StudentId(""))
        assert index[doc_id].student_name == ""
        assert index[doc_id].student_id == ""

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, "Rob"),
            (NamesReviewer.ASK_FOR_NAME, "ok"),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, "224016"),
            (NamesReviewer.ASK_FOR_NAME, "OK"),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, "Smi"),
            (NamesReviewer.ASK_FOR_NAME, "OK"),
            (NamesReviewer.CORRECT_Y_N, "Y"),
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, "Gill"),
            (NamesReviewer.ASK_FOR_NAME, "Ok"),
            (NamesReviewer.CORRECT_Y_N, "Y"),
        ],
    )

    patched_conflict_solver.run()

    for doc_id in STUDENTS:
        assert index[doc_id].student == STUDENTS[doc_id]
        assert index[doc_id].student_name == STUDENTS[doc_id].name
        assert index[doc_id].student_id == STUDENTS[doc_id].id

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_missing_name_skip_doc(patched_conflict_solver, custom_input) -> None:
    """Skip a document using '/' as student name."""
    doc_id = DocumentId(3)
    doc: Document = patched_conflict_solver.scan_data.index[doc_id]
    student_name = doc.student_name
    assert student_name == "Robert Le Hardy"
    doc.student = Student(name=StudentName(""), id=StudentId(""))

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successives expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            (NamesReviewer.PRESS_ENTER, ""),
            (NamesReviewer.ASK_FOR_NAME, "/"),
        ],
    )

    patched_conflict_solver.run()
    assert doc_id not in patched_conflict_solver.scan_data.used_docs

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_duplicate_name(patched_conflict_solver, custom_input):
    """Skip a document."""
    docs = {doc.doc_id: doc for doc in patched_conflict_solver.scan_data}
    assert [doc.student_name for doc in docs.values()] == [student.name for student in STUDENTS.values()]

    # Create duplicate name conflict: give the same name to documents 3 and 4.
    patched_conflict_solver.scan_data.index[DocumentId(4)].student = docs[DocumentId(3)].student

    assert [doc.student_name for doc in docs.values()] != [student.name for student in STUDENTS.values()]

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successives expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            "I) Resolve the conflict between doc 3 and doc 4",
            "I.1) DOC 3",
            (NamesReviewer.PRESS_ENTER, ""),
            # Give invalid student id: ask again
            (NamesReviewer.ASK_FOR_NAME, "0"),
            # Don't change name
            (NamesReviewer.ASK_FOR_NAME, Action.NEXT),
            # Confirm ("yes" should be the default answer)
            # (NamesReviewer.CORRECT_Y_N, ""),
            "I.1) DOC 4",
            (NamesReviewer.PRESS_ENTER, ""),
            # Induce now another conflict by giving to the document 4 the student name of the document 17.
            (NamesReviewer.ASK_FOR_NAME, STUDENTS[DocumentId(17)].name),
            # Confirm.
            (NamesReviewer.CORRECT_Y_N, ""),
            "II) Resolve the new conflict between doc 4 and doc 17.",
            "II.1) DOC 4 (once again!)",
            (NamesReviewer.PRESS_ENTER, ""),
            # Give the right name this time.
            (NamesReviewer.ASK_FOR_NAME, STUDENTS[DocumentId(4)].name),
            # Confirm.
            (NamesReviewer.CORRECT_Y_N, ""),
            "II.2) DOC 17",
            (NamesReviewer.PRESS_ENTER, ""),
            # Keep current name.
            (NamesReviewer.ASK_FOR_NAME, "ok"),
            # Confirm.
            (NamesReviewer.CORRECT_Y_N, ""),
        ],
    )

    patched_conflict_solver.run()
    assert [doc.student_name for doc in docs.values()] == [student.name for student in STUDENTS.values()]

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"
