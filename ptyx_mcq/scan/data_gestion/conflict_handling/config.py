from ptyx_mcq.scan.data_gestion.conflict_handling.data_check.cl_implementation import (
    ClNamesReviewer,
    ClAnswersReviewer,
)
from ptyx_mcq.scan.data_gestion.conflict_handling.integrity_check.cl_implementation import (
    ClIntegrityIssuesFixer,
)


class Config:
    NamesReviewer = ClNamesReviewer
    AnswersReviewer = ClAnswersReviewer
    IntegrityIssuesFixer = ClIntegrityIssuesFixer
