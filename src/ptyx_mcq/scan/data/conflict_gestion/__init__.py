from ptyx_mcq.scan.data.conflict_gestion.data_check.check import DataChecker
from ptyx_mcq.scan.data.conflict_gestion.integrity_check.check import IntegrityChecker
from ptyx_mcq.scan.data import ScanData


class ConflictSolver:
    def __init__(self, scan_data: ScanData):
        self.scan_data = scan_data

    def run(self):
        from ptyx_mcq.scan.data.conflict_gestion.config import Config

        # Check that all documents are scanned completely, and only once.
        integrity_check_results = IntegrityChecker(self.scan_data).run()
        # Fix found issues.
        Config.IntegrityIssuesFixer(self.scan_data).run(integrity_check_results)
        # Search for data's inconsistencies: duplicate or missing names, ambiguous answers.
        data_check_results = DataChecker(self.scan_data).run()
        # Fix found issues.
        Config.AllDataIssuesFixer(self.scan_data).run(check_result=data_check_results)


__all__ = [
    "ConflictSolver",
]
