import shutil
from pathlib import Path
from typing import Literal

import pytest

from ptyx_mcq.scan import scan
from ptyx_mcq.scan.data import ScanData
from ptyx_mcq.scan.data.conflict_gestion.data_check.cl_fix import (
    ClNamesReviewer as NamesReviewer,
)
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    PageNum,
    apparent2real,
    ApparentQuestionNumber,
    ApparentAnswerNumber,
    StudentId,
    StudentName,
)
from tests.test_scan.test_conflict_solver import ASSETS_DIR


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
        assert doc.all_pictures == doc.used_pictures


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
    assert_same_file(copy / "out/infos.csv", origin / "reference_infos.csv")


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
    target = pytest.approx(
        {("22301935", "John"): 8.833333333333332, ("22301417", "Edward"): 9.455952380952379}
    )
    assert mcq_parser.scores_manager.scores == target
    assert mcq_parser.scores_manager.results == target
    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"

    # Launch a new scan. No question should be asked this time, since previous answers have been cached.
    custom_input.set_scenario([])
    mcq_parser = scan(copy)
    # There should be no remaining question.
    assert custom_input.is_empty(), f"List of remaining questions/answers: {custom_input.remaining()}"
    # No change in results of course.
    target = pytest.approx({("22301935", "John"): 8.83333333, ("22301417", "Edward"): 9.45595238})
    assert mcq_parser.scores_manager.scores == target
    assert mcq_parser.scores_manager.results == target


def test_identical_duplicate_documents(no_display, tmp_path, custom_input):
    custom_input.set_scenario([])
    origin = ASSETS_DIR / "duplicate-files"
    copy = tmp_path / "duplicate-files"
    shutil.copytree(origin, copy)
    (copy / "scan/flat-scan-conflict.pdf").unlink()
    shutil.copy(copy / "scan/flat-scan.pdf", copy / "scan/flat-scan-bis.pdf")
    mcq_parser = scan(copy)
    target = pytest.approx({("22301935", "John"): 8.83333333, ("22301417", "Edward"): 9.45595238})
    assert mcq_parser.scores_manager.scores == target
    assert mcq_parser.scores_manager.results == target


def test_bug_inconsistent_checkboxes_state(tmp_path):
    origin = ASSETS_DIR / "duplicate-files"
    copy = tmp_path / "duplicate-files"
    shutil.copytree(origin, copy)
    scan_data = ScanData(config_path=tmp_path / "duplicate-files")
    scan_data.run()
    pic1, pic2 = scan_data.index[DocumentId(44)].pages[PageNum(3)].all_pictures
    assert pic1.as_hashable_tuple() == pic2.as_hashable_tuple()

    # This bug was caused by an error in the calibration process: rotation was not saved!
    # So, test that a rotation has been applied to align the pictures corners.
    for pic in (pic1, pic2):
        assert abs(pic.calibration_data.positions.TL[0] - pic.calibration_data.positions.TR[0]) < 1
        assert abs(pic.calibration_data.positions.TL[1] - pic.calibration_data.positions.BL[1]) < 1


def duplicate_documents_test_base(tmp_path, custom_input, chosen_version: Literal["1", "2"]):
    custom_input.set_scenario(
        [
            "Message indicating that a duplicate has been found.",
            (NamesReviewer.PRESS_ENTER, ""),
            "Keep the first version",
            ("Answer: ", chosen_version),
        ]
    )
    origin = ASSETS_DIR / "duplicate-files"
    copy = tmp_path / "duplicate-files"
    shutil.copytree(origin, copy)
    mcq_parser = scan(copy)

    # Shortcuts
    doc_id = DocumentId(44)
    page_num = PageNum(1)
    doc = mcq_parser.scan_data.index[doc_id]
    config = mcq_parser.scan_data.config

    pic1, pic2 = doc.pages[page_num].all_pictures

    if chosen_version == "1":
        chosen_pic, discarded_pic = pic1, pic2
    else:
        assert chosen_version == "2"
        chosen_pic, discarded_pic = pic2, pic1

    assert not discarded_pic.use
    assert doc.pages[page_num].pic is chosen_pic

    q, a = apparent2real(ApparentQuestionNumber(1), ApparentAnswerNumber(1), config, doc_id)
    answer = doc.questions[q].answers[a]

    # The pdf `flat-scan-conflict.pdf` has its first checkbox checked,
    # contrary to the pdf `flat-scan.pdf`.
    # The problem is, the order of the pictures seems non-deterministic (but I don't why...)
    # So, we have two cases:
    if pic1.original_pdf.name == "flat-scan-conflict.pdf":
        # pic1 is the checked version, pic2 the unchecked one.
        assert pic2.original_pdf.name == "flat-scan.pdf"
        assert pic1.questions[q].answers[a].checked
        assert pic2.questions[q].answers[a].unchecked
        checked_version_chosen = chosen_version == "1"
    else:
        # pic1 is the unchecked version, pic2 the checked one.
        assert pic1.original_pdf.name == "flat-scan.pdf"
        assert pic2.original_pdf.name == "flat-scan-conflict.pdf"
        assert pic1.questions[q].answers[a].unchecked
        assert pic2.questions[q].answers[a].checked
        checked_version_chosen = chosen_version == "2"

    assert answer.checked if checked_version_chosen else answer.unchecked
    if checked_version_chosen:
        # Score for John changed (8.83 -> 8.63).
        scores = {
            # Don't change John's score! An invalid John's score indicates a bug.
            (StudentId("22301935"), StudentName("John")): 8.63333333,
            (StudentId("22301417"), StudentName("Edward")): 9.45595238,
        }

    else:
        scores = {
            # Don't change John's score! An invalid John's score indicates a bug.
            (StudentId("22301935"), StudentName("John")): 8.83333333,
            (StudentId("22301417"), StudentName("Edward")): 9.45595238,
        }

    for student in scores:
        target = pytest.approx(scores[student])
        assert mcq_parser.scores_manager.scores[student] == target
        assert mcq_parser.scores_manager.results[student] == target


def test_different_duplicate_documents_keep_first(no_display, tmp_path, custom_input):
    duplicate_documents_test_base(
        custom_input=custom_input,
        tmp_path=tmp_path,
        chosen_version="1",
    )


def test_different_duplicate_documents_keep_second(no_display, tmp_path, custom_input):
    duplicate_documents_test_base(
        custom_input=custom_input,
        tmp_path=tmp_path,
        chosen_version="2",
    )
