import shutil
import subprocess
from pathlib import Path

import pytest
from numpy import ndarray, array

from ptyx_mcq.scan.conflict_solver import ConflictSolver
from ptyx_mcq.scan.data_handler import DataHandler
from ptyx_mcq.scan.document_data import DocumentData
from ptyx_mcq.tools.config_parser import DocumentId, StudentName
from ptyx_mcq.tools.io_tools import custom_print
from ptyx_mcq.cli import scan

TEST_DIR = Path(__file__).parent


CORRECT_Y_N = "Is it correct ? (Y/n)"
ASK_FOR_STUDENT_NAME = "Student name or ID (or / to skip this document):"
PRESS_ENTER = "-- Press enter --"

STUDENT_NAMES = ["Robert Le Hardi", "Jules Le Preux", "Edouard Le Couard", "Jules de chez Smith"]


def fail_on_input(text=""):
    assert False, f"Unexpected input request: {text!r}"


@pytest.fixture
def no_display(monkeypatch):
    # noinspection PyUnusedLocal
    def display(self, wait: bool = True) -> subprocess.CompletedProcess | subprocess.Popen:
        if wait:
            return subprocess.run(["sleep", "0"])
        else:
            return subprocess.Popen(["sleep", "0"], stdin=subprocess.DEVNULL)

    monkeypatch.setattr("ptyx_mcq.scan.visual_debugging.ArrayViewer.display", display)


@pytest.fixture
def patched_conflict_solver(monkeypatch, tmp_path, no_display):
    shutil.copytree(TEST_DIR / "test-conflict-solver-data/no-conflict", tmp_path / "no-conflict")
    data_storage = DataHandler(config_path=tmp_path / "no-conflict")
    conflict_solver = ConflictSolver(data_storage)
    conflict_solver.data_storage.reload()

    # noinspection PyUnusedLocal
    def get_matrix(self, doc_id: int, page: int) -> ndarray:
        return array([[]])

    monkeypatch.setattr("ptyx_mcq.scan.data_handler.DataHandler.get_matrix", get_matrix)
    return conflict_solver


def test_no_conflict(monkeypatch, patched_conflict_solver):
    """No interaction should occur if there is no conflict."""
    monkeypatch.setattr("builtins.input", fail_on_input)
    patched_conflict_solver.resolve_conflicts()
    data = patched_conflict_solver.data
    assert sorted(data) == [1, 2, 3, 4], data


class CustomInput:
    def __init__(self):
        self.scenario: list[tuple[str, str]] = []
        self.index = 0

    def set_scenario(self, scenario: list[tuple[str, str]]):
        self.scenario = scenario
        self.index = 0

    def __call__(self, text: str = "") -> str:
        while self.index < len(self.scenario) and isinstance(comment := self.scenario[self.index], str):
            assert isinstance(comment, str)  # stupid Pycharm!
            # This is only comments.
            custom_print(comment, label="Note", color="blue", bold=False)
            self.index += 1
        print("Q:", text)
        try:
            question, answer = self.scenario[self.index]
        except IndexError:
            raise ValueError(f"Unexpected input request: {text!r}")
        assert text == question, (question, answer)
        print("A:", answer)
        self.index += 1
        return answer

    def remaining(self):
        return self.scenario[self.index :]

    def is_empty(self) -> bool:
        return self.index == len(self.scenario)


@pytest.fixture
def custom_input(monkeypatch):
    monkeypatch.setattr("builtins.input", custom_input := CustomInput())
    return custom_input


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
            (PRESS_ENTER, ""),
            # No name provided: ask again
            (ASK_FOR_STUDENT_NAME, ""),
            # Invalid student id provided: ask again
            (ASK_FOR_STUDENT_NAME, "22"),
            # Custom name: ok (this behavior may change in the future...)
            (ASK_FOR_STUDENT_NAME, "Any name"),
            # Ask for confirmation; answer "n", so ask again
            (CORRECT_Y_N, "n"),
            # Valid student id
            (ASK_FOR_STUDENT_NAME, "22205649"),
            # Ask for confirmation; answer "Y", so quit (success)
            (CORRECT_Y_N, "Y"),
        ],
    )

    patched_conflict_solver.resolve_conflicts()
    assert patched_conflict_solver.data[DocumentId(1)].name == student_name

    # There should be no remaining question.
    assert custom_input.is_empty(), custom_input.remaining()

    assert doc_data is patched_conflict_solver.data[DocumentId(1)]
    doc_data.name = StudentName("")
    custom_input.set_scenario([])

    patched_conflict_solver.resolve_conflicts()
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
            (PRESS_ENTER, ""),
            (ASK_FOR_STUDENT_NAME, student_name),
            (CORRECT_Y_N, "Y"),
        ],
    )

    patched_conflict_solver.resolve_conflicts()
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
            (PRESS_ENTER, ""),
            (ASK_FOR_STUDENT_NAME, "/"),
        ],
    )

    patched_conflict_solver.resolve_conflicts()
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
            (PRESS_ENTER, ""),
            # Give invalid student id: ask again
            (ASK_FOR_STUDENT_NAME, "0"),
            # Don't change name
            (ASK_FOR_STUDENT_NAME, ""),
            # Confirm ("yes" should be the default answer)
            (CORRECT_Y_N, ""),
            "I.1) DOC 2",
            (PRESS_ENTER, ""),
            # Create another conflict(give the student name of the doc number 3 too)
            (ASK_FOR_STUDENT_NAME, student_names[3]),
            # Confirm.
            (CORRECT_Y_N, ""),
            "II) Resolve the newly created conflict between doc 2 and doc 3.",
            "II.1) DOC 2",
            (PRESS_ENTER, ""),
            # Give the right name this time.
            (ASK_FOR_STUDENT_NAME, student_names[2]),
            # Confirm.
            (CORRECT_Y_N, ""),
            "II.2) DOC 3",
            (PRESS_ENTER, ""),
            # Keep current name.
            (ASK_FOR_STUDENT_NAME, ""),
            # Confirm.
            (CORRECT_Y_N, ""),
        ],
    )

    patched_conflict_solver.resolve_conflicts()
    assert sorted(patched_conflict_solver.data) == [1, 2, 3, 4]

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_blank_page_inserted(tmp_path):
    """Test what happens when a blank page (or any unrelated paper) has been scanned by error.

    This page should be ignored, but a warning should be raised.
    """
    origin = TEST_DIR / "blank-page-test"
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
            (PRESS_ENTER, ""),
            "This is an empty document: use '/' to skip it.",
            (ASK_FOR_STUDENT_NAME, "/"),
        ],
    )
    origin = TEST_DIR / "unfilled-doc-test"
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
    assert mcq_parser.scores_manager.scores == {"John": 8.833333333333332, "Edward": 9.455952380952379}
    assert mcq_parser.scores_manager.results == {"John": 8.833333333333332, "Edward": 9.455952380952379}
