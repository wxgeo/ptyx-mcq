import shutil
import subprocess
from pathlib import Path

import pytest
from numpy import ndarray, array

from ptyx_mcq.scan.data_gestion.conflict_handling import ConflictSolver, NamesReviewer
from ptyx_mcq.scan.data_gestion.conflict_handling.data_check import Action
from ptyx_mcq.scan.data_gestion.data_handler import DataHandler
from ptyx_mcq.scan.data_gestion.document_data import DocumentData
from ptyx_mcq.tools.config_parser import DocumentId, StudentName
from ptyx_mcq.cli import scan

from .toolbox import TEST_DIR

# NamesReviewer.CORRECT_Y_N = "Is it correct? (Y/n)"
# NamesReviewer.ASK_FOR_NAME = "Student name or ID (or / to skip this document):"
# NamesReviewer.PRESS_ENTER = "-- Press ENTER --"

STUDENT_NAMES = ["Robert Le Hardi", "Jules Le Preux", "Edouard Le Couard", "Jules de chez Smith"]

DATA_DIR = TEST_DIR / "data/test-conflict-solver"


def fail_on_input(text=""):
    assert False, f"Unexpected input request: {text!r}"


@pytest.fixture
def no_display(monkeypatch):
    # noinspection PyUnusedLocal
    def display(self, wait: bool = True) -> subprocess.CompletedProcess | subprocess.Popen:
        print("\033[3;37m[Image displayed here...]\033[0m")
        if wait:
            return subprocess.run(["sleep", "0"])
        else:
            return subprocess.Popen(["sleep", "0"], stdin=subprocess.DEVNULL)

    monkeypatch.setattr("ptyx_mcq.scan.image_viewer.ImageViewer.display", display)


@pytest.fixture
def patched_conflict_solver(monkeypatch, tmp_path, no_display):
    shutil.copytree(DATA_DIR / "no-conflict", tmp_path / "no-conflict")
    data_storage = DataHandler(config_path=tmp_path / "no-conflict")
    conflict_solver = ConflictSolver(data_storage)
    conflict_solver.data_storage.reload()

    # noinspection PyUnusedLocal
    def get_matrix(self, doc_id: int, page: int) -> ndarray:
        return array([[0, 0], [0, 0]])  # Array must be at least 2x2 for tests to pass.

    monkeypatch.setattr("ptyx_mcq.scan.data_gestion.data_handler.DataHandler.get_matrix", get_matrix)
    return conflict_solver


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
    # Create duplicate name conflict
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
            # "II.1) DOC 2",
            # (NamesReviewer.PRESS_ENTER, ""),
            # # Give the right name this time.
            # (NamesReviewer.ASK_FOR_NAME, student_names[2]),
            # # Confirm.
            # (NamesReviewer.CORRECT_Y_N, ""),
            "II.2) DOC 3",
            (NamesReviewer.PRESS_ENTER, ""),
            # Keep current name.
            (NamesReviewer.ASK_FOR_NAME, student_names[2]),
            # Confirm.
            (NamesReviewer.CORRECT_Y_N, ""),
        ],
    )

    patched_conflict_solver.run()
    assert sorted(patched_conflict_solver.data) == [1, 2, 3, 4]

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_blank_page_inserted(tmp_path):
    """Test what happens when a blank page (or any unrelated paper) has been scanned by error.

    This page should be ignored, but a warning should be raised.
    """
    origin = DATA_DIR / "blank-page-test"
    copy = tmp_path / "blank-page-test"
    shutil.copytree(origin, copy)
    scan(copy)
    print(copy / ".scan/scores.csv")
    print(origin / "reference_scores.csv")
    assert (copy / ".scan/scores.csv").read_text(encoding="utf8") == (
        origin / "reference_scores.csv"
    ).read_text(encoding="utf8")
    assert (copy / ".scan/infos.csv").read_text(encoding="utf8") == (
        origin / "reference_infos.csv"
    ).read_text(encoding="utf8")


def test_empty_document(no_display, tmp_path, custom_input):
    """Simulate an empty document (i.e. a valid unfilled document) being inserted by mistake."""

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successives expected questions and their corresponding answers.
    custom_input.set_scenario(
        [
            "Empty document: no name found.",
            (NamesReviewer.PRESS_ENTER, ""),
            "This is an empty document: use '/' to skip it.",
            (NamesReviewer.ASK_FOR_NAME, "/"),
        ],
    )
    origin = DATA_DIR / "unfilled-doc-test"
    copy = tmp_path / "unfilled-doc-test"
    shutil.copytree(origin, copy)
    mcq_parser = scan(copy)
    assert mcq_parser.scores_manager.scores == {"John": 8.833333333333332, "Edward": 9.455952380952379}
    assert mcq_parser.scores_manager.results == {"John": 8.833333333333332, "Edward": 9.455952380952379}
    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"
    custom_input.set_scenario([])
    mcq_parser = scan(copy)
    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"
    # No change in results of course.
    target = pytest.approx({"John": 8.83333333, "Edward": 9.45595238})
    assert mcq_parser.scores_manager.scores == target
    assert mcq_parser.scores_manager.results == target


def test_identical_duplicate_documents(no_display, tmp_path, custom_input):
    custom_input.set_scenario([])
    origin = DATA_DIR / "duplicate-files"
    copy = tmp_path / "duplicate-files"
    shutil.copytree(origin, copy)
    (copy / "scan/flat-scan-conflict.pdf").unlink()
    shutil.copy(copy / "scan/flat-scan.pdf", copy / "scan/flat-scan-bis.pdf")
    mcq_parser = scan(copy)
    target = pytest.approx({"John": 8.83333333, "Edward": 9.45595238})
    assert mcq_parser.scores_manager.scores == target
    assert mcq_parser.scores_manager.results == target


def test_different_duplicate_documents_keep_first(no_display, tmp_path, custom_input):
    custom_input.set_scenario(
        [
            "Message indicating that a duplicate has been found.",
            (NamesReviewer.PRESS_ENTER, ""),
            "Keep the first version",
            ("Answer: ", "1"),
        ]
    )
    origin = DATA_DIR / "duplicate-files"
    copy = tmp_path / "duplicate-files"
    shutil.copytree(origin, copy)
    mcq_parser = scan(copy)
    assert (
        Path(mcq_parser.data[45].pages[1].pic_path).parent
        != Path(mcq_parser.data[44].pages[1].pic_path).parent
    )
    # Score for John changed (8.83 -> 8.63).
    target = pytest.approx({"John": 8.63333333, "Edward": 9.45595238})
    assert mcq_parser.scores_manager.scores == target
    assert mcq_parser.scores_manager.results == target


def test_different_duplicate_documents_keep_second(no_display, tmp_path, custom_input):
    custom_input.set_scenario(
        [
            "Message indicating that a duplicate has been found.",
            (NamesReviewer.PRESS_ENTER, ""),
            "Keep the seconde version",
            ("Answer: ", "2"),
        ]
    )
    origin = DATA_DIR / "duplicate-files"
    copy = tmp_path / "duplicate-files"
    shutil.copytree(origin, copy)
    mcq_parser = scan(copy)
    assert (
        Path(mcq_parser.data[45].pages[1].pic_path).parent
        == Path(mcq_parser.data[44].pages[1].pic_path).parent
    )
    # Score for John was left unchanged.
    target = pytest.approx({"John": 8.83333333, "Edward": 9.45595238})
    assert mcq_parser.scores_manager.scores == target
    assert mcq_parser.scores_manager.results == target
