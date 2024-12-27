from dataclasses import dataclass

from ptyx.shell import print_warning, print_info, print_error

from ptyx_mcq.scan.data import ScanData
from ptyx_mcq.scan.data.documents import Document
from ptyx_mcq.tools.config_parser import DocumentId, OriginalQuestionNumber, PageNum

DuplicatePages = dict[DocumentId, list[PageNum]]
MissingPages = dict[DocumentId, list[PageNum]]
MissingQuestions = dict[DocumentId, list[OriginalQuestionNumber]]


class MissingQuestion(RuntimeError):
    """Error raised when some questions where not seen when scanning all data."""


class MissingConfigurationData(RuntimeError):
    """Error raised when some configuration data is missing."""


@dataclass
class IntegrityCheckResult:
    duplicates: dict[DocumentId, list[PageNum]]
    missing_pages: dict[DocumentId, list[PageNum]]
    missing_questions: dict[DocumentId, list[OriginalQuestionNumber]]


# def detect_duplicates(pictures: list[Picture]) -> tuple[list[Picture], list[Picture]]:
#     already_seen = set()
#     no_duplicates = []
#     duplicates = []
#     for pic in pictures:
#         tuple_ = pic.as_hashable_tuple()
#         if tuple_ in already_seen:
#             duplicates.append(pic)
#         else:
#             no_duplicates.append(pic)
#             already_seen.add(tuple_)
#     return no_duplicates, duplicates


class IntegrityChecker:
    """Test for data integrity: each scanned document must appear only once, and must be complete."""

    def __init__(self, data_manager: ScanData):
        self.data_manager = data_manager

    @property
    def index(self) -> dict[DocumentId, Document]:
        return self.data_manager.index

    def run(self) -> IntegrityCheckResult:
        """Main method: check problems, then solve them with user help."""
        print("Searching for duplicate pages...")
        duplicates = self.search_for_duplicate_pages()
        print("Searching for missing pages...")
        missing_pages, missing_questions = self.check_for_missing_pages()
        return IntegrityCheckResult(
            duplicates=duplicates,
            missing_pages=missing_pages,
            missing_questions=missing_questions,
        )

    def search_for_duplicate_pages(self) -> DuplicatePages:
        """Search for duplicate pages.

        Return a list of conflicts, i.e. a dictionary with the different versions of a page
        for the same document.
        """
        duplicates: DuplicatePages = {}
        for doc_id, doc in self.data_manager.index.items():
            for page_num, page in doc.pages.items():
                if len(page.pictures) >= 2:
                    print_info(f"Page {page_num} of document {doc_id} found in {len(page.pictures)} copies.")
                    page.disable_duplicates()
                if len(page.pictures) >= 2:
                    duplicates.setdefault(doc_id, []).append(page_num)
        return duplicates

    def check_for_missing_pages(self) -> tuple[MissingPages, MissingQuestions]:
        """For every scanned document:
        - all pages must have been scanned,
        - all questions must have been seen."""
        missing_questions: MissingQuestions = {}
        missing_pages: MissingPages = {}
        ordering = self.data_manager.config.ordering
        for doc_id, doc in self.index.items():
            try:
                doc_ordering = ordering[doc_id]
            except KeyError:
                raise MissingConfigurationData(
                    f"No configuration data found for document #{doc_id}.\n"
                    "Maybe you recompiled the ptyx file in the while ?\n"
                    f"(Executing `mcq make -n {max(self.index)}` might fix it.)"
                )
            expected = set(doc_ordering["questions"])
            if questions_diff := sorted(expected - set(doc.questions)):
                missing_questions[doc_id] = questions_diff
            # ", ".join(str(q) for q in unseen_questions)
            # All tests may not have the same number of pages, since
            # page breaking will occur at a different place for each test.
            if pages_diff := sorted(
                set(self.data_manager.config.boxes[doc_id]) - set(self.index[doc_id].pages)
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
