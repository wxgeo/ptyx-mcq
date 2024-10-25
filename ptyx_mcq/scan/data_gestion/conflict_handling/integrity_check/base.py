from abc import ABC, abstractmethod
from typing import Literal

from ptyx.shell import print_success, print_warning

from ptyx_mcq.scan.data_gestion.conflict_handling.integrity_check.checker import (
    MissingQuestion,
    IntegrityCheckResult,
)
from ptyx_mcq.scan.data_gestion.data_handler import DataHandler
from ptyx_mcq.scan.data_gestion.document_data import Page
from ptyx_mcq.tools.config_parser import DocumentId


class AbstractIntegrityIssuesFixer(ABC):
    """Abstract class to build an integrity issues' fixer.

    All interaction methods must be implemented."""

    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = self.data_storage.data

    @abstractmethod
    def select_version(
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
        ...

    def run(self, check_results: IntegrityCheckResult) -> None:
        if check_results.missing_questions:
            # Don't raise an error for pages not found (only a warning in log)
            # since if all questions were found, they were probably only empty pages.
            # However, an error must be raised for missing questions.
            #            if input("Should we skip missing questions? (y/n)").lower() != "y":
            raise MissingQuestion("Questions not seen! (Look at message above).")
        else:
            print_success("Data integrity successfully verified.")

        while check_results.conflicts:
            conflict = next(iter(check_results.conflicts))
            scanned_id, page = conflict
            for tmp_doc_id in check_results.conflicts.pop(conflict):
                print_warning(
                    f"Page {page} of test #{scanned_id} seen twice"
                    f' (in "{self.data_storage.absolute_pic_path_for_page(scanned_id, page)}"'
                    f' and "{self.data_storage.absolute_pic_path_for_page(tmp_doc_id, page)}")!'
                )
                if self.select_version(scanned_id, tmp_doc_id, page) == 1:
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
