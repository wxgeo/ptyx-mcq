from typing import TYPE_CHECKING

from ptyx.pretty_print import TermColors, term_color
from ptyx_mcq.scan.scores.printers import (
    TerminalScoresPrinter,
    ExcelScoresPrinter,
    CsvScoresPrinter,
)
from ptyx_mcq.tools.evaluation_strategies import (
    AnswersData,
    ScoreData,
    ScoringImplementations,
    ScoringStrategy,
)
from ptyx_mcq.tools.parse_config.subtypes import StudentId, StudentName

if TYPE_CHECKING:
    from ptyx_mcq.scan.scan_doc import MCQPictureParser


class ScoresManager:
    def __init__(self, mcq_parser: "MCQPictureParser"):
        self.mcq_parser = mcq_parser
        # The scores of all the scanned students' works.
        # See the property `.class_scores` and its docstring for more information.
        self.work_scores: dict[tuple[StudentName, StudentId], float] = {}

    @property
    def max_score(self):
        return self.mcq_parser.config.max_score

    def calculate_scores(self) -> None:
        cfg = self.mcq_parser.config
        default_mode = cfg.mode["default"]
        default_weight = cfg.weight["default"]
        default_correct = cfg.correct["default"]
        default_incorrect = cfg.incorrect["default"]
        default_skipped = cfg.skipped["default"]
        default_floor = cfg.floor["default"]
        default_ceil = cfg.ceil["default"]

        for doc_id, doc in self.mcq_parser.scan_data.used_docs_index.items():
            print(f"Test {doc_id} - {doc.student_name}")
            for q, question in doc.questions.items():
                answered = {answer.answer_num for answer in question if answer.checked}
                correct_ones = {answer.answer_num for answer in question if answer.is_correct}
                neutralized_ones = {answer.answer_num for answer in question if answer.neutralized}
                all_answers = {answer.answer_num for answer in question}

                # Neutralized answers must be removed from each set of answers.
                # (Typically, neutralized answers are answers which were detected faulty during or after the
                # examination).
                answered -= neutralized_ones
                correct_ones -= neutralized_ones
                all_answers -= neutralized_ones

                mode = cfg.mode.get(q, default_mode)

                if mode == ScoringStrategy.SKIP:
                    # Used mostly to skip bogus questions.
                    print(f"Question {q} skipped...")
                    continue

                try:
                    func = getattr(ScoringImplementations, mode)
                except AttributeError:
                    raise AttributeError(f"Unknown evaluation mode: {mode!r}.")

                ans_data = AnswersData(checked=answered, correct=correct_ones, all=all_answers)
                scores_data = ScoreData(
                    correct=float(cfg.correct.get(q, default_correct)),
                    skipped=float(cfg.skipped.get(q, default_skipped)),
                    incorrect=float(cfg.incorrect.get(q, default_incorrect)),
                )
                earn = func(ans_data, scores_data)

                floor = cfg.floor.get(q, default_floor)
                assert floor is None or isinstance(floor, (float, int))
                if floor is not None and earn < floor:
                    earn = floor
                ceil = cfg.ceil.get(q, default_ceil)
                assert ceil is None or isinstance(ceil, (float, int))
                if ceil is not None and earn > ceil:
                    earn = ceil

                if earn == scores_data.correct:
                    color = TermColors.GREEN
                elif earn == scores_data.incorrect:
                    color = TermColors.RED
                else:
                    color = TermColors.YELLOW
                print("-  " + term_color(f"Rating (Q{q}): {earn:g}", color=color))
                # Don't forget to include the weight of the question to calculate the global score.
                earn *= float(cfg.weight.get(q, default_weight))
                # Don't use weight for per question score, since it would make success rates
                # harder to compare.
                question.score = earn

        # default = self.mcq_parser.config.default_score
        # self.class_scores = {
        #     (student_name, student_id): default
        #     for student_id, student_name in self.mcq_parser.config.students_ids.items()
        # }
        self.work_scores = {
            (doc.student_name, doc.student_id): doc.score
            for doc in self.mcq_parser.scan_data
            if doc.score is not None
        }
        # self.class_scores.update(self.work_scores)

    @property
    def class_scores(self) -> dict[tuple[StudentName, StudentId], float | str]:
        """
        The scores of the class.

        In addition to all the scanned work scores, a default score is added to absent students,
        so most of the time, you should use it instead of the raw `.work_scores` attribute.

        The default score may not be numeric (it may be "ABS" for example, depending on the configuration).

        Note that all scores are kept, even for students which are not listed in the configuration file.
        The last case is rare, but may occur if a student was present at the exam, but have resigned in the while,
        and the configuration file is updated then.

        To sum up, `class_scores` = `work_scores` + absents.
        """
        default = self.mcq_parser.config.default_score
        defaults = {
            (student_name, student_id): default
            for student_id, student_name in self.mcq_parser.config.students_ids.items()
        }
        return defaults | self.work_scores

    def print_scores(self) -> None:
        TerminalScoresPrinter(self).run()

    def generate_csv_file(self) -> None:
        CsvScoresPrinter(self).run()

    def generate_xlsx_file(self) -> None:
        ExcelScoresPrinter(self).run()
