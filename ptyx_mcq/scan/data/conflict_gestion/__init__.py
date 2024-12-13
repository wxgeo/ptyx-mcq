from ptyx_mcq.scan.data.conflict_gestion.data_check.check import DataChecker
from ptyx_mcq.scan.data.conflict_gestion.integrity_check.check import IntegrityChecker
from ptyx_mcq.scan.data.main_manager import DataHandler


class ConflictSolver:
    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = data_storage.data

    def run(self):
        from ptyx_mcq.scan.data.conflict_gestion.config import Config

        # Check that all documents are scanned completely, and only once.
        integrity_check_results = IntegrityChecker(self.data_storage).run()
        # Fix found issues.
        Config.IntegrityIssuesFixer(self.data_storage).run(integrity_check_results)
        # Search for data's inconsistencies: duplicate or missing names, ambiguous answers.
        data_check_results = DataChecker(self.data_storage).run()
        # Fix found issues.
        Config.AllDataIssuesFixer(self.data_storage).run(check_result=data_check_results)


__all__ = [
    "ConflictSolver",
]
