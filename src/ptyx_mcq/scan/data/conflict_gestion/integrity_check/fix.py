from abc import ABC, abstractmethod
from typing import Literal

from ptyx.pretty_print import print_success

from ptyx_mcq.scan.data import ScanData, Picture
from ptyx_mcq.scan.data.conflict_gestion.integrity_check.check import (
    MissingPage,
    IntegrityCheckResult,
)


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
        if check_results.missing_pages:
            # Don't raise an error for pages not found (only a warning in log)
            # since if all questions were found, they were probably only empty pages.
            # However, an error must be raised for missing questions.
            #            if input("Should we skip missing questions? (y/n)").lower() != "y":
            raise MissingPage("Page not seen! (Look at message above).")
        else:
            print_success("Data integrity successfully verified.")

        for doc_id, page_num_list in check_results.duplicates.items():
            for page_num in page_num_list:
                page = self.index[doc_id].pages[page_num]
                while page.has_conflicts:
                    print(f"Document {doc_id}: please select a version for page {page_num}.")
                    pic1, pic2, *_ = page.used_pictures
                    version = self.select_version(pic1, pic2)
                    match version:
                        case 1:
                            pic2.use = False
                            print(f"Picture 1 selected ({pic1.short_path})")
                            print(f"Picture 2 discarded ({pic2.short_path})")
                        case 2:
                            pic1.use = False
                            print(f"Picture 1 discarded ({pic1.short_path})")
                            print(f"Picture 2 selected ({pic2.short_path})")
                        case _ as selection:
                            raise ValueError(f"Value must be 1 or 2, not {selection}.")
                    # print(len(page.used_pictures), [pic.use for pic in page.pictures])
