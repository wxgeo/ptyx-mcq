"""
Analyze the data extracted from the input pdf.

This means:
- detecting checkboxes
- evaluating checkboxes state
- retrieving student name and identifiant
"""
import concurrent.futures
import multiprocessing
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from numpy import ndarray, concatenate
from ptyx.shell import ANSI_CYAN, ANSI_RESET, ANSI_GREEN, ANSI_YELLOW


from ptyx_mcq.scan.data.structures import DetectionStatus, DocumentData, ReviewData, Student
from ptyx_mcq.scan.picture_analyze.checkbox_analyzer import eval_checkbox_color
from ptyx_mcq.scan.picture_analyze.square_detection import adjust_checkbox, test_square_color
from ptyx_mcq.scan.picture_analyze.types_declaration import Line, Col
from ptyx_mcq.tools.config_parser import (
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    Page,
    DocumentId,
    CbxRef,
)
from ptyx_mcq.tools.pic import save_webp

if TYPE_CHECKING:
    from ptyx_mcq.scan.data.main_manager import DataHandler


CheckboxAnalyzeResult = dict[CbxRef, DetectionStatus]
CheckboxesPositions = dict[CbxRef, tuple[Line, Col]]


class InvalidFormat(RuntimeError):
    """Raised when a file has an invalid format and cannot be decoded."""


