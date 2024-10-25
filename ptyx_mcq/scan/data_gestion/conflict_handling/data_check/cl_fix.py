from subprocess import Popen, CompletedProcess

from numpy import ndarray

from ptyx.shell import print_warning

from ptyx_mcq.scan.data_gestion.conflict_handling.data_check.fix import (
    Action,
    AbstractNamesReviewer,
    AbstractAnswersReviewer,
    AbstractDocHeaderDisplayer,
)
from ptyx_mcq.scan.data_gestion.data_handler import DataHandler
from ptyx_mcq.tools.misc import copy_docstring
from ptyx_mcq.tools.rgb import Color, RGB
from ptyx_mcq.scan.data_gestion.document_data import (
    Page,
    DetectionStatus,
    RevisionStatus,
    PicData,
)
from ptyx_mcq.scan.picture_analyze.image_viewer import ImageViewer
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    ApparentQuestionNumber,
    apparent2real,
    ApparentAnswerNumber,
    StudentName,
    StudentId,
)


# --------------------------
#       Review names
# ==========================


class ClDocHeaderDisplayer(AbstractDocHeaderDisplayer):
    def __init__(self, data_storage: DataHandler, doc_id: DocumentId):
        array = data_storage.get_matrix(doc_id, Page(1))
        width = array.shape[1]
        self.viewer = ImageViewer(array=array[0 : int(3 / 4 * width), :])
        self.process: CompletedProcess | Popen | None = None

    def __enter__(self):
        return self

    def display(self) -> None:
        """Display the top of the scanned document.

        Don't relaunch process if it is still alive.
        """
        # `self.process.poll() is not None`: it means that the process is dead.
        if (
            self.process is None
            or isinstance(self.process, CompletedProcess)
            or self.process.poll() is not None
        ):
            self.process = self.viewer.display(wait=False)

    def __exit__(self, exc_type, exc_value, traceback):
        assert self.process is not None and not isinstance(self.process, CompletedProcess)
        self.process.terminate()


class ClNamesReviewer(AbstractNamesReviewer):
    """Command line names' reviewer.

    Fix missing names issues."""

    ASK_FOR_NAME = "Name, ID or command: "
    PRESS_ENTER = "-- Press ENTER --"
    CORRECT_Y_N = "Is it correct? (Y/n)"

    @copy_docstring(AbstractNamesReviewer._suggest_name)
    def _suggest_name(self, incorrect_name: str) -> StudentName:
        name = super()._suggest_name(incorrect_name=incorrect_name)
        if name:
            print(f"Suggestion: {name} (write `ok` to validate it).")
        return name

    @copy_docstring(AbstractNamesReviewer._ask_user_for_name)
    def _ask_user_for_name(self, suggestion: str, doc_id: DocumentId) -> str:
        """Ask the user to read the name."""
        user_input = input("Name, ID or command: ").strip()
        if user_input.lower() == "ok":
            user_input = suggestion
        return StudentName(user_input)

    @copy_docstring(AbstractNamesReviewer._does_user_confirm)
    def _does_user_confirm(self) -> bool:
        """Ask user to confirm its choice.

        Return True if user validate its choice, False else."""
        while (is_correct := input(self.CORRECT_Y_N).lower()) not in (
            "y",
            "yes",
            "",
            "n",
            "no",
        ):
            pass
        return is_correct not in ("n", "no")

    @copy_docstring(AbstractNamesReviewer.enter_name_and_id)
    def enter_name_and_id(
        self, doc_id: DocumentId, default: StudentName
    ) -> tuple[StudentName, StudentId, Action, bool]:
        print(f"[Document {doc_id}]")
        print(f"Please verify student name or ID (current name: {default!r}).")
        print("Please read the name on the picture which will be displayed now.")
        input(self.PRESS_ENTER)
        print(
            "Write below the actual student name or ID, or write one of the following commands:\n"
            f"   - Use {Action.DISCARD} to discard (remove) this document.\n"
            f"   - Use {Action.BACK} to go back to previous document.\n"
            f"   - Use {Action.NEXT} ou `ok` to go to next document, keeping current name."
        )
        return super().enter_name_and_id(doc_id, default)


# --------------------------
#      Review answers
# ==========================


