import operator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ptyx.shell import print_warning

from ptyx_mcq.tools.config_parser import DocumentId, StudentName, PageNum

UnnamedDocsList = list[DocumentId]
AmbiguousPagesList = list[tuple[DocumentId, PageNum]]
DuplicateNamesDict = dict[StudentName, list[DocumentId]]

if TYPE_CHECKING:
    from ptyx_mcq.scan.data import ScanData


@dataclass
class DataCheckResult:
    unnamed_docs: UnnamedDocsList
    duplicate_names: DuplicateNamesDict
    ambiguous_answers: AmbiguousPagesList

    @property
    def names_to_review(self) -> list[DocumentId]:
        return self.unnamed_docs + [doc_id for docs in self.duplicate_names.values() for doc_id in docs]


class DataChecker:
    """
    Check for missing data.

    This check must occur *after* the integrity check (search for duplicate pages),
    so that each page is associated with a unique picture at this stage.
    """

    def __init__(self, scan_data: "ScanData"):
        self.scan_data = scan_data

    # @property
    # def index(self):
    #     return self.scan_data.index

    def run(self) -> DataCheckResult:
        print("Searching for unnamed documents...")
        unnamed_docs = self.get_unnamed_docs()
        print(f"{len(unnamed_docs)} unnamed document(s) found." if unnamed_docs else "OK")

        print("Searching for duplicate names...")
        duplicate_names = self.find_duplicate_names()
        print(f"{len(duplicate_names)} conflict(s) found." if duplicate_names else "OK")

        print("Searching for ambiguous answers...")
        ambiguous_answers = self.find_ambiguous_answers()
        print(f"{len(ambiguous_answers)} page(s) to verify." if ambiguous_answers else "OK")

        check_result = DataCheckResult(
            unnamed_docs=unnamed_docs, duplicate_names=duplicate_names, ambiguous_answers=ambiguous_answers
        )

        self.report_data_issues(check_result)
        return check_result

    def get_unnamed_docs(self) -> list[DocumentId]:
        """Get the (sorted) list of all unnamed documents ids."""
        # Sorting documents is cheap and make testing easier.
        return sorted(
            (doc.doc_id for doc in self.scan_data if doc.student_name == ""),
            key=operator.attrgetter("doc_id"),
        )

    def find_duplicate_names(self) -> DuplicateNamesDict:
        """Detect if several documents have the same student name.

        Return a dictionary associating each conflicting name with the corresponding documents.
        """
        seen_names: dict[StudentName, DocumentId] = {}
        duplicate_names: dict[StudentName, list[DocumentId]] = {}
        # Sorting documents is cheap and make testing easier.
        for doc_id in sorted(self.scan_data.index):
            name = self.scan_data.index[doc_id].student_name
            # Be careful to not count unnamed documents as duplicates!
            if name:
                if name in seen_names:
                    duplicate_names.setdefault(name, [seen_names[name]]).append(doc_id)
                    # matching_doc_id = seen_names[name]
                    # matching_doc_data = self.data[matching_doc_id]
                else:
                    seen_names[name] = doc_id
        return duplicate_names

    def find_ambiguous_answers(self) -> AmbiguousPagesList:
        # The answers are ambiguous and were not already manually verified in a previous scan.
        return [
            (doc_id, page_num)
            for doc_id, doc in self.scan_data.index.items()
            for page_num, page in doc.pages.items()
            if page.pic.checkboxes_need_review
        ]

    @staticmethod
    def report_data_issues(check_result: DataCheckResult) -> None:
        for doc_id in check_result.unnamed_docs:
            print_warning(f"• No student name for document {doc_id}.")
        for name, doc_ids in check_result.duplicate_names.items():
            print_warning(f"• Same student name {name!r} on documents {','.join(map(str, doc_ids))}.")
