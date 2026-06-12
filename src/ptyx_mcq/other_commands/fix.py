from pathlib import Path

from ptyx.pretty_print import print_info, print_warning, print_success

from ptyx_mcq.scan.data import Document

from ptyx_mcq.scan.data.conflict_gestion.data_check.check import DataCheckResult


from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION
from ptyx_mcq.scan import MCQPictureParser

from ptyx_mcq.tools.io_tools import get_file_or_sysexit

from ptyx_mcq.tools.config_parser import DocumentId, StudentName, StudentId, PageNum
from ptyx_mcq.scan.data.conflict_gestion.config import Config


def _get_scan_data(path: Path) -> MCQPictureParser:
    """
    Get the data from the scanned document.

    If a previous scan is detected, the data will be loaded from the previously generated data files,
    stored on the disk. If the data are missing or out of sync, they will be extracted from the scanned PDF.

    The data themselves are stored in the attribute `.scan_data` of the returned mcq picture parser.

    :param path: The path to a .ptyx.mcq.config.json file (a pTyX configuration file).
    :return: The MCQ picture parser, which contains all the up-to-date extracted data from the scanned document.
    """
    config_file = get_file_or_sysexit(path, extension=CONFIG_FILE_EXTENSION)
    parser = MCQPictureParser(config_file)
    parser.analyze_pages()
    return parser


def _print_results(*docs: Document) -> None:
    print("Found results:")
    for doc in docs:
        print(f"- Document #{doc.doc_id}: {doc.student_name} ({doc.student_id})")


def fix_doc(
    path: Path,
    doc: DocumentId | None = None,
    page: PageNum | None = None,
    name: StudentName | None = None,
    student_id: StudentId | None = None,
    max_results: int = 10,
) -> None:
    """Launch a verification of all the answers of the specified document or the specified page."""

    # Load or extract scan data.
    print_info("Analyzing the scanned data...")
    parser = _get_scan_data(path)

    # Collect all the matching documents.
    print_info("Searching for matching documents...")
    docs_and_pages: set[tuple[DocumentId, PageNum]] = set()
    for _doc_id, _doc in parser.scan_data.used_docs_index.items():
        if name is not None and not _doc.student_name.startswith(name):
            continue
        if student_id is not None and not _doc.student_id != student_id:
            continue
        if doc is not None and doc != _doc_id:
            continue
        for _page in _doc.pages_index:
            if page is not None and _page != page:
                continue
            docs_and_pages.add((_doc_id, _page))

    _doc_ids: set[DocumentId] = {_id for _id, _ in docs_and_pages}
    docs: list[Document] = [parser.scan_data.used_docs_index[_id] for _id in _doc_ids]
    if docs_and_pages:
        _print_results(*docs)

        if len(docs) <= max_results:
            # Ask the user to review those documents.
            to_check = DataCheckResult(
                unnamed_docs=[], duplicate_names={}, ambiguous_answers=sorted(docs_and_pages)
            )
            Config.AllDataIssuesFixer(parser.scan_data).run(check_result=to_check)
            print_info("Updating scores...")
            # Recalculate scores.
            parser.calculate_scores()
            print_info("Regenerating the output documents...")
            # Regenerate the output documents.
            parser.generate_documents()
            print_success("Documents successfully reviewed.")
        print_warning(
            f"{len(docs_and_pages)} documents were found, but the maximal number of results is set to {max_results}.\n"
            "You can modify this maximal number of results using the option `--max-docs <MAX>`."
        )

    else:
        print_warning("No matching document found.")


def fix_name(path: Path, doc: DocumentId) -> None:
    """Launch a verification of the student's name and identifier for the specified document."""
    # Load or extract scan data.
    parser = _get_scan_data(path)
    if doc not in parser.scan_data.used_docs_index:
        print_warning(f"Document {doc} was not found in the scanned documents.")
    else:
        _print_results(parser.scan_data.used_docs_index[doc])
        # Ask the user to set the student's name for this document.
        to_check = DataCheckResult(unnamed_docs=[doc], duplicate_names={}, ambiguous_answers=[])
        Config.AllDataIssuesFixer(parser.scan_data).run(check_result=to_check)
        print_success(f"Document {doc} successfully reviewed.")
