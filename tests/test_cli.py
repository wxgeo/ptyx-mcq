"""
Test mcq command line interface.

Test new, make and scan subcommands.
"""

import csv
import tempfile
from os import listdir
from pathlib import Path

import pytest
from PIL import ImageDraw
from pdf2image import convert_from_path  # type: ignore

from ptyx_mcq.cli import main
from ptyx_mcq.parameters import CELL_SIZE_IN_CM
from ptyx_mcq.scan.color import Color, RGB
from ptyx_mcq.scan.tools import round
from ptyx_mcq.tools.config_parser import (
    Configuration,
    is_answer_correct,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    StudentId,
    StudentName,
)

DPI = 200
PX_PER_CM = DPI / 2.54
PX_PER_MM = PX_PER_CM / 10
CELL_SIZE_IN_PX = CELL_SIZE_IN_CM * PX_PER_CM
STUDENTS = {
    StudentId("12345678"): StudentName("Jean Dupond"),
    StudentId("34567890"): StudentName("Martin De La Tour"),
}
MAX_ID_LEN = max(len(student_id) for student_id in STUDENTS)


def xy2ij(x: float, y: float) -> tuple[int, int]:
    """Convert (x, y) position (mm) to pixels (i,j).

    (x, y) is the position from the bottom left of the page in mm,
    as given by LaTeX.
    (i, j) is the position in pixels, where i is the line and j the
    column, starting from the top left of the image.
    """
    # Top left square is printed at 1 cm from the left and the top of the sheet.
    i = (297 - y) * PX_PER_MM  # 29.7 cm - 1 cm = 28.7 cm (A4 sheet format = 21 cm x 29.7 cm)
    j = x * PX_PER_MM
    return round(i), round(j)


def _fill_checkbox(draw: ImageDraw.ImageDraw, pos: tuple, size: float, color: RGB = Color.red) -> None:
    i, j = xy2ij(*pos)
    # Draw a blue square around the box (for debugging purpose).
    draw.rectangle((j, i, j + size, i + size), fill=color)


def write_student_id(draw: ImageDraw.ImageDraw, student_id: str, config: Configuration) -> None:
    assert config.id_table_pos is not None
    x0, y0 = config.id_table_pos
    for i, digit in enumerate(student_id.zfill(MAX_ID_LEN)):
        x_shift = 10 + 10 * int(digit)
        y_shift = 10 * i
        _fill_checkbox(
            draw,
            (x0 + x_shift * CELL_SIZE_IN_CM, y0 - y_shift * CELL_SIZE_IN_CM),
            CELL_SIZE_IN_PX,
            color=Color.blue,
        )


def simulate_answer(pics: list, config: Configuration):
    """Amend answer sheet with scores and correct answers.

    `data` is the dict generated when the answer sheet is scanned.
    `ID` is the ID of answer sheet.
    """
    # Convert cell size from cm to pixels
    students_ids = list(STUDENTS)
    boxes = config.boxes
    for i, (doc_id, data) in enumerate(boxes.items()):
        if i >= len(students_ids):
            print(f"Warning: {len(boxes)} documents but only {len(students_ids)} students.")
            break
        for page, page_data in data.items():
            # Each document has 2 pages, but page 2 should be empty as there are only 2 questions.
            # So we must skip the empty page.
            pic = pics[2 * i]
            # Drawing context
            draw = ImageDraw.Draw(pic)
            write_student_id(draw, students_ids[i], config)
            for q_a, pos in page_data.items():
                q_str, a_str = q_a[1:].split("-")
                q = OriginalQuestionNumber(int(q_str))
                a = OriginalAnswerNumber(int(a_str))
                if is_answer_correct(q, a, config, doc_id):
                    _fill_checkbox(draw, pos, CELL_SIZE_IN_PX)
    return pics[: 2 * len(students_ids)]


def write_students_id_to_csv(path: Path, students: dict[StudentId, StudentName]) -> Path:
    with open(csv_path := path / "students.csv", "w", newline="") as csvfile:
        csv.writer(csvfile).writerows(students.items())
    return csv_path


def read_students_scores(path: Path) -> dict[StudentName, str]:
    students: dict[StudentName, str] = {}
    # TODO : store scores outside of .scan folder, in a RESULTS folder !
    with open(score_path := path / ".scan/scores.csv") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            match row:
                case ["Name", "Score"]:
                    pass  # Header row
                case [name, score]:
                    students[StudentName(name)] = score
                case _:
                    raise ValueError(f"Invalid format in '{score_path}': {row!r}.")
    return students


@pytest.mark.slow
def test_many_docs():
    NUMBER_OF_DOCUMENTS = 40
    with tempfile.TemporaryDirectory() as _parent:
        parent = Path(_parent)
        path = parent / "mcq"
        # Test mcq new
        main(["new", str(path)])
        assert "new.ptyx" in listdir(path)
        # Test mcq make
        main(["make", str(path), "-n", str(NUMBER_OF_DOCUMENTS)])
        assert "new.pdf" in listdir(path)
        assert "new-corr.pdf" in listdir(path)


