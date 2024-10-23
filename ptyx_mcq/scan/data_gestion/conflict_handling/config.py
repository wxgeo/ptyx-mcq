from typing import Any

from ptyx_mcq.scan.data_gestion.conflict_handling.data_check.base import (
    AbstractNamesReviewer,
    AbstractAnswersReviewer,
    AbstractDocHeaderDisplayer,
)
from ptyx_mcq.scan.data_gestion.conflict_handling.data_check.cl_implementation import (
    ClNamesReviewer,
    ClAnswersReviewer,
    ClDocHeaderDisplayer,
)
from ptyx_mcq.scan.data_gestion.conflict_handling.integrity_check.cl_implementation import (
    ClIntegrityIssuesFixer,
)
from ptyx_mcq.scan.data_gestion.conflict_handling.integrity_check.base import AbstractIntegrityIssuesFixer


class Config:
    """A registry enabling extensions to customize conflicts' handling process.

    For now, this is used only by ptyx-mcq GUI.
    """

    NamesReviewer: type[AbstractNamesReviewer] = ClNamesReviewer
    AnswersReviewer: type[AbstractAnswersReviewer] = ClAnswersReviewer
    IntegrityIssuesFixer: type[AbstractIntegrityIssuesFixer] = ClIntegrityIssuesFixer
    DocHeaderDisplayer: type[AbstractDocHeaderDisplayer] = ClDocHeaderDisplayer

    extensions_data: dict[str, Any] = {}
