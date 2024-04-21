from ptyx_mcq.scan.data_gestion.conflict_handling.data_check import (
    DataChecker,
    AllDataIssuesFixer,
    AnswersReviewer,
    NamesReviewer,
)
from ptyx_mcq.scan.data_gestion.conflict_handling.integrity_check import IntegrityChecker, FixIntegrityIssues
from ptyx_mcq.scan.data_gestion.data_handler import DataHandler


class ConflictSolver:
    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = data_storage.data

    def run(self):
        # Check that all documents are scanned completely, and only once.
        integrity_check_results = IntegrityChecker(self.data_storage).run()
        # Fix found issues.
        FixIntegrityIssues(self.data_storage).run(integrity_check_results)
        # Search for data's inconsistencies: duplicate or missing names, ambiguous answers.
        data_check_results = DataChecker(self.data_storage).run()
        # Fix found issues.
        AllDataIssuesFixer(self.data_storage).run(check_result=data_check_results)


__all__ = [
    "ConflictSolver",
    "IntegrityChecker",
    "FixIntegrityIssues",
    "DataChecker",
    "AllDataIssuesFixer",
    "NamesReviewer",
    "AnswersReviewer",
]
