from dataclasses import dataclass

from ptyx.shell import print_warning, print_info, print_error

from ptyx_mcq.scan.data.main_manager import DataHandler
from ptyx_mcq.scan.data.structures import DocumentData, PicData
from ptyx_mcq.tools.config_parser import DocumentId, OriginalQuestionNumber, Page

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


# FIXME: the following function is not used anymore, remove it?


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
