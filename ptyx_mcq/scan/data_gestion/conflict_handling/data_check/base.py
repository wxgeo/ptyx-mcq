import string
from abc import ABC, abstractmethod, ABCMeta
from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from ptyx.shell import print_warning, print_error, print_info

from ptyx_mcq.scan.data_gestion.data_handler import DataHandler
from ptyx_mcq.scan.data_gestion.document_data import Page
from ptyx_mcq.tools.config_parser import DocumentId, StudentName, StudentId
from ptyx_mcq.tools.math import levenshtein_distance

UnnamedDocsList = list[DocumentId]
AmbiguousPagesList = list[tuple[DocumentId, Page]]
DuplicateNamesDict = dict[StudentName, list[DocumentId]]


@dataclass
class DataCheckResult:
    unnamed_docs: UnnamedDocsList
    duplicate_names: DuplicateNamesDict
    ambiguous_answers: AmbiguousPagesList


class Action(StrEnum):
    NEXT = ">"
    BACK = "<"
    DISCARD = "/"


class AbstractDocHeaderDisplayer(AbstractContextManager, ABC):
    """Abstract class."""

    # noinspection PyUnusedLocal
    @abstractmethod
    def __init__(self, data_storage: DataHandler, doc_id: DocumentId):
        ...

    @abstractmethod
    def display(self) -> None:
        """Display document header."""


class AbstractNamesReviewer(ABC, metaclass=ABCMeta):
    """Abstract class."""

    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = data_storage.data
        self.students_ids = self.data_storage.config.students_ids

    def enter_name_and_id(
        self, doc_id: DocumentId, default: StudentName
    ) -> tuple[StudentName, StudentId, Action, bool]:
        """Ask user to read student name and id for current document.

        Return the given student name (empty if no name was provided),
        the student id (same remark), the action to do
        (go to next document, go back to previous one, or skip document),
        and a boolean which indicates if the document as been
        effectively reviewed.
        """
        name = StudentName("")
        student_id = StudentId("")
        action: Action | None = None

        suggestion = default

        from ptyx_mcq.scan.data_gestion.conflict_handling.config import Config

        with Config.DocHeaderDisplayer(self.data_storage, doc_id) as doc_header_displayer:
            while action is None:
                doc_header_displayer.display()

                # ------------------------------
                # Ask the user to read the name.
                # ------------------------------
                user_input = self._ask_user_for_name(suggestion=suggestion, doc_id=doc_id)

                # -------------------------
                # Handle the user's answer.
                # -------------------------
                suggestion = StudentName("")

                if user_input == Action.DISCARD:
                    # Discard this document. It will be removed later.
                    print_info(f"Discarding document {doc_id}.")
                    return StudentName(user_input), StudentId("-1"), Action.NEXT, True
                elif user_input == Action.BACK:
                    print("Navigating back to previous document.")
                    return StudentName(default), StudentId(student_id), Action.BACK, False
                elif user_input == Action.NEXT:
                    print("Navigating to next document.")
                    return StudentName(default), StudentId(student_id), Action.NEXT, True
                elif self.students_ids:
                    if user_input in self.students_ids:
                        # This is in fact not a name, but a known student id,
                        # so convert it to a name.
                        name, student_id = self.students_ids[StudentId(user_input)], StudentId(user_input)
                        action = Action.NEXT
                    elif user_input in self.students_ids.values():
                        for _student_id, _name in self.students_ids.items():
                            if _name == user_input:
                                break
                        # noinspection PyUnboundLocalVariable
                        name = StudentName(_name)
                        # noinspection PyUnboundLocalVariable
                        student_id = StudentId(_student_id)
                        action = Action.NEXT
                    elif any((digit in user_input) for digit in string.digits):
                        # If `name` contains a digit, this is not a student name,
                        # but probably a misspelled student id!
                        print("Unknown ID.")
                        # So, suggest the more closely related existing id.
                        suggestion = self.students_ids[self._suggest_id(user_input)]
                    else:
                        print("Unknown name.")
                        suggestion = self._suggest_name(user_input)
                elif self.data_storage.config.students_list:
                    if user_input in self.data_storage.config.students_list:
                        action = Action.NEXT
                    else:
                        suggestion = self._suggest_name(user_input)
                elif user_input:
                    name = StudentName(user_input)

                if action is not None:
                    print(f"Name: {name}")
                    if not self._does_user_confirm():
                        action = None
        # Keep track of manually entered information (will be useful if the scan has to be run again later!)
        self.data_storage.store_additional_info(doc_id=doc_id, name=name, student_id=student_id)
        return name, student_id, action, True

    def review_name(self, doc_id: DocumentId) -> tuple[Action, bool]:
        """Review the document name.

        Return the action to do (go to next document, go back to previous one,
        or skip document), and a boolean which indicates if the document as been
        effectively reviewed.
        """
        first_page = self.data[doc_id].pages.get(Page(1))
        if first_page is None:
            print_error(f"No first page found for document {doc_id}!")
            return Action.NEXT, False

        # Ask user for name.
        student_name, student_id, action, reviewed = self.enter_name_and_id(
            doc_id, default=self.data[doc_id].name
        )

        # Store name and student id.
        self.data[doc_id].name = student_name
        self.data[doc_id].student_id = student_id
        self.data_storage.more_infos[doc_id] = (student_name, student_id)
        return action, reviewed

    def _suggest_id(self, incorrect_student_id: str) -> StudentId:
        """Print a suggestion of student name, based on provided id.

        The name associated with the most closely matching id will be suggested.
        """

        def _proximity(id_):
            return levenshtein_distance(incorrect_student_id, id_)

        suggestion: StudentId = min(self.students_ids, key=_proximity)
        print(f"Suggestion: {suggestion} → {self.students_ids[suggestion]} (write `ok` to validate it).")
        return suggestion

    def _suggest_name(self, incorrect_name: str) -> StudentName:
        """Print a suggestion of student name, based on provided name and existing ones."""
        incorrect_name = incorrect_name.lower()
        if self.students_ids:
            names = list(self.students_ids.values())
        elif self.data_storage.config.students_list:
            names = list(self.data_storage.config.students_list)
        else:
            return StudentName("")

        # Strategy 1: search if a name is almost the same.
        def _proximity(name_: StudentName):
            return levenshtein_distance(incorrect_name, name_)

        suggestion: StudentName = min(names, key=_proximity)

        if levenshtein_distance(incorrect_name, suggestion) <= 3:
            name = suggestion
        else:
            # Strategy 2: search if it is the start of a name.
            for name in names:
                if name.lower().startswith(incorrect_name):
                    break
            else:
                # Strategy 3: search if it is the start of any part of a name.
                for name in names:
                    if any(part.startswith(incorrect_name) for part in name.lower().split()):
                        break
                else:
                    # Strategy 4: search if it is a substring of any part of a name, or reciprocally.
                    for name in names:
                        if any(
                            (part in incorrect_name or incorrect_name in part)
                            for part in name.lower().split()
                        ):
                            break
                    else:
                        # Giving up...
                        name = StudentName("")
        return name

    @abstractmethod
    def _ask_user_for_name(self, suggestion: str, doc_id: DocumentId) -> str:
        """Ask the user to read the name."""
        ...

    @abstractmethod
    def _does_user_confirm(self):
        """Ask user to confirm its choice.

        Return True if user validate its choice, False else."""
        pass


