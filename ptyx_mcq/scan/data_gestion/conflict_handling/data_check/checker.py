from dataclasses import dataclass
from pathlib import Path

from ptyx.shell import print_warning

from ptyx_mcq.scan.data_gestion.data_handler import DataHandler
from ptyx_mcq.scan.data_gestion.document_data import Page
from ptyx_mcq.tools.config_parser import DocumentId, StudentName

UnnamedDocsList = list[DocumentId]
AmbiguousPagesList = list[tuple[DocumentId, Page]]
DuplicateNamesDict = dict[StudentName, list[DocumentId]]


@dataclass
class DataCheckResult:
    unnamed_docs: UnnamedDocsList
    duplicate_names: DuplicateNamesDict
    ambiguous_answers: AmbiguousPagesList


class DataChecker:
    """Check for missing data."""

    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = self.data_storage.data

    def run(self) -> DataCheckResult:
        # First, complete missing information with previous scan data, if any.
        for doc_id, (student_name, student_id) in self.data_storage.more_infos.items():
            try:
                self.data[doc_id].name = student_name
                self.data[doc_id].student_id = student_id
            except KeyError:
                print_warning(f"Document {doc_id} not found... Maybe it was discarded previously?")

        # The students name to ID mapping may have been updated
        # (using `mcq fix` for example).
        # Let's try again to get names from ID.
        for doc_id, doc_data in self.data.items():
            if doc_data.name == "":
                doc_data.name = self.data_storage.config.students_ids.get(
                    doc_data.student_id, StudentName("")
                )

        print("Searching for unnamed documents...")
        unnamed_docs = self.get_unnamed_docs()
        print(f"{len(unnamed_docs)} unnamed document(s) found." if unnamed_docs else "OK")

        print("Searching for duplicate names...")
        duplicate_names = self.find_duplicate_names()
        print(f"{len(duplicate_names)} conflict(s) found." if duplicate_names else "OK")

        print("Searching for ambiguous answers...")
        ambiguous_answers = self.find_ambiguous_answers()
        print(f"{len(ambiguous_answers)} page(s) to verify." if ambiguous_answers else "OK")

        return DataCheckResult(
            unnamed_docs=unnamed_docs, duplicate_names=duplicate_names, ambiguous_answers=ambiguous_answers
        )

    def get_unnamed_docs(self) -> list[DocumentId]:
        """Get the (sorted) list of all unnamed documents ids."""
        # Sorting documents is cheap and make testing easier.
        return sorted(doc_id for doc_id, doc_data in self.data.items() if doc_data.name == "")

    def find_duplicate_names(self) -> DuplicateNamesDict:
        """Detect if several documents have the same student name.

        Return a dictionary associating each conflicting name with the corresponding documents.
        """
        seen_names: dict[StudentName, DocumentId] = {}
        duplicate_names: dict[StudentName, list[DocumentId]] = {}
        # Sorting documents is cheap and make testing easier.
        for doc_id in sorted(self.data):
            name = self.data[doc_id].name
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
            (doc_id, page)
            for doc_id, doc_data in self.data.items()
            for page, pic_data in doc_data.pages.items()
            if pic_data.needs_review and Path(pic_data.pic_path) not in self.data_storage.verified
        ]


# FIXME: the following function is not used anymore, remove it?


def report_data_issues(check_result: DataCheckResult) -> None:
    for doc_id in check_result.unnamed_docs:
        print_warning(f"• No student name for document {doc_id}.")
    for name, doc_ids in check_result.duplicate_names.items():
        print_warning(f"• Same student name {name!r} on documents {','.join(map(str, doc_ids))}.")