class CheckboxesDataAnalyzer:
    """Analyze all data checkboxes."""

    def __init__(self, data_handler: "DataHandler"):
        self.data_handler: "DataHandler" = data_handler
        self._checkboxes_state: dict[DocumentId, dict[Path, dict[CbxRef, DetectionStatus]]] | None = None

    @property
    def dirs(self):
        return self.data_handler.dirs

    @property
    def data(self):
        return self.data_handler.data

    @property
    def pdf_data(self):
        return self.data_handler.input_pdf.data

    @property
    def config(self):
        return self.data_handler.config

    def get_checkboxes_positions(self, pic_path: Path) -> CheckboxesPositions:
        """For the picture saved in `pic_path`, get the checkboxes positions in the pixel's matrix."""
        pic_data = self.data_handler.get_pic_data(pic_path)
        try:
            # The page may contain no question, so return an empty dict by default.
            boxes = self.config.boxes[pic_data.doc_id].get(pic_data.page, {})
        except KeyError:
            print(f"ERROR: doc id:{pic_data.doc_id}, doc page: {pic_data.page}")
            raise
        return {q_a: pic_data.xy2ij(*xy) for q_a, xy in boxes.items()}

    def get_checkboxes(self, pic_path: Path) -> dict[CbxRef, ndarray]:
        """For the picture saved in `pic_path`, get all the arrays representing the checkbox pictures."""
        checkboxes: dict[CbxRef, ndarray] = {}
        positions = self.get_checkboxes_positions(pic_path)
        matrix = self.data_handler.get_matrix(pic_path)
        cell_size = self.data_handler.get_pic_data(pic_path).calibration_data.cell_size
        for (q, a), (i, j) in positions.items():
            i, j = adjust_checkbox(matrix, i, j, cell_size)
            checkboxes[(q, a)] = matrix[i : i + cell_size, j : j + cell_size]
        return checkboxes

    def get_doc_checkboxes_state(self, doc_id: DocumentId) -> dict[Path, dict[CbxRef, DetectionStatus]]:
        # Get all paths corresponding to the given document id.
        doc_pic_paths = self.data_handler.get_document_pic_paths(doc_id)
        # Analyze each checkbox.
        to_analyze = {pic_path: self.get_checkboxes(pic_path) for pic_path in doc_pic_paths}
        if not to_analyze:
            print(f"No data: {doc_id}")
        return analyze_checkboxes(to_analyze)

    @property
    def checkboxes_state(self) -> dict[DocumentId : [Path, dict[CbxRef, DetectionStatus]]]:
        """Retrieve the state of each checkbox (checked or not).

        The returned dictionary is cached. The method follows this process:
        1. Attempt to retrieve the dictionary from the cache.
        2. If not cached, try loading it from disk.
        3. As a last resort, generate the dictionary by evaluating the blackness of each checkbox.
        """
        if self._checkboxes_state is None:
            # No cache, try to load it from the disk.
            for doc_id in self.data_handler.index:
                self._checkboxes_state = self.load_checkboxes_state(doc_id)
                if self._checkboxes_state is None:
                    print(f"Analyzing checkboxes: {doc_id}")
                    # No previous saving on the disk, generate the dictionary, and write it on the disk.
                    self._checkboxes_state = {
                        doc_id: self.get_doc_checkboxes_state(doc_id) for doc_id in self.data_handler.index
                    }
                    self.save_checkboxes_state(doc_id)
        assert self._checkboxes_state is not None
        return self._checkboxes_state

    @staticmethod
    def _encode_state(q_a: CbxRef, status: DetectionStatus) -> str:
        q, a = q_a
        return f"{q}, {a}: {status}"

    @staticmethod
    def _decode_state(line: str) -> tuple[CbxRef, DetectionStatus]:
        try:
            q_a, status = line.split(":")
            q, a = q_a.split(",")
            return (OriginalQuestionNumber(int(q)), OriginalAnswerNumber(int(a))), getattr(
                DetectionStatus, status
            )
        except (ValueError, AttributeError):
            raise InvalidFormat(f"Incorrect line: {line!r}")

    def _read_cbx_state_file(self, path) -> dict[CbxRef, DetectionStatus]:
        """Read the content of a checkboxes state file.

        May raise:
            - an OSError variant if the file is missing or unreadable.
            - an InvalidFormat if the file format is incorrect.
        """
        pic_cbx_status: dict[CbxRef, DetectionStatus] = {}
        for line in path.open("r", encoding="utf8"):
            q_a, status = self._decode_state(line)
            pic_cbx_status[q_a] = status
        return pic_cbx_status

    def save_checkboxes_state(self, doc_id: DocumentId) -> None:
        """Save to disk the checkboxes states for all the pictures associated with the given document id."""
        for path, pic_cbx_state in self.checkboxes_state[doc_id].items():
            (folder := path.parent / "review/checkboxes").mkdir(exist_ok=True, parents=True)
            lines = (self._encode_state(q_a, status) for q_a, status in pic_cbx_state.items())
            (folder / path.stem).write_text("\n".join(lines) + "\n", encoding="utf8")

    def load_checkboxes_state(self, doc_id: DocumentId) -> dict[Path, dict[CbxRef, DetectionStatus]] | None:
        """Load from disk the checkboxes states for all the pictures associated with the given document id."""
        doc_cbx_states: dict[Path, dict[CbxRef, DetectionStatus]] = {}
        for page, page_paths in self.data_handler.index[doc_id].items():
            for pic_path in page_paths:
                try:
                    cbx_state_file = pic_path.parent / "review/checkboxes" / pic_path.stem
                    # Read the file and import its data.
                    result = self._read_cbx_state_file(cbx_state_file)
                    # Now, we should verify that the (<question_num>, <answer_num>) keys
                    # are the expected one. (Unexpected or missing keys are unlikely,
                    # yet maybe the disk is corrupted?)
                    expected = set(self.data_handler.config.boxes[doc_id][page])
                    if set(result) == expected:
                        doc_cbx_states[pic_path] = result
                    else:
                        # Missing (or incorrect) data!
                        return None
                except (InvalidFormat, OSError):
                    # The data was not found on disk or the data are invalid.
                    return None
        return doc_cbx_states

    # TODO: Remove old code???

    # ==========
    #  OLD CODE
    # ==========

    # def review_doc_pictures(
    #     self, doc_pics: dict[Page, set[Path]], pdf_data: PdfData
    # ) -> dict[Path, ReviewData]:
    #     """Get checkbox state of all the pictures corresponding to the given document."""
    #     paths = [path for page, paths in doc_pics.items() for path in paths]
    #     # 1. Collect all the checkboxes
    #     checkboxes: dict[Path, dict[CbxRef, ndarray]] = {path: self.get_checkboxes(path) for path in paths}
    #     # 2. Analyze them
    #     checkboxes_status: dict[Path, dict[CbxRef, DetectionStatus]] = self.review_checkboxes(checkboxes)
    #     # 3. Detect student name / id
    #     # TODO:
    #     students: dict[Path, Student] = ...
    #     return {
    #         path: ReviewData(
    #             student_id=students[path].id,
    #             student_name=students[path].name,
    #             checkboxes=checkboxes_status[path],
    #         )
    #         for path in paths
    #     }
    #
    # def review_all_pictures(
    #     self, index: dict[DocumentId, dict[Page, set[Path]]], pdf_data: PdfData
    # ) -> dict[Path, ReviewData]:
    #     """Get checkbox state in all the pictures."""
    #     review: dict[Path, ReviewData] = {}
    #     for doc_id, doc_pics in index.items():
    #         review |= self.review_doc_pictures(doc_pics, pdf_data)
    #     return review

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
                if DetectionStatus.seems_checked(status):
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
                        case DetectionStatus.CHECKED:
                            c = "■"
                            ok = is_correct
                        case DetectionStatus.PROBABLY_CHECKED:
                            c = "■?"
                            ok = is_correct
                        case DetectionStatus.UNCHECKED:
                            c = "□"
                            ok = not is_correct
                        case DetectionStatus.PROBABLY_UNCHECKED:
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