def test_cli() -> None:
    NUMBER_OF_DOCUMENTS = 2
    # Set `USE_TMP_DIR` to `False` to make the debugging easier.
    USE_TMP_DIR = False
    # If `USE_TMP_DIR` is set to `False`, all the generated content can
    # be retrieved in /tmp/mcq.
    if not USE_TMP_DIR:
        from shutil import rmtree

        rmtree("/tmp/mcq", ignore_errors=True)
        rmtree("/tmp/mcq-2", ignore_errors=True)
    # Make a temporary directory
    with tempfile.TemporaryDirectory() as _parent:
        print(10 * "=")
        print(_parent)
        print(10 * "=")
        parent = Path(_parent) if USE_TMP_DIR else Path("/tmp")
        write_students_id_to_csv(parent, STUDENTS)

        path = parent / "mcq"

        # ----------------
        # Test `mcq new`
        # ----------------
        main(["new", str(path)])
        assert "new.ptyx" in listdir(path)

        with open(path / "new.ptyx") as ptyxfile:
            ptyxfile_content = ptyxfile.read()
        with open(path / "new.ptyx", "w") as ptyxfile:
            assert "\nid format" in ptyxfile_content
            ptyxfile.write(ptyxfile_content.replace("\nid format", "\nids=../students.csv\nid format"))

        # ----------------
        # Test `mcq make`
        # ----------------
        main(["make", str(path), "-n", str(NUMBER_OF_DOCUMENTS)])
        assert "new.pdf" in listdir(path)
        assert "new-corr.pdf" in listdir(path)
        # TODO: assert "new.all.pdf" in listdir(path)

        config = Configuration.load(path / "new.ptyx.mcq.config.json")
        for student_id in STUDENTS:
            assert student_id in config.students_ids, (repr(student_id), repr(config.students_ids))
            assert config.students_ids[student_id] == STUDENTS[student_id]

        # -----------------------------------
        # Test `mcq new PATH -i INCLUDE_PATH`
        # -----------------------------------
        path2 = parent / "mcq-2"
        main(["new", str(path2), "-i", str(path / "questions")])
        assert "new.ptyx" in listdir(path)
        assert not (path2 / "questions").exists()

        # --------------------------------------
        # Test `mcq make PATH --correction-only`
        # --------------------------------------

        main(["make", str(path2), "--correction-only"])
        with open(path2 / ".compile/new/new-corr.tex", encoding="utf8") as f:
            assert f.read().count(r"\checkBox") > 10  # TODO: give a precise number.

        # ----------------
        # Test `mcq scan`
        # ----------------
        images = convert_from_path(path / "new.pdf", dpi=DPI, output_folder=path)
        images = simulate_answer(images, config)
        assert len(images) / 2 == min(NUMBER_OF_DOCUMENTS, len(STUDENTS))
        scan_path = path / "scan"
        scan_path.mkdir(exist_ok=True)
        images[0].save(scan_path / "simulate-scan.pdf", save_all=True, append_images=images[1:])
        main(["scan", str(path)])

        # TODO : store scores outside of .scan folder, in a RESULTS folder !
        students_scores: dict[StudentName, str] = read_students_scores(path)
        for score in students_scores.values():
            assert abs(float(score) - 20) < 1e-10, repr(score)  # Maximal score
        assert set(students_scores) == set(STUDENTS.values()), repr(students_scores)

        # -----------------
        # Test `mcq update`
        # -----------------
        STUDENTS[StudentId("12345678")] = StudentName(new_student_name := "Julien Durand")
        csv_path = write_students_id_to_csv(parent, STUDENTS)
        with open(csv_path) as f:
            assert new_student_name in f.read()
        # Invert correct and incorrect answers for testing update.
        with open(path / "questions/question1.ex", encoding="utf8") as f:
            file_content = f.read()
        with open(path / "questions/question1.ex", "w", encoding="utf8") as f:
            f.write(file_content.replace("+", "§").replace("-", "+").replace("§", "-"))

        main(["update-config", str(path)])
        config = Configuration.load(path / "new.ptyx.mcq.config.json")
        assert new_student_name in config.students_ids.values(), repr(path / "new.ptyx.mcq.config.json")
        main(["scan", str(path)])
        old_students_scores = students_scores.copy()
        students_scores = read_students_scores(path)
        # Names are not updated yet, since they are stored in `.scandata` cache files.
        # Updating names requires clearing cache
        for student in students_scores:
            if student != new_student_name:
                assert float(students_scores[student]) < float(old_students_scores[student])
            else:
                # TODO: add configuration option for default value.
                assert students_scores[student] == "ABI"
        # Names are  Updating names requires clearing cache,
        # through `--reset` option.
        main(["scan", "--reset", str(path)])
        students_scores = read_students_scores(path)
        assert set(students_scores) == set(STUDENTS.values()), repr(students_scores)

        # ----------------
        # Test `mcq clear`
        # ----------------
        paths_to_be_removed = [
            ".scan",
            "new.pdf",
            "new.ptyx.mcq.config.json",
        ]
        paths_to_be_kept = [
            "new.ptyx",
            "scan/simulate-scan.pdf",
        ]
        for endpath in paths_to_be_removed + paths_to_be_kept:
            assert (pth := path / endpath).exists(), pth
        main(["clear", str(path)])
        for endpath in paths_to_be_removed:
            assert not (pth := path / endpath).exists(), pth
        for endpath in paths_to_be_kept:
            assert (pth := path / endpath).exists(), pth


if __name__ == "__main__":
    test_cli()
