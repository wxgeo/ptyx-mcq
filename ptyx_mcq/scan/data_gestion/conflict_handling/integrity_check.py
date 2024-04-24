"""
This module contains tools to check data completeness, ie:
    - all documents are complete (no missing page)
    - there are no duplicates (each document/page must appear only once)

Main classes:
    - `IntegrityChecker`: report integrity problems.
    - `FixIntegrityIssues`: fix reported issues (if possible), with user help.

The function `report_integrity_issues()`

"""
from dataclasses import dataclass
from typing import Literal

from PIL import Image, ImageDraw
from ptyx.shell import print_success, print_warning, print_info, print_error

from ptyx_mcq.tools.rgb import Color

from ptyx_mcq.scan.data_gestion.data_handler import DataHandler
from ptyx_mcq.scan.data_gestion.document_data import Page, DocumentData, PicData
from ptyx_mcq.scan.picture_analyze.image_viewer import ImageViewer
from ptyx_mcq.tools.config_parser import DocumentId, OriginalQuestionNumber

DuplicatePagesDict = dict[tuple[DocumentId, Page], list[DocumentId]]
MissingPages = dict[DocumentId, list[Page]]
MissingQuestions = dict[DocumentId, list[OriginalQuestionNumber]]


class MissingQuestion(RuntimeError):
    """Error raised when some questions where not seen when scanning all data."""


class MissingConfigurationData(RuntimeError):
    """Error raised when some configuration data is missing."""


@dataclass
class IntegrityCheckResult:
    conflicts: DuplicatePagesDict
    resolved_conflicts: DuplicatePagesDict
    missing_pages: MissingPages
    missing_questions: MissingQuestions


class IntegrityChecker:
    """Test for data integrity: each scanned document must appear only once, and must be complete."""

    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = self.data_storage.data

    def run(self) -> IntegrityCheckResult:
        """Main method: check problems, then solve them with user help."""
        print("Searching for duplicate pages...")
        conflicts, resolved_conflicts = self.search_for_duplicate_pages()
        print("Searching for missing pages...")
        missing_pages, missing_questions = self.check_for_missing_pages()
        return IntegrityCheckResult(
            conflicts=conflicts,
            resolved_conflicts=resolved_conflicts,
            missing_pages=missing_pages,
            missing_questions=missing_questions,
        )

    def search_for_duplicate_pages(self) -> tuple[DuplicatePagesDict, DuplicatePagesDict]:
        """Search for duplicate pages.

        Return a list of conflicts, i.e. a dictionary with the different versions of a page
        for the same document.
        """
        conflicts: dict[tuple[DocumentId, Page], list[DocumentId]] = {}
        resolved_conflicts: dict[tuple[DocumentId, Page], list[DocumentId]] = {}
        tmp_doc_id: DocumentId
        doc_data: DocumentData
        page: Page
        pic_data: PicData
        print(list(self.data))
        for tmp_doc_id, doc_data in self.data_storage.get_all_temporary_ids().items():
            assert tmp_doc_id < 0
            assert len(doc_data.pages) == 1, (tmp_doc_id, list(doc_data.pages))
            print(tmp_doc_id, list(doc_data.pages))
            for page, pic_data in doc_data.pages.items():
                print(list(self.data))
                scanned_id = pic_data.doc_id
                conflicting_pic_data = self.data[scanned_id].pages[page]
                same_data = (
                    pic_data.detection_status == conflicting_pic_data.detection_status
                    and pic_data.name == conflicting_pic_data.name
                )
                if same_data:
                    # Same name and same answers detected for both versions,
                    # so we can safely ignore the new version, and remove `tmp_dic_id` data.
                    self.data_storage.remove_tmp_doc_id(tmp_doc_id)
                    resolved_conflicts.setdefault((scanned_id, page), []).append(tmp_doc_id)
                else:
                    conflicts.setdefault((scanned_id, page), []).append(tmp_doc_id)
        return conflicts, resolved_conflicts

    def check_for_missing_pages(self) -> tuple[MissingPages, MissingQuestions]:
        """For every scanned document:
        - all pages must have been scanned,
        - all questions must have been seen."""
        missing_questions: MissingQuestions = {}
        missing_pages: MissingPages = {}
        ordering = self.data_storage.config.ordering
        for doc_id in self.data:
            if self.data_storage.is_temp_id(doc_id):
                # This is just a duplicate of an already scanned document, so skip it.
                continue
            try:
                doc_ordering = ordering[doc_id]
            except KeyError:
                raise MissingConfigurationData(
                    f"No configuration data found for document #{doc_id}.\n"
                    "Maybe you recompiled the ptyx file in the while ?\n"
                    f"(Launching `mcq make -n {max(self.data)}` might fix it.)"
                )
            if questions_diff := sorted(set(doc_ordering["questions"]) - set(self.data[doc_id].answered)):
                missing_questions[doc_id] = questions_diff
            # ", ".join(str(q) for q in unseen_questions)
            # All tests may not have the same number of pages, since
            # page breaking will occur at a different place for each test.
            if pages_diff := sorted(
                set(self.data_storage.config.boxes[doc_id]) - set(self.data[doc_id].pages)
            ):
                missing_pages[doc_id] = pages_diff

        return missing_pages, missing_questions


