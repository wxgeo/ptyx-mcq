import shutil
from pathlib import Path

import pytest

from ptyx_mcq.scan import scan
from ptyx_mcq.scan.data_gestion.conflict_handling.data_check.cl_fix import (
    ClNamesReviewer as NamesReviewer,
)
from tests.test_conflict_solver import DATA_DIR


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

    def same_file(path: Path, path2: Path) -> bool:
        return path.read_text(encoding="utf8") == path2.read_text(encoding="utf8")

    assert same_file(copy / ".scan/scores.csv", origin / "reference_scores.csv")
    assert same_file(copy / ".scan/infos.csv", origin / "reference_infos.csv")


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
