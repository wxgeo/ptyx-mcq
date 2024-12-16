"""
Analyze the data extracted from the input pdf.

This means:
- detecting checkboxes
- evaluating checkboxes state
- retrieving student name and identifier
"""
import concurrent.futures
import multiprocessing
from functools import partial
from pathlib import Path

from numpy import ndarray, concatenate
from ptyx.shell import ANSI_CYAN, ANSI_RESET, ANSI_GREEN, ANSI_YELLOW

from ptyx_mcq.scan.data.structures import CbxState
from ptyx_mcq.scan.picture_analyze.square_detection import test_square_color
from ptyx_mcq.scan.picture_analyze.types_declaration import Line, Col
from ptyx_mcq.tools.config_parser import DocumentId, CbxRef
from ptyx_mcq.tools.pic import save_webp


CheckboxAnalyzeResult = dict[CbxRef, CbxState]
CheckboxesPositions = dict[CbxRef, tuple[Line, Col]]


class InvalidFormat(RuntimeError):
    """Raised when a file has an invalid format and cannot be decoded."""


def _get_max_blackness(blackness: list[dict[CbxRef, float]]) -> float:
    return max(max(pic_blackness.values(), default=0) for pic_blackness in blackness)


def _get_average_blackness(blackness: list[dict[CbxRef, float]]) -> float:
    total = 0.0
    count = 0
    for pic_blackness in blackness:
        for cbx_blackness in pic_blackness.values():
            total += cbx_blackness
            count += 1
    return total / count if count != 0 else 0


def analyze_checkboxes(
    all_checkboxes: list[dict[CbxRef, ndarray]],
) -> list[dict[CbxRef, CbxState]]:
    """
    Evaluate each checkbox, and estimate if it was checked.
    """
    detection_status: list[dict[CbxRef, CbxState]] = [{} for _ in all_checkboxes]
    # Store blackness of checkboxes, to help detect false positives
    # and false negatives.
    blackness: list[dict[CbxRef, float]] = [{} for _ in all_checkboxes]
    core_blackness: list[dict[CbxRef, float]] = [{} for _ in all_checkboxes]

    for pic_checkboxes, pic_blackness, pic_core_blackness in zip(all_checkboxes, blackness, core_blackness):
        for q_a, checkbox in pic_checkboxes.items():
            # `q` and `a` are real questions and answers numbers, that is,
            # questions and answers numbers before shuffling.
            # The following will be used to detect false positives or false negatives later.
            pic_blackness[q_a] = eval_checkbox_color(checkbox, margin=4)
            pic_core_blackness[q_a] = eval_checkbox_color(checkbox, margin=7)
            # `q0` and `a0` keep track of apparent question and answers numbers,
            # which will be used on output to make debugging easier.

    max_blackness = _get_max_blackness(blackness)
    max_core_blackness = _get_max_blackness(core_blackness)

    # Various metrics used to compare the blackness of a checkbox with the other ones.
    floor = max(0.2 * max_blackness, max_blackness - 0.4)
    upper_floor = max(0.2 * max_blackness, max_blackness - 0.3)
    core_floor = max(0.2 * max_core_blackness, max_core_blackness - 0.4)
    upper_core_floor = max(0.2 * max_core_blackness, max_core_blackness - 0.3)
    # Add 0.03 to 1.5*mean, in case mean is almost 0.
    ceil = 1.5 * _get_average_blackness(blackness) + 0.02
    core_ceil = 1.2 * _get_average_blackness(core_blackness) + 0.01

    # First pass
    # Each checkbox is evaluated (almost) individually.
    # (Only the maximal checkbox blackness value is considered too).
    for pic_checkboxes, pic_blackness, pic_core_blackness, pic_detection_status in zip(
        all_checkboxes, blackness, core_blackness, detection_status
    ):
        for q_a, checkbox in pic_checkboxes.items():
            test_square = partial(test_square_color, m=checkbox, i=0, j=0, size=checkbox.shape[0], margin=5)

            if (
                test_square(proportion=0.2, gray_level=0.65)
                # ~ test_square_color(m, i + 3, j + 3, cell_size - 7, proportion=0.4, gray_level=0.75) or
                # ~ test_square_color(m, i + 3, j + 3, cell_size - 7, proportion=0.45, gray_level=0.8) or
                or test_square(proportion=0.4, gray_level=0.90)
                or test_square(proportion=0.6, gray_level=0.95)
            ):
                if test_square(proportion=0.4, gray_level=0.9):
                    pic_detection_status[q_a] = CbxState.CHECKED
                else:
                    pic_detection_status[q_a] = CbxState.PROBABLY_CHECKED
            else:
                if test_square(proportion=0.2, gray_level=0.95) and pic_blackness[q_a] > upper_floor:
                    pic_detection_status[q_a] = CbxState.PROBABLY_UNCHECKED
                else:
                    pic_detection_status[q_a] = CbxState.UNCHECKED

    # Second pass :
    # We will test now for false negatives and false positives, by comparing each checkbox
    # with the other ones.
    # The assumption is that a student will likely use a consistent approach to marking the checkboxes.

    for pic_checkboxes, pic_blackness, pic_core_blackness, pic_detection_status in zip(
        all_checkboxes, blackness, core_blackness, detection_status
    ):
        for q_a in pic_blackness:
            # First, try to detect false negatives.
            # If a checkbox considered unchecked is notably darker than the others,
            # it is probably checked after all (and if not, it will most probably be caught
            # with false positives in next section).
            if not pic_detection_status[q_a].seems_checked and (
                pic_blackness[q_a] > ceil or pic_core_blackness[q_a] > core_ceil
            ):
                print("False negative detected", q_a)
                # This is probably a false negative, but we'd better verify manually.
                pic_detection_status[q_a] = CbxState.PROBABLY_CHECKED

            # If a checkbox is tested as checked, but is much lighter than the darker one,
            # it is very probably a false positive.
            if pic_detection_status[q_a].seems_checked and (
                pic_blackness[q_a] < upper_floor or pic_core_blackness[q_a] < upper_core_floor
            ):
                if pic_blackness[q_a] < floor or pic_core_blackness[q_a] < core_floor:
                    print("False positive detected", q_a, pic_blackness[q_a], max_blackness)
                    # This is probably a false positive, but we'd better verify manually.
                    pic_detection_status[q_a] = CbxState.PROBABLY_UNCHECKED
                else:
                    # Probably note a false positive, but we should verify.
                    pic_detection_status[q_a] = CbxState.PROBABLY_CHECKED

    return detection_status


