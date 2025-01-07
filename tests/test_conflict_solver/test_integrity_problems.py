import shutil
from pathlib import Path

import pytest

from ptyx_mcq.scan import scan
from ptyx_mcq.scan.data import ScanData
from ptyx_mcq.scan.data.conflict_gestion.data_check.cl_fix import (
    ClNamesReviewer as NamesReviewer,
)
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    PageNum,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    real2apparent,
)
from tests.test_conflict_solver import ASSETS_DIR


def fail_on_input(text=""):
    assert False, f"Unexpected input request: {text!r}"


def test_no_conflict(monkeypatch, patched_conflict_solver):
    """No interaction should occur if there is no conflict."""
    monkeypatch.setattr("builtins.input", fail_on_input)
    patched_conflict_solver.run()
    docs = list(patched_conflict_solver.scan_data.index)
    assert docs == [3, 4, 17, 70], docs
    for doc in patched_conflict_solver.scan_data:
        # No conflict: all pictures are used.
        assert doc.pictures == doc.used_pictures


def test_blank_page_inserted(tmp_path):
    """Test what happens when a blank page (or any unrelated paper) has been scanned by error.

    This page should be ignored, but a warning should be raised.
    """
    origin = ASSETS_DIR / "blank-page-test"
    copy = tmp_path / "blank-page-test"
    shutil.copytree(origin, copy)
    scan(copy)
    print(copy / ".scan/scores.csv")
    print(origin / "reference_scores.csv")

    def assert_same_file(path: Path, path2: Path) -> None:
        assert path.read_text(encoding="utf8") == path2.read_text(encoding="utf8"), (path, path2)

    assert_same_file(copy / "out/scores.csv", origin / "reference_scores.csv")
    assert_same_file(output := copy / "out/infos.csv", expected := origin / "reference_infos.csv")


# todo
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
    origin = ASSETS_DIR / "unfilled-doc-test"
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


# todo
def test_identical_duplicate_documents(no_display, tmp_path, custom_input):
    custom_input.set_scenario([])
    origin = ASSETS_DIR / "duplicate-files"
    copy = tmp_path / "duplicate-files"
    shutil.copytree(origin, copy)
    (copy / "scan/flat-scan-conflict.pdf").unlink()
    shutil.copy(copy / "scan/flat-scan.pdf", copy / "scan/flat-scan-bis.pdf")
    mcq_parser = scan(copy)
    target = pytest.approx({"John": 8.83333333, "Edward": 9.45595238})
    assert mcq_parser.scores_manager.scores == target
    assert mcq_parser.scores_manager.results == target


def test_bug_inconsistent_checkboxes_state(tmp_path):
    Q = OriginalQuestionNumber
    A = OriginalAnswerNumber
    origin = ASSETS_DIR / "duplicate-files"
    copy = tmp_path / "duplicate-files"
    shutil.copytree(origin, copy)
    scan_data = ScanData(config_path=tmp_path / "duplicate-files")
    scan_data.run()
    pic1, pic2 = scan_data.index[DocumentId(44)].pages[PageNum(3)].pictures
    assert pic1.questions[Q(17)].answers[A(5)].state == pic2.questions[Q(17)].answers[A(5)].state, (
        real2apparent(Q(17), A(5), scan_data.config, DocumentId(44)),
        pic1.short_path,
        pic2.short_path,
        pic1.path,
        pic2.path,
    )
    assert pic1.as_hashable_tuple() == pic2.as_hashable_tuple()


def test_different_duplicate_documents_keep_first(no_display, tmp_path, custom_input):
    custom_input.set_scenario(
        [
            "Message indicating that a duplicate has been found.",
            (NamesReviewer.PRESS_ENTER, ""),
            "Keep the first version",
            ("Answer: ", "1"),
        ]
    )
    origin = ASSETS_DIR / "duplicate-files"
    copy = tmp_path / "duplicate-files"
    shutil.copytree(origin, copy)
    mcq_parser = scan(copy)
    assert len(mcq_parser.scan_data.index[DocumentId(45)].pages[PageNum(1)].pictures) == 2
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
    origin = ASSETS_DIR / "duplicate-files"
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
