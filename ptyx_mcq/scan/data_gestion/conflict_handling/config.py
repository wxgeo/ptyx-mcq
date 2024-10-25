from typing import Any

from ptyx_mcq.scan.data_gestion.conflict_handling.data_check.fix import (
    AbstractNamesReviewer,
    AbstractAnswersReviewer,
    AbstractDocHeaderDisplayer,
    DefaultAllDataIssuesFixer,
)
from ptyx_mcq.scan.data_gestion.conflict_handling.data_check.cl_fix import (
    ClNamesReviewer,
    ClAnswersReviewer,
    ClDocHeaderDisplayer,
)
from ptyx_mcq.scan.data_gestion.conflict_handling.integrity_check.cl_fix import (
    ClIntegrityIssuesFixer,
)
from ptyx_mcq.scan.data_gestion.conflict_handling.integrity_check.fix import AbstractIntegrityIssuesFixer


class Config:
    """A registry enabling extensions to customize conflicts' handling process.

    For now, this is used only by ptyx-mcq GUI.
    """

    NamesReviewer: type[AbstractNamesReviewer] = ClNamesReviewer
    AnswersReviewer: type[AbstractAnswersReviewer] = ClAnswersReviewer
    IntegrityIssuesFixer: type[AbstractIntegrityIssuesFixer] = ClIntegrityIssuesFixer
    DocHeaderDisplayer: type[AbstractDocHeaderDisplayer] = ClDocHeaderDisplayer
    AllDataIssuesFixer: type[DefaultAllDataIssuesFixer] = DefaultAllDataIssuesFixer

    extensions_data: dict[str, Any] = {}