class AbstractAnswersReviewer(ABC, metaclass=ABCMeta):
    """"""

    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = self.data_storage.data

    def review_answer(self, doc_id: DocumentId, page: Page) -> tuple[Action, bool]:
        """Review the student answers.

        Return the action to do (go to next document, go back to previous one,
        or skip document), and a boolean which indicates if the document as been
        effectively reviewed."""
        if self.data[doc_id].name == Action.DISCARD.value:
            # Skip this document.
            return Action.NEXT, False
        else:
            pic_data = self.data[doc_id].pages[page]
            action, reviewed = self.edit_answers(doc_id, page)
            self.data_storage.store_verified_pic(Path(pic_data.pic_path))
            return action, reviewed

    @abstractmethod
    def edit_answers(self, doc_id: DocumentId, page: Page) -> tuple[Action, bool]:
        """Call interactive editor to change answers.

        MCQ parser internal state `self.data` will be modified accordingly.

        Return the action to do (go to next document, go back to previous one,
        or skip document), and a boolean which indicates if the document as been
        effectively reviewed.
        """


# -----------------------
#      Main class
# =======================


class AllDataIssuesFixer(ABC):
    """Fix missing names and ambiguous answers issues."""

    def __init__(
        self,
        data_storage: DataHandler,
    ):
        from ptyx_mcq.scan.data_gestion.conflict_handling.config import Config

        self.data_storage = data_storage
        self.data = self.data_storage.data
        self.data_checker = DataChecker(data_storage)
        self.name_reviewer = Config.NamesReviewer(data_storage)
        self.answers_reviewer = Config.AnswersReviewer(data_storage)

    def get_names_to_review(self) -> dict[DocumentId, bool]:
        check_results = self.data_checker.run()
        return {doc_id: False for doc_id in check_results.unnamed_docs} | {
            doc_id: False for name, docs in check_results.duplicate_names.items() for doc_id in docs
        }

    def run(self, check_result: DataCheckResult) -> None:
        """Resolve conflicts manually: unknown student ID, ambiguous answer..."""
        # Each operation is independent of the other ones,
        # and user should be able to navigate between them.

        # The boolean indicates whether the document was reviewed.
        # TODO: No need to use a dict, since `reviewed` boolean is never used for `names_to_review`.
        #       A list should be enough.
        names_to_review: dict[DocumentId, bool] = {doc_id: False for doc_id in check_result.unnamed_docs}
        names_to_review.update(
            (doc_id, False) for name, docs in check_result.duplicate_names.items() for doc_id in docs
        )
        # The boolean indicates whether the document was reviewed.
        answers_to_review: dict[tuple[DocumentId, Page], bool] = {
            (doc, page): False for doc, page in check_result.ambiguous_answers
        }

        while len(names_to_review) + len(answers_to_review) > 0:
            position = 0
            print_warning("Conflicts detected.")
            if names_to_review:
                print_warning(
                    f"Names problems on {len(names_to_review)} document(s) {tuple(names_to_review)}."
                )
            if answers_to_review:
                print_warning(f"Ambiguous answers on {len(answers_to_review)} page(s).")
            while position < len(names_to_review) + len(answers_to_review):
                if position < len(names_to_review):
                    doc_id = list(names_to_review)[position]
                    action, reviewed = self.name_reviewer.review_name(doc_id)
                    names_to_review[doc_id] |= reviewed
                    # Verify that the new name has not induced a new conflict.
                    for _doc_id in self.data:
                        if _doc_id != doc_id and self.data[_doc_id].name == self.data[doc_id].name:
                            names_to_review[doc_id] = False
                else:
                    doc_id, page = list(answers_to_review)[position - len(names_to_review)]
                    action, reviewed = self.answers_reviewer.review_answer(doc_id, page)
                    answers_to_review[(doc_id, page)] |= reviewed
                if action == Action.NEXT:
                    position += 1
                elif action == Action.BACK:
                    position = max(0, position - 1)

            # Apply changes definitively.
            for doc_id in names_to_review:
                if self.data[doc_id].name == Action.DISCARD.value:
                    doc_data = self.data.pop(doc_id)
                    # For each page of the document, add corresponding picture path
                    # to skipped paths list.
                    # If `mcq scan` is run again, those pictures will be skipped.
                    for pic_data in doc_data.pages.values():
                        self.data_storage.store_skipped_pic(Path(pic_data.pic_path))
                    # Remove also all corresponding data files.
                    self.data_storage.remove_doc_files(doc_id)

            # The new entered names might have induced new conflicts.
            names_to_review = self.get_names_to_review()
            answers_to_review = {key: reviewed for key, reviewed in answers_to_review.items() if not reviewed}