def _get_max_blackness(blackness: dict[Path, dict[CbxRef, float]]) -> float:
    return max(max(pic_blackness_values.values(), default=0) for pic_blackness_values in blackness.values())


def _get_average_blackness(blackness: dict[Path, dict[CbxRef, float]]) -> float:
    total = 0.0
    count = 0
    for pic_blackness_values in blackness.values():
        for cbx_blackness in pic_blackness_values.values():
            total += cbx_blackness
            count += 1
    return total / count if count != 0 else 0


def analyze_checkboxes(
    all_checkboxes: dict[Path, dict[CbxRef, ndarray]],
) -> dict[Path, dict[CbxRef, DetectionStatus]]:
    """
    Evaluate each checkbox, and estimate if it was checked.
    """
    detection_status: dict[Path, dict[CbxRef, DetectionStatus]] = {path: {} for path in all_checkboxes}
    # Store blackness of checkboxes, to help detect false positives
    # and false negatives.
    blackness: dict[Path, dict[CbxRef, float]] = {path: {} for path in all_checkboxes}
    core_blackness: dict[Path, dict[CbxRef, float]] = {path: {} for path in all_checkboxes}

    for pic_path, pic_checkboxes in all_checkboxes.items():
        pic_blackness = blackness[pic_path]
        pic_core_blackness = core_blackness[pic_path]
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
    for pic_path, pic_checkboxes in all_checkboxes.items():
        pic_detection_status = detection_status[pic_path]
        pic_blackness = blackness[pic_path]
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
                    pic_detection_status[q_a] = DetectionStatus.CHECKED
                else:
                    pic_detection_status[q_a] = DetectionStatus.PROBABLY_CHECKED
            else:
                if test_square(proportion=0.2, gray_level=0.95) and pic_blackness[q_a] > upper_floor:
                    pic_detection_status[q_a] = DetectionStatus.PROBABLY_UNCHECKED
                else:
                    pic_detection_status[q_a] = DetectionStatus.UNCHECKED

    # Second pass :
    # We will test now for false negatives and false positives, by comparing each checkbox
    # with the other ones.
    # The assumption is that a student will likely use a consistent approach to marking the checkboxes.

    for pic_path in blackness:
        pic_blackness = blackness[pic_path]
        pic_core_blackness = core_blackness[pic_path]
        pic_detection_status = detection_status[pic_path]
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
                pic_detection_status[q_a] = DetectionStatus.PROBABLY_CHECKED

            # If a checkbox is tested as checked, but is much lighter than the darker one,
            # it is very probably a false positive.
            if pic_detection_status[q_a].seems_checked and (
                pic_blackness[q_a] < upper_floor or pic_core_blackness[q_a] < upper_core_floor
            ):
                if pic_blackness[q_a] < floor or pic_core_blackness[q_a] < core_floor:
                    print("False positive detected", q_a, pic_blackness[q_a], max_blackness)
                    # This is probably a false positive, but we'd better verify manually.
                    pic_detection_status[q_a] = DetectionStatus.PROBABLY_UNCHECKED
                else:
                    # Probably note a false positive, but we should verify.
                    pic_detection_status[q_a] = DetectionStatus.PROBABLY_CHECKED

    return detection_status
