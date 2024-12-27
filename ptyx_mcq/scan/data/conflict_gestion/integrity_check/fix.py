from abc import ABC, abstractmethod
from typing import Literal

from ptyx.shell import print_success, print_warning

from ptyx_mcq.scan.data.conflict_gestion.integrity_check.check import (
    MissingQuestion,
    IntegrityCheckResult,
)
from ptyx_mcq.scan.data import ScanData, Picture
from ptyx_mcq.tools.config_parser import DocumentId, PageNum


class AbstractIntegrityIssuesFixer(ABC):
    """Abstract class to build an integrity issues' fixer.

    All interaction methods must be implemented."""

    def __init__(self, scan_data: ScanData):
        self.scan_data = scan_data

    @property
    def index(self):
        return self.scan_data.index

    @abstractmethod
    def select_version(self, pic1: Picture, pic2: Picture) -> Literal[1, 2]:
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

        for doc_id, page_num_list in check_results.duplicates:
            for page_num in page_num_list:
                page = self.index[doc_id].pages[page_num]
                while page.has_conflicts:
                    pic1, pic2, *_ = page.pictures
                    bad_pic = page.pictures.pop(self.select_version(pic1, pic2) - 1)
                    # Write a file <pdf-hash>/<pic-num>.skip,
                    # to indicate that the picture should be ignored in case of a future run.
                    (folder := self.scan_data.paths.dirs.fix / bad_pic.pdf_hash).mkdir(exist_ok=True)
                    (folder / f"{bad_pic.num}.skip").touch()