class DataChecker:
    """Check for missing data."""

    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = self.data_storage.data

    def run(self) -> DataCheckResult:
        # First, complete missing information with previous scan data, if any.
        for doc_id, (student_name, student_id) in self.data_storage.more_infos.items():
            try:
                self.data[doc_id].name = student_name
                self.data[doc_id].student_id = student_id
            except KeyError:
                print_warning(f"Document {doc_id} not found... Maybe it was discarded previously?")

        # The students name to ID mapping may have been updated
        # (using `mcq fix` for example).
        # Let's try again to get names from ID.
        for doc_id, doc_data in self.data.items():
            if doc_data.name == "":
                doc_data.name = self.data_storage.config.students_ids.get(
                    doc_data.student_id, StudentName("")
                )

        print("Searching for unnamed documents...")
        unnamed_docs = self.get_unnamed_docs()
        print(f"{len(unnamed_docs)} unnamed document(s) found." if unnamed_docs else "OK")

        print("Searching for duplicate names...")
        duplicate_names = self.find_duplicate_names()
        print(f"{len(duplicate_names)} conflict(s) found." if duplicate_names else "OK")

        print("Searching for ambiguous answers...")
        ambiguous_answers = self.find_ambiguous_answers()
        print(f"{len(ambiguous_answers)} page(s) to verify." if ambiguous_answers else "OK")

        return DataCheckResult(
            unnamed_docs=unnamed_docs, duplicate_names=duplicate_names, ambiguous_answers=ambiguous_answers
        )

    def get_unnamed_docs(self) -> list[DocumentId]:
        """Get the (sorted) list of all unnamed documents ids."""
        # Sorting documents is cheap and make testing easier.
        return sorted(doc_id for doc_id, doc_data in self.data.items() if doc_data.name == "")

    def find_duplicate_names(self) -> DuplicateNamesDict:
        """Detect if several documents have the same student name.

        Return a dictionary associating each conflicting name with the corresponding documents.
        """
        seen_names: dict[StudentName, DocumentId] = {}
        duplicate_names: dict[StudentName, list[DocumentId]] = {}
        # Sorting documents is cheap and make testing easier.
        for doc_id in sorted(self.data):
            name = self.data[doc_id].name
            # Be careful to not count unnamed documents as duplicates!
            if name:
                if name in seen_names:
                    duplicate_names.setdefault(name, [seen_names[name]]).append(doc_id)
                    # matching_doc_id = seen_names[name]
                    # matching_doc_data = self.data[matching_doc_id]
                else:
                    seen_names[name] = doc_id
        return duplicate_names

    def find_ambiguous_answers(self) -> AmbiguousPagesList:
        # The answers are ambiguous and were not already manually verified in a previous scan.
        return [
            (doc_id, page)
            for doc_id, doc_data in self.data.items()
            for page, pic_data in doc_data.pages.items()
            if pic_data.needs_review and Path(pic_data.pic_path) not in self.data_storage.verified
        ]


# FIXME: the following function is not used anymore, remove it?


def report_data_issues(check_result: DataCheckResult) -> None:
    for doc_id in check_result.unnamed_docs:
        print_warning(f"• No student name for document {doc_id}.")
    for name, doc_ids in check_result.duplicate_names.items():
        print_warning(f"• Same student name {name!r} on documents {','.join(map(str, doc_ids))}.")
