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

TEST_DIR = Path(__file__).parent


CORRECT_Y_N = "Is it correct ? (Y/n)"
ASK_FOR_STUDENT_NAME = "Student name or ID (or / to skip this document):"
PRESS_ENTER = "-- Press enter --"

STUDENT_NAMES = ["Robert Le Hardi", "Jules Le Preux", "Edouard Le Couard", "Jules de chez Smith"]


def fail_on_input(text=""):
    assert False, f"Unexpected input request: {text!r}"


@pytest.fixture
def conflict_solver(tmp_path, monkeypatch):
    shutil.copytree(TEST_DIR / "test-conflict-solver-data/no-conflict", tmp_path / "no-conflict")
    data_storage = DataHandler(config_path=tmp_path / "no-conflict")

    # noinspection PyUnusedLocal
    def get_matrix(self, doc_id: int, page: int) -> ndarray:
        return array([[]])

    # noinspection PyUnusedLocal
    def display(self, wait: bool = True) -> subprocess.CompletedProcess | subprocess.Popen:
        if wait:
            return subprocess.run(["sleep", "0"])
        else:
            return subprocess.Popen(["sleep", "0"], stdin=subprocess.DEVNULL)

    monkeypatch.setattr("ptyx_mcq.scan.data_handler.DataHandler.get_matrix", get_matrix)
    monkeypatch.setattr("ptyx_mcq.scan.visual_debugging.ArrayViewer.display", display)
    conflict_solver = ConflictSolver(data_storage)
    conflict_solver.data_storage.reload()
    return conflict_solver


def test_no_conflict(monkeypatch, conflict_solver):
    """No interaction should occur if there is no conflict."""
    monkeypatch.setattr("builtins.input", fail_on_input)
    conflict_solver.resolve_conflicts()
    data = conflict_solver.data
    assert sorted(data) == [1, 2, 3, 4], data


class CustomInput:
    def __init__(self, scenario: list[tuple[str, str]]):
        self.scenario = scenario
        self.index = 0

    def __call__(self, text: str = "") -> str:
        while isinstance(comment := self.scenario[self.index], str):
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


def set_custom_input(monkeypatch, scenario):
    monkeypatch.setattr("builtins.input", custom_input := CustomInput(scenario))
    return custom_input


def test_missing_name(monkeypatch, conflict_solver) -> None:
    """Test interactions if a name is missing."""
    doc_data: DocumentData = conflict_solver.data[DocumentId(1)]
    student_name = doc_data.name
    assert student_name == "Robert Le Hardi"
    doc_data.name = StudentName("")

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    custom_input = set_custom_input(
        monkeypatch=monkeypatch,
        scenario=[
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

    conflict_solver.resolve_conflicts()
    assert conflict_solver.data[DocumentId(1)].name == student_name

    # There should be no remaining question.
    assert custom_input.is_empty(), custom_input.remaining()

    assert doc_data is conflict_solver.data[DocumentId(1)]
    doc_data.name = StudentName("")
    custom_input = set_custom_input(monkeypatch=monkeypatch, scenario=[])

    conflict_solver.resolve_conflicts()
    assert conflict_solver.data[DocumentId(1)].name == student_name

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_missing_name2(monkeypatch, conflict_solver) -> None:
    """Test interactions if a name is missing."""
    doc_data: DocumentData = conflict_solver.data[DocumentId(1)]
    student_name = doc_data.name
    assert student_name == "Robert Le Hardi"
    doc_data.name = StudentName("")

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successive expected questions and their corresponding answers.
    custom_input = set_custom_input(
        monkeypatch=monkeypatch,
        scenario=[
            (PRESS_ENTER, ""),
            (ASK_FOR_STUDENT_NAME, student_name),
            (CORRECT_Y_N, "Y"),
        ],
    )

    conflict_solver.resolve_conflicts()
    assert conflict_solver.data[DocumentId(1)].name == student_name

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_missing_name_skip_doc(monkeypatch, conflict_solver) -> None:
    """Skip a document."""
    doc_data: DocumentData = conflict_solver.data[DocumentId(1)]
    student_name = doc_data.name
    assert student_name == "Robert Le Hardi"
    doc_data.name = StudentName("")

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successives expected questions and their corresponding answers.
    custom_input = set_custom_input(
        monkeypatch=monkeypatch,
        scenario=[
            (PRESS_ENTER, ""),
            (ASK_FOR_STUDENT_NAME, "/"),
        ],
    )

    conflict_solver.resolve_conflicts()
    assert DocumentId(1) not in conflict_solver.data

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


def test_duplicate_name(monkeypatch, conflict_solver):
    """Skip a document."""
    student_names = {i: conflict_solver.data[DocumentId(i)].name for i in (1, 2, 3, 4)}
    assert list(student_names.values()) == STUDENT_NAMES
    # Create duplicate name conflict
    conflict_solver.data[DocumentId(2)].name = student_names[1]

    # Test a scenario, simulating questions for the user in the terminal and the user's answers.
    # The variable `scenario` is the list of the successives expected questions and their corresponding answers.
    custom_input = set_custom_input(
        monkeypatch=monkeypatch,
        scenario=[
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

    conflict_solver.resolve_conflicts()
    assert sorted(conflict_solver.data) == [1, 2, 3, 4]

    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"


# def test_blank_page_inserted(tmp_path):
#     """Test what happens when a blank page (or any unrelated paper) has been scanned by error.
#
#     This page should be ignored, but a warning should be raised.
#     """
#     copy = tmp_path / "blank-page-test"
#     origin = TEST_DIR / "blank-page-test"
#     shutil.copytree(origin, copy)
#     scan(copy)
#     assert (copy / ".scan/scores.csv").read_text(encoding="utf8") == (
#         origin / ".scan/patched_scores.csv"
#     ).read_text(encoding="utf8")