class ClAnswersReviewer(AbstractAnswersReviewer):
    """Command line answers' reviewer.

    Fix ambiguous answers issues."""

    ENTER_COMMAND = (
        f"Write {Action.BACK}, {Action.NEXT}, or just press ENTER to review current document's answers:"
    )
    IS_CORRECT = "Is this correct ? [(y)es/(N)o]"
    SELECT_QUESTION = "Write a question number, or 0 to escape:"
    EDIT_ANSWERS = "Add or remove answers (Example: +2 -1 -4 to add answer 2, and remove answers 1 et 4):"

    @copy_docstring(AbstractAnswersReviewer.edit_answers)
    def edit_answers(self, doc_id: DocumentId, page: Page) -> tuple[Action, bool]:
        config = self.data_storage.config
        pic_data = self.data[doc_id].pages[page]
        answered = pic_data.answered
        revision_status = pic_data.revision_status
        print_warning(f"Ambiguous answers for student {self.data[doc_id].name} (doc {doc_id}, page: {page}).")
        print(
            f"Tip: write {Action.BACK} to go back to previous document,"
            f" or {Action.NEXT} to jump directly to next document."
        )
        match input(self.ENTER_COMMAND):
            case Action.BACK:
                return Action.BACK, False
            case Action.NEXT:
                return Action.NEXT, False

        while True:
            process = self.display_page_with_detected_answers(doc_id, page)
            if input(self.IS_CORRECT).lower() in ("y", "yes"):
                break
            while (q_str := input(self.SELECT_QUESTION)) != "0":
                try:
                    q0 = ApparentQuestionNumber(int(q_str))
                    q, _ = apparent2real(q0, None, config, doc_id)
                    if q not in answered:
                        # print(f"{answered=} {page=} {doc_id=}\n")
                        raise IndexError(rf"Invalid question number: {q0}")

                    checked = answered[q]
                    a_str = input(self.EDIT_ANSWERS)
                    for val in a_str.split():
                        op, a0 = val[0], ApparentAnswerNumber(int(val[1:]))
                        q, a = apparent2real(q0, a0, config, doc_id)
                        if op == "+":
                            if a in checked:
                                print(f"Warning: {a0} already in answers.")
                            else:
                                checked.add(a)
                                revision_status[(q, a)] = RevisionStatus.MARKED_AS_CHECKED
                        elif op == "-":
                            if a in checked:
                                checked.remove(a)
                                revision_status[(q, a)] = RevisionStatus.MARKED_AS_UNCHECKED
                            else:
                                print(f"Warning: {a0} not in answers.")
                        else:
                            print(f"Invalid operation: {val!r}")
                except ValueError:
                    print("Invalid value.")
                    continue
                except (KeyError, IndexError):
                    # import traceback
                    # import sys
                    # traceback.print_exc(file=sys.stdout)
                    print("Invalid number.")
                finally:
                    process.terminate()
                    process = self.display_page_with_detected_answers(doc_id, page)
        process.terminate()
        return Action.NEXT, True

    def display_page_with_detected_answers(self, doc_id: DocumentId, page: Page) -> Popen:
        """Display the page with its checkboxes colored following their detection status."""
        array = self.data_storage.get_matrix(doc_id, page)
        pic_data = self.data[doc_id].pages[page]
        return self.display_picture_with_detected_answers(array, pic_data)

    @staticmethod
    def display_picture_with_detected_answers(array: ndarray, pic_data: PicData) -> Popen:
        """Display the picture of the MCQ with its checkboxes colored following their detection status."""
        viewer = ImageViewer(array=array)
        colors: dict[DetectionStatus | RevisionStatus, RGB] = {
            DetectionStatus.CHECKED: Color.blue,
            DetectionStatus.PROBABLY_CHECKED: Color.green,
            DetectionStatus.PROBABLY_UNCHECKED: Color.magenta,
            DetectionStatus.UNCHECKED: Color.pink,
            RevisionStatus.MARKED_AS_CHECKED: Color.cyan,
            RevisionStatus.MARKED_AS_UNCHECKED: Color.red,
        }
        thicknesses: dict[DetectionStatus | RevisionStatus, int] = {
            DetectionStatus.CHECKED: 2,
            DetectionStatus.PROBABLY_CHECKED: 5,
            DetectionStatus.PROBABLY_UNCHECKED: 5,
            DetectionStatus.UNCHECKED: 2,
            RevisionStatus.MARKED_AS_CHECKED: 5,
            RevisionStatus.MARKED_AS_UNCHECKED: 5,
        }
        for (q, a), (i, j) in pic_data.positions.items():
            status = pic_data.revision_status.get((q, a), pic_data.detection_status[(q, a)])
            viewer.add_rectangle(
                (i, j), pic_data.cell_size, color=colors[status], thickness=thicknesses[status]
            )
        return viewer.display(wait=False)
