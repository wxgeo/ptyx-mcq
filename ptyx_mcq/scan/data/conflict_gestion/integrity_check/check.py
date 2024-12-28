from dataclasses import dataclass

from ptyx.shell import print_warning, print_info, print_success, print_error

from ptyx_mcq.scan.data import ScanData
from ptyx_mcq.scan.data.documents import Document
from ptyx_mcq.tools.config_parser import DocumentId, OriginalQuestionNumber, PageNum

DuplicatePages = dict[DocumentId, list[PageNum]]
MissingPages = dict[DocumentId, list[PageNum]]
MissingQuestions = dict[DocumentId, list[OriginalQuestionNumber]]


class MissingPage(RuntimeError):
    """Error raised when a page was not seen when scanning all data."""


class MissingConfigurationData(RuntimeError):
    """Error raised when some configuration data is missing."""


@dataclass
class IntegrityCheckResult:
    duplicates: dict[DocumentId, list[PageNum]]
    missing_pages: dict[DocumentId, list[PageNum]]


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

    def __init__(self, scan_data: ScanData):
        self.scan_data = scan_data

    @property
    def index(self) -> dict[DocumentId, Document]:
        return self.scan_data.index

    def run(self) -> IntegrityCheckResult:
        """Main method: check problems, then solve them with user help."""
        print("Searching for duplicate pages...")
        duplicates = self.search_for_duplicate_pages()
        print("Searching for missing pages...")
        missing_pages = self.check_for_missing_pages()
        check_result = IntegrityCheckResult(
            duplicates=duplicates,
            missing_pages=missing_pages,
        )
        self.report_integrity_issues(check_result)
        return check_result

    def search_for_duplicate_pages(self) -> DuplicatePages:
        """Search for duplicate pages.

        Return a list of potential conflicts, i.e. a dictionary with the different versions of a page
        for the same document.
        """
        duplicates: DuplicatePages = {}
        for doc_id, doc in self.scan_data.index.items():
            for page_num, page in doc.pages.items():
                if len(page.pictures) >= 2:
                    print_info(f"Page {page_num} of document {doc_id} found in {len(page.pictures)} copies.")
                    page.disable_duplicates()
                    duplicates.setdefault(doc_id, []).append(page_num)
        return duplicates

    def check_for_missing_pages(self) -> MissingPages:
        """For every scanned document:
        - all pages must have been scanned,
        - all questions must have been seen."""
        missing_pages: MissingPages = {}
        boxes = self.scan_data.config.boxes
        for doc_id, doc in self.index.items():
            try:
                # Boxes will retrieve only the pages containing questions.
                # (This is fine, since pages containing no questions don't need to be scanned anyway).
                expected_pages = set(boxes[doc_id])
            except KeyError:
                raise MissingConfigurationData(
                    f"No configuration data found for document #{doc_id}.\n"
                    "Maybe you recompiled the ptyx file in the while ?\n"
                    f"(Executing `mcq make -n {max(self.index)}` might fix it.)"
                )
            seen_pages = set(self.index[doc_id].pages)
            if unseen_pages := expected_pages - seen_pages:
                missing_pages[doc_id] = sorted(unseen_pages)
        return missing_pages

    def report_integrity_issues(self, integrity_check_results: IntegrityCheckResult):
        # TODO: refactor this, and improve display.
        if integrity_check_results.duplicates:
            print("--------------------------")
            print("Pages found several times:")
            print("--------------------------")
            for doc_id, page_num_list in integrity_check_results.duplicates.items():
                for page_num in page_num_list:
                    print_info(f"Page {page_num} of document {doc_id} was scanned several times.")
                    if self.scan_data.index[doc_id].pages[page_num].has_conflicts:
                        print_warning("Different conflicting versions of this page were found!")
        else:
            print_success("No duplicate pages.")

        if integrity_check_results.missing_pages:
            print("--------------------------")
            print("Pages missing:")
            print("--------------------------")
            for doc_id, page_num_list in integrity_check_results.missing_pages.items():
                print_error(f"Document {doc_id} has missing pages:  {', '.join(map(str, page_num_list))}")
        else:
            print_success("No missing pages.")
