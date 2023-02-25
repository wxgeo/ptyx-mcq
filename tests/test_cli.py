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
from ptyx_mcq.tools.config_parser import load, is_answer_correct, Configuration

DPI = 200
PX_PER_CM = DPI / 2.54
PX_PER_MM = PX_PER_CM / 10
CELL_SIZE_IN_PX = CELL_SIZE_IN_CM * PX_PER_CM
STUDENTS = {"12345678": "Jean Dupond", "34567890": "Martin De La Tour"}
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


def _fill_checkbox(
    draw: ImageDraw.ImageDraw, pos: tuple, size: float, color: RGB = Color.red
) -> None:
    i, j = xy2ij(*pos)
    # Draw a blue square around the box (for debugging purpose).
    draw.rectangle((j, i, j + size, i + size), fill=color)


def write_student_id(draw: ImageDraw.ImageDraw, student_id: str, config: Configuration) -> None:
    x0, y0 = config["id_table_pos"]
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
    boxes = config["boxes"]
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
                q, a = map(int, q_a[1:].split("-"))
                if is_answer_correct(q, a, config, doc_id):
                    _fill_checkbox(draw, pos, CELL_SIZE_IN_PX)
    return pics[:2*len(students_ids)]


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
    # Make a temporary directory
    with tempfile.TemporaryDirectory() as _parent:
        print(10 * "=")
        print(_parent)
        print(10 * "=")
        parent = Path(_parent) if USE_TMP_DIR else Path("/tmp")
        with open(parent / "students.csv", "w", newline="") as csvfile:
            csv.writer(csvfile).writerows(STUDENTS.items())

        path = parent / "mcq"

        # Test mcq new
        main(["new", str(path)])
        assert "new.ptyx" in listdir(path)

        with open(path / "new.ptyx") as ptyxfile:
            ptyxfile_content = ptyxfile.read()
        with open(path / "new.ptyx", "w") as ptyxfile:
            assert "\nid format" in ptyxfile_content
            ptyxfile.write(ptyxfile_content.replace("\nid format", "\nids=../students.csv\nid format"))

        # Test mcq make
        main(["make", str(path), "-n", str(NUMBER_OF_DOCUMENTS)])
        assert "new.pdf" in listdir(path)
        assert "new-corr.pdf" in listdir(path)
        # TODO: assert "new.all.pdf" in listdir(path)

        config = load(path / "new.ptyx.mcq.config.json")
        for student_id in STUDENTS:
            assert student_id in config["students_ids"], (repr(student_id), repr(config["students_ids"]))
            assert config["students_ids"][student_id] == STUDENTS[student_id]

        # Test mcq scan
        images = convert_from_path(path / "new.pdf", dpi=DPI, output_folder=path)
        images = simulate_answer(images, config)
        assert len(images)/2 == min(NUMBER_OF_DOCUMENTS, len(STUDENTS))
        scan_path = path / "scan"
        scan_path.mkdir(exist_ok=True)
        images[0].save(scan_path / "simulate-scan.pdf", save_all=True, append_images=images[1:])
        main(["scan", str(path)])

        students: set[str] = set()
        # TODO : store scores outside of .scan folder, in a RESULTS folder !
        with open(path / ".scan/scores.csv") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row[0] != "Name":
                    assert abs(float(row[1]) - 20) < 1e-10, repr(row)  # Maximal score
                    students.add(row[0])
        assert students == set(STUDENTS.values()), repr(students)


if __name__ == "__main__":
    test_cli()
