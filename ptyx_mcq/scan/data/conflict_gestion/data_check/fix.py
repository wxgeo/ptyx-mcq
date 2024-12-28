import string
from abc import ABC, abstractmethod, ABCMeta
from contextlib import AbstractContextManager
from enum import StrEnum
from pathlib import Path

from ptyx.shell import print_warning, print_error, print_info

from ptyx_mcq.scan.data.analyze.checkboxes import CheckboxAnalyzeResult
from ptyx_mcq.scan.data.conflict_gestion.data_check.check import DataChecker, DataCheckResult
from ptyx_mcq.scan.data import ScanData
from ptyx_mcq.scan.data.students import Student
from ptyx_mcq.tools.config_parser import DocumentId, StudentName, StudentId, PageNum
from ptyx_mcq.tools.math import levenshtein_distance


class Action(StrEnum):
    NEXT = ">"
    BACK = "<"
    DISCARD = "/"


class AbstractDocHeaderDisplayer(AbstractContextManager, ABC):
    """Abstract class."""

    # noinspection PyUnusedLocal
    @abstractmethod
    def __init__(self, data_storage: ScanData, doc_id: DocumentId): ...

    @abstractmethod
    def display(self) -> None:
        """Display document header."""


class AbstractNamesReviewer(ABC, metaclass=ABCMeta):
    """Abstract class."""

    def __init__(self, scan_data: ScanData):
        self.scan_data = scan_data
        self.students_ids = self.scan_data.config.students_ids

    def enter_name_and_id(
        self, doc_id: DocumentId, default: StudentName
    ) -> tuple[StudentName, StudentId, Action]:
        """Ask user to read student name and id for current document.

        Return the given student name (empty if no name was provided),
        the student id (same remark) and the action to do
        (go to next document, go back to previous one, or skip document).
        """
        name = StudentName("")
        student_id = StudentId("")
        action: Action | None = None

        suggestion = default

        from ptyx_mcq.scan.data.conflict_gestion.config import Config

        with Config.DocHeaderDisplayer(self.scan_data, doc_id) as doc_header_displayer:
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
                    return StudentName(user_input), StudentId("-1"), Action.NEXT
                elif user_input == Action.BACK:
                    print("Navigating back to previous document.")
                    return StudentName(default), StudentId(student_id), Action.BACK
                elif user_input == Action.NEXT:
                    print("Navigating to next document.")
                    return StudentName(default), StudentId(student_id), Action.NEXT
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
                elif self.scan_data.config.students_list:
                    if user_input in self.scan_data.config.students_list:
                        action = Action.NEXT
                    else:
                        suggestion = self._suggest_name(user_input)
                elif user_input:
                    name = StudentName(user_input)

                if action is not None:
                    print(f"Name: {name}")
                    if not self._does_user_confirm():
                        action = None
        return name, student_id, action

    def review_name(self, doc_id: DocumentId) -> Action:
        """Review the document name.

        Return the action to do (go to next document, go back to previous one,
        or skip document).
        """
        doc = self.scan_data.index[doc_id]
        if doc.first_page is None:
            print_error(f"No first page found for document {doc_id}!")
            return Action.NEXT

        # Ask user for name.
        student_name, student_id, action = self.enter_name_and_id(
            doc_id, default=self.scan_data.index[doc_id].student_name
        )

        # Store name and student id.
        self.scan_data.index[doc_id].first_page.pic.student = Student(name=student_name, id=student_id)
        return action

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
        elif self.scan_data.config.students_list:
            names = list(self.scan_data.config.students_list)
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

    def __init__(self, scan_data: ScanData):
        self.scan_data = scan_data

    def review_answer(self, doc_id: DocumentId, page_num: PageNum) -> Action:
        """Review the student answers.

        Return the action to do (go to next document, go back to previous one,
        or skip document), and a boolean which indicates if the document as been
        effectively reviewed."""
        doc = self.scan_data.index[doc_id]
        if doc.student_name == Action.DISCARD.value:
            # Skip this document.
            return Action.NEXT
        else:
            action, changes = self.edit_answers(doc_id, page_num)
            # Apply changes.
            doc.pages[page_num].pic.update_checkboxes_states(changes)
            return action

    @abstractmethod
    def edit_answers(self, doc_id: DocumentId, page_num: PageNum) -> tuple[Action, CheckboxAnalyzeResult]:
        """Call interactive editor to change answers.

        MCQ parser internal state `self.data` will be modified accordingly.

        Return the action to do (go to next document, go back to previous one,
        or skip document), and a boolean which indicates if the document as been
        effectively reviewed.
        """


# -----------------------
#      Main class
# =======================


class DefaultAllDataIssuesFixer:
    """Fix missing names and ambiguous answers issues."""

    def __init__(
        self,
        scan_data: ScanData,
    ):
        from ptyx_mcq.scan.data.conflict_gestion.config import Config

        self.scan_data = scan_data
        self.data_checker = DataChecker(scan_data)
        self.name_reviewer = Config.NamesReviewer(scan_data)
        self.answers_reviewer = Config.AnswersReviewer(scan_data)

    def run(self, check_result: DataCheckResult) -> None:
        """Resolve conflicts manually: unknown student ID, ambiguous answer..."""
        # Each operation is independent of the other ones,
        # and user should be able to navigate between them.

        while (
            len(names_to_review := check_result.names_to_review)
            + len(answers_to_review := check_result.ambiguous_answers)
            > 0
        ):
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
                    action = self.name_reviewer.review_name(doc_id)
                    # # Verify that the new name has not induced a new conflict.
                    # for other_doc_id in self.scan_data.index:
                    #     if (
                    #         other_doc_id != doc_id
                    #         and self.scan_data.index[other_doc_id].student_name
                    #         == self.scan_data.index[doc_id].student_name
                    #     ):
                    #         if doc_id not in names_to_review:
                    #             names_to_review.append(doc_id)
                else:
                    doc_id, page = list(answers_to_review)[position - len(names_to_review)]
                    action = self.answers_reviewer.review_answer(doc_id, page)
                if action == Action.NEXT:
                    position += 1
                elif action == Action.BACK:
                    position = max(0, position - 1)

            # # Apply changes definitively.
            # for doc_id in names_to_review:
            #     if self.scan_data.index[doc_id].student_name == Action.DISCARD.value:
            #         doc_data = self.scan_data.pop(doc_id)
            #         # For each page of the document, add corresponding picture path
            #         # to skipped paths list.
            #         # If `mcq scan` is run again, those pictures will be skipped.
            #         for pic_data in doc_data.pages.values():
            #             self.scan_data.store_skipped_pic(Path(pic_data.pic_path))
            #         # Remove also all corresponding data files.
            #         self.scan_data.remove_doc_files(doc_id)

            # The new entered names might have induced new conflicts.
            check_result = self.data_checker.run()
