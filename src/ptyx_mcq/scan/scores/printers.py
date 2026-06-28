import csv
import math
from abc import abstractmethod, ABC
from collections import Counter
from typing import TYPE_CHECKING, Callable

from openpyxl import Workbook
from openpyxl.chart import Reference, BarChart
from openpyxl.chart.layout import ManualLayout, Layout
from openpyxl.styles import PatternFill, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet

from ptyx.pretty_print import TermColors, bold, green, red, term_color, yellow, print_info

if TYPE_CHECKING:
    from ptyx_mcq.scan.scores.scores_manager import ScoresManager

STATISTIC_INFO = {"mean": "AVERAGE", "min": "MIN", "max": "MAX"}


class ScoresPrinter(ABC):
    def __init__(self, parent: "ScoresManager"):
        super().__init__()
        self.parent = parent

    @staticmethod
    def _convert(num: float | str, factor=1.0):
        if isinstance(num, float):
            num = round(factor * num, 2)
        return num

    @abstractmethod
    def run(self): ...


class TerminalScoresPrinter(ScoresPrinter):
    def run(self) -> None:
        min_score: float = math.inf
        max_score: float = -math.inf
        print()
        print(term_color(f"SCORES (/{self.parent.max_score:g}):", color=TermColors.CYAN))
        for (student_name, student_id), score in sorted(self.parent.class_scores.items()):
            score = self._convert(score)
            if isinstance(score, (float, int)):
                if score < min_score:
                    min_score = score
                if score > max_score:
                    max_score = score
            print(f" - {student_name}: {self._convert(score)}")
        if self.parent.work_scores:
            mean = round(sum(self.parent.work_scores.values()) / len(self.parent.work_scores), 2)
            print(yellow("Mean: " + bold(f"{mean:g}") + f"/{self.parent.max_score:g}"))
            print(f"Min: {red(min_score)} - Max: {green(max_score)}")
        else:
            print("No score found !")
        print()


class SheetsScoresPrinter(ScoresPrinter, ABC):
    def _write_scores(self, writerow: Callable) -> None:
        # max_score is the maximal theoretical score, not the highest actually obtained.
        max_score = self.parent.max_score
        writerow(("ID", "Name", f"Score/{max_score:g}", "Score/20", "Score/100"))
        for (student_name, student_id), score in sorted(self.parent.class_scores.items()):
            # TODO: Add ability to change the notation system.
            writerow(
                [
                    student_id,
                    student_name,
                    self._convert(score),
                    self._convert(score, factor=20 / max_score) if max_score else 0,
                    self._convert(score, factor=100 / max_score) if max_score else 0,
                ]
            )


class CsvScoresPrinter(SheetsScoresPrinter):
    def run(self) -> None:
        scores_path = self.parent.mcq_parser.scan_data.files.csv_scores
        with open(scores_path, "w", newline="") as csvfile:
            self._write_scores(writerow=csv.writer(csvfile).writerow)
        print_info(f'Results stored in "{scores_path}"')


class ExcelScoresPrinter(SheetsScoresPrinter):
    def __init__(self, parent: "ScoresManager"):
        super().__init__(parent)
        self.workbook = Workbook()

    def run(self) -> None:
        wb = self.workbook
        # grab the active worksheet
        sheet: Worksheet | None = wb.active
        assert sheet is not None
        sheet.title = "Resume"
        self._write_scores(writerow=sheet.append)

        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)

        # Row Stripes: Light Blue background
        row_stripe_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        # ---------------------------------------

        # 2. Iterate and apply Direct Formatting (for LibreOffice)
        # We iterate from row 1 (header) to max_row
        for row in sheet.iter_rows(min_row=1, max_row=sheet.max_row, max_col=sheet.max_column):
            for cell in row:
                assert cell.row is not None
                # Apply Header Style
                if cell.row == 1:
                    cell.fill = header_fill
                    cell.font = header_font
                # Apply Striped Row Style (Even rows)
                elif cell.row % 2 == 0:
                    cell.fill = row_stripe_fill

        tab = Table(displayName="Table1", ref=f"A1:{get_column_letter(sheet.max_column)}{sheet.max_row}")

        # Add a default style with striped rows and banded columns
        style = TableStyleInfo(
            name="TableStyleMedium9",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=True,
        )
        # noinspection PyTypeChecker
        tab.tableStyleInfo = style
        sheet.add_table(tab)

        # Fix columns' widths.
        sheet.column_dimensions["A"].width = 1.23 * max(
            len(student_id) for _, student_id in self.parent.class_scores
        )
        sheet.column_dimensions["B"].width = 1.23 * max(
            len(student_name) for student_name, _ in self.parent.class_scores
        )
        sheet.append([])

        # Append some statistics concerning the students' scores.
        n = len(self.parent.class_scores)
        for legend, formula in STATISTIC_INFO.items():
            sheet.append([legend.capitalize(), ""] + [f"={formula}({col}2:{col}{n + 1})" for col in "CDE"])

        # Add a chart to illustrate scores' distribution.
        self._append_chart(wb)
        wb.save(self.parent.mcq_parser.scan_data.files.xlsx_scores)

    # Remove the LineProperties import — not needed for bar fills

    def _append_chart(self, wb: Workbook) -> None:
        """Append a chart representing the scores' distribution as a new sheet."""
        ws = wb.create_sheet(title="Scores Distribution")

        score_counts = Counter(
            round(score) for score in self.parent.class_scores.values() if isinstance(score, (int, float))
        )

        ws.append(["Score", "Count"])
        for score in range(math.ceil(self.parent.max_score) + 1):
            ws.append([score, score_counts.get(score, 0)])

        n = ws.max_row
        counts_ref = Reference(ws, min_col=2, min_row=2, max_row=n)
        scores_ref = Reference(ws, min_col=1, min_row=2, max_row=n)

        # ✅ Use BarChart instead of LineChart
        chart = BarChart()
        chart.type = "col"  # vertical columns (not horizontal bars)
        chart.grouping = "clustered"
        chart.title = "Scores Distribution"
        chart.x_axis.title = "Score"
        chart.y_axis.title = "Number of Students"

        chart.add_data(counts_ref, titles_from_data=False)
        chart.set_categories(scores_ref)

        chart.legend = None
        chart.width = 21
        chart.height = 9
        chart.layout = Layout(
            manualLayout=ManualLayout(x=0.005, y=0.05, w=0.75, h=0.8, xMode="factor", yMode="factor")
        )

        # ✅ Set bar fill to solid red (replaces LineProperties)
        chart.series[0].graphicalProperties.solidFill = "FA8C84"
        chart.series[0].graphicalProperties.line.solidFill = "FF0000"  # bar border color

        # ✅ Control spacing between bars (lower % = narrower gaps, default is 150)
        chart.gapWidth = 50

        ws.add_chart(chart, "E2")