class FixIntegrityIssues:
    """
    Interact with the user to fix previously found problems.

    Main method is `run()`.
    """

    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = self.data_storage.data

    def run(self, check_results: IntegrityCheckResult) -> None:
        if check_results.missing_questions:
            # Don't raise an error for pages not found (only a warning in log)
            # if all questions were found, this was probably empty pages.
            if input("Should we skip missing questions? (y/n)").lower() != "y":
                raise MissingQuestion("Questions not seen! (Look at message above).")
        else:
            print_success("Data integrity successfully verified.")

        while check_results.conflicts:
            conflict = next(iter(check_results.conflicts))
            scanned_id, page = conflict
            for tmp_doc_id in check_results.conflicts.pop(conflict):
                if self._select_version(scanned_id, tmp_doc_id, page) == 1:
                    # Remove the second version.
                    self.data_storage.remove_tmp_doc_id(tmp_doc_id)
                else:
                    # Remove first version:
                    # we must replace the data and the files corresponding to this page
                    # by the new version (corresponding to id `tmp_doc_id`).
                    # Warning: All other data of document `scanned_id` (i.e. the data for all the other pages)
                    # must be kept unchanged!
                    self.data[scanned_id].pages[page] = self.data.pop(tmp_doc_id).pages[page]
                    data_dir = self.data_storage.dirs.data
                    # Replace the WEBP image.
                    (data_dir / f"{tmp_doc_id}-{page}.webp").replace(data_dir / f"{scanned_id}-{page}.webp")
                    # Create an updated `scanned_id` .scandata file.
                    # Warning: we can't simply replace it with the `tmp_doc_id` .scandata file, because it would only
                    # contain the data corresponding to this page, not the other ones.
                    self.data_storage.write_scandata_file(scanned_id)
        assert len(self.data_storage.get_all_temporary_ids()) == 0, self.data_storage.get_all_temporary_ids()

    def _select_version(
        self, scanned_doc_id: DocumentId, temp_doc_id: DocumentId, page: Page
    ) -> Literal[1, 2]:
        """Ask user what to do is two versions of the same page exist, with conflicting data.

        It may mean the page has been scanned twice with different scan qualities, but it could
        also indicate a more serious problem (for example, tests with the same ID
        have been given to different students !).
        Anyway, we should signal the problem to the user, and ask him
        what he wants to do.

        Return the number of the version to keep, either 1 or 2.
        """
        pic_path1 = self.data[scanned_doc_id].pages[page].pic_path
        pic_path1 = self.data_storage.absolute_pic_path(pic_path1)
        pic_path2 = self.data[temp_doc_id].pages[page].pic_path
        pic_path2 = self.data_storage.absolute_pic_path(pic_path2)
        # assert isinstance(pic_path1, str)
        # assert isinstance(pic_path2, str)
        print_warning(
            f"Page {page} of test #{scanned_doc_id} seen twice " f'(in "{pic_path1}" and "{pic_path2}") !'
        )
        print("Choose which version to keep:")
        input("-- Press ENTER --")
        action = ""

        while action not in ("1", "2"):
            self._display_duplicates(scanned_doc_id, temp_doc_id, page)
            print("What must we do ?")
            print("- Keep only 1st one (1)")
            print("- Keep only 2nd one (2)")
            print("If you want to see the pictures again, juste press ENTER.")
            action = input("Answer: ")

        return 1 if action == "1" else 2

    def _display_duplicates(self, scanned_doc_id: DocumentId, temp_doc_id: DocumentId, page: Page) -> None:
        # im1 = Image.open(pic_path1)
        # im2 = Image.open(pic_path2)
        im1 = self.data_storage.get_pic(scanned_doc_id, page)
        im2 = self.data_storage.get_pic(temp_doc_id, page)
        dst = Image.new("RGB", (im1.width + im2.width, height := min(im1.height, im2.height)))
        dst.paste(im1, (0, 0))
        dst.paste(im2, (im1.width, 0))
        ImageDraw.Draw(dst).line([(im1.width, 0), (im1.width, height)], fill=Color.blue)

        ImageViewer(image=dst).display()


def report_integrity_issues(integrity_check_results: IntegrityCheckResult):
    # TODO: refactor this, and improve display.
    if integrity_check_results.conflicts or integrity_check_results.resolved_conflicts:
        print("--------------------------")
        print("Pages found several times:")
        print("--------------------------")
        for conflict in integrity_check_results.conflicts:
            scanned_id, page = conflict
            print_warning(f"Page {page} of document {scanned_id} was scanned twice.")
        for conflict in integrity_check_results.resolved_conflicts:
            scanned_id, page = conflict
            print_warning(f"Page {page} of document {scanned_id} was scanned twice.")
            print_info("Same information found on both versions, so we may safely ignore it.")
    else:
        print("[OK] No duplicate pages.")

    if integrity_check_results.missing_pages:
        print_warning("Pages missing:")
        for doc_id in sorted(integrity_check_results.missing_pages):
            print_warning(
                f"    • Test {doc_id}: page(s) {', '.join(map(str, integrity_check_results.missing_pages[doc_id]))}"
            )
        if not integrity_check_results.missing_questions:
            print_info(
                "Missing pages seem to be empty, since all questions"
                " and answers have been successfully recovered yet."
            )
    if integrity_check_results.missing_questions:
        print_error("Questions missing!")
        for doc_id in sorted(integrity_check_results.missing_questions):
            questions = ", ".join(map(str, integrity_check_results.missing_questions[doc_id]))
            print_error(f"    • Test {doc_id}: question(s) {questions}")