def eval_checkbox_color(checkbox: ndarray, margin: int = 0) -> float:
    """Return an indicator of blackness, which is a float in range (0, 1).
    The bigger the float returned, the darker the square.

    This indicator is useful to compare several squares, and find the blacker one.
    Note that the core of the square is considered the more important part to assert
    blackness.
    """
    height, width = checkbox.shape
    assert width == height, (width, height)
    if width <= 2 * margin:
        raise ValueError("Square too small for current margins !")
    # Warning: pixels outside the sheet shouldn't be considered black !
    # Since we're doing a sum, 0 should represent white and 1 black,
    # so as if a part of the square is outside the sheet, it is considered
    # white, not black ! This explains the `1 - m[...]` below.
    square = 1 - checkbox[margin : width - margin, margin : width - margin]
    return square.sum() / (width - margin) ** 2


# =====================================
# TODO: remove or update
# =====================================


class OldCheckboxesDataAnalyzer:
    """Analyze all data checkboxes."""

    # TODO: Remove old code???

    # ==========
    #  OLD CODE
    # ==========

    # -------------------------
    #    Checkboxes analyze
    # =========================

    def _collect_untreated_checkboxes(self) -> list[DocumentId]:
        """Return documents whose checkboxes have not been already analyzed during a previous scan."""
        return [
            doc_id
            for doc_id, doc_data in self.data.items()
            if not all(
                len(pic_data.detection_status) == len(pic_data.positions)
                for pic_data in doc_data.pages.values()
            )
        ]

    def _analyze_document_checkboxes(self, doc_id: DocumentId) -> tuple[DocumentId, CheckboxAnalyzeResult]:
        """Mark each answer's checkbox of the document `doc_id` as checked or blank."""
        doc_data: DocumentData = self.data[doc_id]
        checkboxes = {
            key: val for page in doc_data.pages for key, val in self.get_checkboxes(doc_id, page).items()
        }
        return doc_id, analyze_checkboxes(checkboxes)

    def _save_checkbox_analyze_result(
        self, doc_id: DocumentId, detection_status: CheckboxAnalyzeResult
    ) -> None:
        """Store information concerning checked box."""
        doc_data = self.data[doc_id]
        for page, pic_data in doc_data.pages.items():
            for q, a in pic_data.positions:
                pic_data.answered.setdefault(q, set())
                status = pic_data.detection_status[(q, a)] = detection_status[(q, a)]
                if CbxState.seems_checked(status):
                    pic_data.answered[q].add(a)
            # Store results, to be able to interrupt and resume scan.
            self.data_handler.store_doc_data(str(Path(pic_data.pic_path).parent), doc_id, page)

    def _parallel_checkboxes_analyze(self, number_of_processes: int = 2, display=False):
        to_analyze = self._collect_untreated_checkboxes()
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=number_of_processes, mp_context=multiprocessing.get_context("spawn")
        ) as executor:
            # Use an iterator, to limit memory consumption.
            todo = (executor.submit(self._analyze_document_checkboxes, doc_id) for doc_id in to_analyze)
            for i, future in enumerate(concurrent.futures.as_completed(todo), start=1):
                doc_id, detection_status = future.result()
                self._save_checkbox_analyze_result(doc_id, detection_status)
                print(f"Document {i}/{len(to_analyze)} processed.", end="\r")
                if display:
                    self.display_analyze_results(doc_id)

    def _serial_checkboxes_analyse(self, display=False):
        for doc_id in self._collect_untreated_checkboxes():
            _, detection_status = self._analyze_document_checkboxes(doc_id)
            self._save_checkbox_analyze_result(doc_id, detection_status)
            if display:
                self.display_analyze_results(doc_id)
            else:
                print(f"Analyzing checkboxes of document {doc_id}...")

    def analyze_checkboxes(self, number_of_processes=1, display=False):
        """Determine whether each checkbox is checked or not, and update data accordingly."""
        if number_of_processes == 1:
            self._serial_checkboxes_analyse(display)
        else:
            self._parallel_checkboxes_analyze(number_of_processes=number_of_processes)

    # -----------------------------------------
    #     Display checkboxes analyze results
    # =========================================

    # Mainly for debugging.

    def display_analyze_results(self, doc_id: DocumentId) -> None:
        """Print the result of the checkbox analysis for document `doc_id` in terminal."""
        print(f"\n[Document {doc_id}]\n")
        for page, pic_data in self.data[doc_id].pages.items():
            print(f"\nPage {page}:")
            for q, q0 in pic_data.questions_nums_conversion.items():
                # `q0` is the apparent number of the question, as displayed on the document,
                # while `q` is the internal number of the question (attributed before shuffling).
                print(f"\n{ANSI_CYAN}• Question {q0}{ANSI_RESET} (Q{q})")
                for a, is_correct in self.config.ordering[doc_id]["answers"][q]:
                    match pic_data.detection_status[(q, a)]:
                        case CbxState.CHECKED:
                            c = "■"
                            ok = is_correct
                        case CbxState.PROBABLY_CHECKED:
                            c = "■?"
                            ok = is_correct
                        case CbxState.UNCHECKED:
                            c = "□"
                            ok = not is_correct
                        case CbxState.PROBABLY_UNCHECKED:
                            c = "□?"
                            ok = not is_correct
                        case other:
                            raise ValueError(f"Unknown detection status: {other!r}.")
                    term_color = ANSI_GREEN if ok else ANSI_YELLOW
                    print(f"  {term_color}{c} {a}  {ANSI_RESET}", end="\t")
            print()

    # ---------------------
    #   Checkboxes export
    # =====================

    # This is mainly useful to create regression tests.

    def _export_document_checkboxes(self, doc_id: DocumentId, path: Path = None, compact=False) -> None:
        """Save the checkboxes of the document `doc_id` as .webm images in a directory."""
        if path is None:
            path = self.dirs.checkboxes
        (doc_dir := path / str(doc_id)).mkdir(exist_ok=True)
        for page, pic_data in self.data[doc_id].pages.items():
            matrices: list[ndarray] = []
            index_lines: list[str] = []
            for (q, a), matrix in self.get_checkboxes(doc_id, page).items():
                detection_status = pic_data.detection_status[(q, a)]
                revision_status = pic_data.revision_status.get((q, a))
                info = f"{q}-{a}-{detection_status.value}-{'' if revision_status is None else revision_status.value}"

                if compact:
                    matrices.append(matrix)
                    index_lines.append(info)
                else:
                    webp = doc_dir / f"{info}.webp"
                    save_webp(matrix, webp)
            if compact and matrices:
                save_webp(concatenate(matrices), doc_dir / f"{page}.webp")
                with open(doc_dir / f"{page}.index", "w") as f:
                    f.write("\n".join(sorted(index_lines)) + "\n")

    def export_checkboxes(self, export_all=False, path: Path = None, compact=False) -> None:
        """Save checkboxes as .webm images in a directory.

        By default, only export the checkboxes of the documents whose at least one page
        has been manually verified. Set `export_all=True` to export all checkboxes.

        This is used to build regressions tests.
        """
        to_export: set[DocumentId] = {
            doc_id
            for doc_id, doc_data in self.data.items()
            if export_all
            or any(
                (q, a) in pic_data.revision_status
                for page, pic_data in doc_data.pages.items()
                for (q, a) in self.get_checkboxes(doc_id, page)
            )
        }
        for doc_id in to_export:
            self._export_document_checkboxes(doc_id, path=path, compact=compact)
