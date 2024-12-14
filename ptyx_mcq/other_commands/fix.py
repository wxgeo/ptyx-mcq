from ptyx_mcq.tools.config_parser import DocumentId, StudentName, StudentId, Page


def fix_doc(
    doc: DocumentId | None = None,
    page: Page | None = None,
    student_name: StudentName | None = None,
    student_id: StudentId | None = None,
) -> None:
    """Launch a verification of all the answers of the specified document or the specified page."""
    raise NotImplementedError


def fix_name(doc: DocumentId) -> None:
    """Launch a verification of the student's name and identifier for the specified document."""
    raise NotImplementedError
