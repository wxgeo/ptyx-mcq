import string
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw
from numpy import ndarray

from ptyx_mcq.scan.color import Color, RGB
from ptyx_mcq.scan.data_handler import DataHandler
from ptyx_mcq.scan.document_data import Page, DetectionStatus, RevisionStatus, PicData, DocumentData
from ptyx_mcq.scan.image_viewer import ImageViewer
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    ApparentQuestionNumber,
    apparent2real,
    ApparentAnswerNumber,
    StudentName,
    StudentId,
    OriginalQuestionNumber,
)
from ptyx_mcq.tools.io_tools import print_framed_msg, print_warning, print_success, print_error, print_info


class MissingQuestion(RuntimeError):
    """Error raised when some questions where not seen when scanning all data."""


class MissingConfigurationData(RuntimeError):
    """Error raised when some configuration data is missing."""


class ConflictSolver:
    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = data_storage.data

    def resolve_conflicts(self, debug=False):
        """Resolve conflicts manually: unknown student ID, ambiguous answer..."""
        print("Searching for duplicate names...")
        self.review_missing_names()
        # Reviewing missing names must have been done *BEFORE* searching for duplicate pages,
        # to detect conflicts in duplicate pages (same document with different names).
        print("Searching for duplicate pages...")
        self.review_duplicate_pages()
        print("Searching for missing names...")
        self.review_duplicate_names()
        print("Searching for ambiguous answers...")
        self.review_answers(debug=debug)
        print("Test for data integrity...")
        self.test_integrity()

    def review_missing_names(self) -> None:
        # First, complete missing information with previous scan data, if any.
        for doc_id, (student_name, student_id) in self.data_storage.more_infos.items():
            self.data[doc_id].name = student_name
            self.data[doc_id].student_id = student_id
        to_remove: list[DocumentId] = []
        # Search for any missing information remaining.
        for doc_id, doc_data in self.data.items():
            if doc_data.name == "":
                first_page = doc_data.pages.get(Page(1))
                if first_page is None:
                    print_warning(f"No first page found for document {doc_id}!")
                    return
                else:
                    print(f"Picture's path: '{first_page.pic_path}'.")
                print_warning(f"No student name for document {doc_id}.")
                student_name, student_id = self.enter_name_and_id(doc_id)
                if student_name == "/":
                    # Remove this document.
                    to_remove.append(doc_id)
                doc_data.name = student_name
                doc_data.student_id = student_id
                self.data_storage.more_infos[doc_id] = (student_name, student_id)
        for doc_id in to_remove:
            doc_data = self.data.pop(doc_id)
            # For each page of the document, add corresponding picture path
            # to skipped paths list.
            # If `mcq scan` is run again, those pictures will be skipped.
            for pic_data in doc_data.pages.values():
                self.data_storage.store_skipped_pic(Path(pic_data.pic_path))
            # Remove also all corresponding data files.
            self.data_storage.remove_doc_files(doc_id)

    def review_duplicate_names(self) -> None:
        name_to_doc_id: dict[StudentName, DocumentId] = {}
        for doc_id, doc_data in self.data.items():
            name = doc_data.name
            if name in name_to_doc_id:
                matching_doc_id = name_to_doc_id[name]
                matching_doc_data = self.data[matching_doc_id]
                print_warning(f"Same student name on documents {doc_id} and {matching_doc_id}: {name!r}.")
                self.resolve_duplicate_name_conflict(name, doc_id, name_to_doc_id)
                self.data_storage.more_infos[doc_id] = doc_data.name, doc_data.student_id
                self.data_storage.more_infos[matching_doc_id] = (
                    matching_doc_data.name,
                    matching_doc_data.student_id,
                )
            name_to_doc_id[name] = doc_id

    def resolve_duplicate_name_conflict(
        self, name: StudentName, doc_id: DocumentId, name_to_doc_id: dict[StudentName, DocumentId]
    ) -> None:
        while name in name_to_doc_id:
            print(f"Test #{name_to_doc_id[name]}: {name}")
            print(f"Test #{doc_id}: {name}")
            print_framed_msg(
                f"Error : 2 tests for same student ({name}) !\n"
                "Please modify at least one name (enter nothing to keep a name)."
            )
            # Remove twin name from name2doc_id, and get the corresponding previous test ID.
            doc_id0 = name_to_doc_id.pop(name)
            # Ask for a new name.
            name0, student_id0 = self.enter_name_and_id(doc_id0, default=name)
            # Update all infos.
            name_to_doc_id[name0] = doc_id0
            self.data[doc_id0].name = name0
            self.data[doc_id0].student_id = student_id0
            # Ask for a new name for new test too.
            name = self.enter_name_and_id(doc_id, default=name)[0]

        assert name, "Name should not be empty at this stage !"
        name_to_doc_id[name] = doc_id
        self.data[doc_id].name = name

    def enter_name_and_id(self, doc_id: DocumentId, default: str = "") -> tuple[StudentName, StudentId]:
        array = self.data_storage.get_matrix(doc_id, Page(1))
        width = array.shape[1]
        viewer = ImageViewer(array=array[0 : int(3 / 4 * width), :])
        id_name_dict = self.data_storage.config.students_ids
        student_id = ""
        print("Name can not be read automatically.")
        print("Please read the name on the picture which will be displayed now.")
        input("-- Press ENTER --")
        #    subprocess.run(["display", "-resize", "1920x1080", pic_path])
        # TODO: use first letters of students name to find student.
        # (ask again if not found, or if several names match first letters)
        process = None
        name = ""
        while name == "":
            # Don't relaunch process if it is still alive.
            # (process.poll() is not None for dead processes.)
            if process is None or process.poll() is not None:
                process = viewer.display(wait=False)
            name = input("Student name or ID (or / to skip this document):").strip()
            if name == "/":
                # Skip this document
                return StudentName("/"), StudentId("-1")
            if not name:
                name = default
            elif id_name_dict:
                if name in id_name_dict:
                    name, student_id = id_name_dict[StudentId(name)], name
                elif any((digit in name) for digit in string.digits):
                    # This is not a student name !
                    print("Unknown ID.")
                    name = ""
            if name:
                print("Name: %s" % name)
                if input("Is it correct ? (Y/n)").lower() not in ("y", "yes", ""):
                    name = ""
        assert process is not None
        process.terminate()
        name = StudentName(name)
        student_id = StudentId(student_id)
        # Keep track of manually entered information (will be useful if the scan has to be run again later !)
        self.data_storage.store_additional_info(doc_id=doc_id, name=name, student_id=student_id)
        return name, student_id

    def review_answers(self, debug=False):
        for doc_id, doc_data in self.data.items():
            for page, pic_data in doc_data.pages.items():
                if pic_data.needs_review and Path(pic_data.pic_path) not in self.data_storage.verified:
                    # The answers are ambiguous and were not already manually verified in a previous scan.
                    print(f"Picture's path: '{pic_data.pic_path}'.")
                    print_warning(f"Ambiguous answers for student {doc_data.name}.")
                    self.edit_answers(doc_id, page)
                    self.data_storage.store_verified_pic(Path(pic_data.pic_path))
                elif debug:
                    print(f"Picture's path: '{pic_data.pic_path}'.")
                    print_success(f"All answers successfully read for student {doc_data.name}.")
                    self.display_page_with_detected_answers(doc_id, page)

    def display_page_with_detected_answers(self, doc_id: DocumentId, page: Page) -> subprocess.Popen:
        """Display the page with its checkboxes colored following their detection status."""
        array = self.data_storage.get_matrix(doc_id, page)
        pic_data = self.data[doc_id].pages[page]
        return self.display_picture_with_detected_answers(array, pic_data)

    @staticmethod
    def display_picture_with_detected_answers(array: ndarray, pic_data: PicData) -> subprocess.Popen:
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

    def edit_answers(self, doc_id: DocumentId, page: Page) -> None:
        """Interactive editor to change answers."""
        config = self.data_storage.config
        pic_data = self.data[doc_id].pages[page]
        # m = self.data_handler.get_matrix(doc_id, page)
        # cell_size = pic_data.cell_size
        answered = pic_data.answered
        revision_status = pic_data.revision_status
        print("Please verify answers detection:")
        input("-- Press ENTER --")

        while True:
            process = self.display_page_with_detected_answers(doc_id, page)
            if input("Is this correct ? [(y)es/(N)o]").lower() in ("y", "yes"):
                break
            while (q_str := input("Write a question number, or 0 to escape:")) != "0":
                try:
                    q0 = ApparentQuestionNumber(int(q_str))
                    q, _ = apparent2real(q0, None, config, doc_id)
                    if q not in answered:
                        # print(f"{answered=} {page=} {doc_id=}\n")
                        raise IndexError(rf"Invalid question number: {q0}")

                    checked = answered[q]
                    a_str = input(
                        "Add or remove answers "
                        "(Example: +2 -1 -4 to add answer 2, and remove answers 1 et 4):"
                    )
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

    def display_first_page_head(self, doc_id: DocumentId) -> subprocess.CompletedProcess | subprocess.Popen:
        """Display the head of the first page, to be able to read student name manually."""
        array = self.data_storage.get_matrix(doc_id, Page(1))
        width = array.shape[1]
        viewer = ImageViewer(array=array[0 : int(3 / 4 * width), :])
        return viewer.display(wait=False)

    def test_integrity(self) -> None:
        """For every test:
        - all pages must have been scanned,
        - all questions must have been seen."""
        missing_questions: dict[DocumentId, list[OriginalQuestionNumber]] = {}
        missing_pages: dict[DocumentId, list[Page]] = {}
        ordering = self.data_storage.config.ordering
        for doc_id in self.data:
            try:
                doc_ordering = ordering[doc_id]
            except KeyError:
                raise MissingConfigurationData(
                    f"No configuration data found for document #{doc_id}.\n"
                    "Maybe you recompiled the ptyx file in the while ?\n"
                    f"(Launching `mcq make -n {max(self.data)}` might fix it.)"
                )
            if questions_diff := sorted(set(doc_ordering["questions"]) - set(self.data[doc_id].answered)):
                missing_questions[doc_id] = questions_diff
            # ", ".join(str(q) for q in unseen_questions)
            # All tests may not have the same number of pages, since
            # page breaking will occur at a different place for each test.
            if pages_diff := sorted(
                set(self.data_storage.config.boxes[doc_id]) - set(self.data[doc_id].pages)
            ):
                missing_pages[doc_id] = pages_diff

        if missing_pages:
            print_warning("Pages missing:")
            for doc_id in sorted(missing_pages):
                print_warning(
                    f"    • Test {doc_id}: page(s) {', '.join(str(page) for page in missing_pages[doc_id])}"
                )
            if not missing_questions:
                print_info(
                    "Missing pages seem to be empty, since all questions"
                    " and answers have been successfully recovered yet."
                )
        if missing_questions:
            print_error("Questions missing!")
            for doc_id in sorted(missing_questions):
                print_error(
                    f"    • Test {doc_id}: question(s) {', '.join(str(page) for page in missing_questions[doc_id])}"
                )

        if missing_questions:
            # Don't raise an error for pages not found (only a warning in log)
            # if all questions were found, this was probably empty pages.
            raise MissingQuestion("Questions not seen ! (Look at message above).")
        else:
            print_success("Data integrity successfully verified.")

    def review_duplicate_pages(self) -> None:
        # List of all ids alias.
        # conflicts: dict[tuple[DocumentId, Page], list[DocumentId]] = self.data_storage.duplicates_alias
        tmp_doc_id: DocumentId
        doc_data: DocumentData
        page: Page
        pic_data: PicData
        print(list(self.data))
        for tmp_doc_id, doc_data in self.data_storage.get_all_temporary_ids().items():
            assert tmp_doc_id < 0
            assert len(doc_data.pages) == 1, (tmp_doc_id, list(doc_data.pages))
            print(tmp_doc_id, list(doc_data.pages))
            for page, pic_data in doc_data.pages.items():
                print(list(self.data))
                scanned_id = pic_data.doc_id
                conflicting_pic_data = self.data[scanned_id].pages[page]
                same_data = (
                    pic_data.detection_status == conflicting_pic_data.detection_status
                    and pic_data.name == conflicting_pic_data.name
                )
                if same_data or self._keep_previous_version(scanned_id, tmp_doc_id, page):
                    # Same name and same answers detected for both versions,
                    # so we can safely ignore the new version, and remove `tmp_dic_id` data.
                    print(list(self.data))
                    self.data.pop(tmp_doc_id)
                    self.data_storage.remove_doc_files(tmp_doc_id)
                    if same_data:
                        print_warning(f"Page {page} of document {scanned_id} was scanned twice.")
                        print_info("Same information found on both versions, so we ignore it.")
                else:
                    # Replace the data and the files corresponding to this page
                    # by the new version (corresponding to id `tmp_doc_id`).
                    # Warning: All other data of document `scanned_id` (i.e. the data for all the other pages)
                    # must be kept unchanged!
                    self.data[scanned_id].pages[page] = self.data.pop(tmp_doc_id).pages[page]
                    data_dir = self.data_storage.dirs.data
                    # Replace the WEBP image.
                    (data_dir / f"{tmp_doc_id}-{page}.webp").replace(data_dir / f"{scanned_id}-{page}.webp")
                    # Create an updated `scanned_id` .scandata file.
                    # Warning: we can't simply replace it with the `tmp_doc_id` .scandata file, because it would only
                    # contain the data corresponding to this page, not the other ones.
                    self.data_storage.write_scandata_file(scanned_id)

    def _keep_previous_version(self, scanned_doc_id: DocumentId, temp_doc_id: DocumentId, page: Page) -> bool:
        """Ask user what to do is two versions of the same page exist, with conflicting data.

        It may mean the page has been scanned twice with different scan qualities, but it could
        also indicate a more serious problem (for example, tests with the same ID
        have been given to different students !).
        Anyway, we should signal the problem to the user, and ask him
        what he wants to do.
        """
        pic_path1 = self.data[scanned_doc_id].pages[page].pic_path
        pic_path1 = self.data_storage.absolute_pic_path(pic_path1)
        pic_path2 = self.data[temp_doc_id].pages[page].pic_path
        pic_path2 = self.data_storage.absolute_pic_path(pic_path2)
        # assert isinstance(pic_path1, str)
        # assert isinstance(pic_path2, str)
        print_warning(
            f"Page {page} of test #{scanned_doc_id} seen twice " f'(in "{pic_path1}" and "{pic_path2}") !'
        )
        print("Choose which version to keep:")
        input("-- Press ENTER --")
        action = ""

        while action not in ("1", "2"):
            self._display_duplicates(scanned_doc_id, temp_doc_id, page)
            print("What must we do ?")
            print("- Keep only 1st one (1)")
            print("- Keep only 2nd one (2)")
            print("If you want to see the pictures again, juste press ENTER.")
            action = input("Answer: ")

        return action == "1"

    def _display_duplicates(self, scanned_doc_id: DocumentId, temp_doc_id: DocumentId, page: Page) -> None:
        # im1 = Image.open(pic_path1)
        # im2 = Image.open(pic_path2)
        im1 = self.data_storage.get_pic(scanned_doc_id, page)
        im2 = self.data_storage.get_pic(temp_doc_id, page)
        dst = Image.new("RGB", (im1.width + im2.width, height := min(im1.height, im2.height)))
        dst.paste(im1, (0, 0))
        dst.paste(im2, (im1.width, 0))
        ImageDraw.Draw(dst).line([(im1.width, 0), (im1.width, height)], fill=Color.blue)

        ImageViewer(image=dst).display()
        # TODO: Use ImageViewer.display() from image_viewer.py
        #  We must refactor ImageViewer() first to accept PIL Image as argument.
        #
        # with tempfile.TemporaryDirectory() as tmpdir:
        #     dst.save(path := Path(tmpdir) / "test.png")
        #     subprocess.run(["feh", "-F", str(path)], check=True)
        #     input("-- pause --")
