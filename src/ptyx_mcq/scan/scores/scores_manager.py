from typing import TYPE_CHECKING

from ptyx.pretty_print import TermColors, term_color
from ptyx_mcq.scan.data import Question
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
    ScoringFunc,
)
from ptyx_mcq.tools.parse_config.subtypes import StudentId, StudentName

if TYPE_CHECKING:
    from ptyx_mcq.scan import MCQPictureParser


class SkipQuestion(Exception):
    """Error raised to skip a question. It should be intercepted by the caller."""


class ScoresManager:
    """
    Main class for scores' management.
    """

    def __init__(self, mcq_parser: "MCQPictureParser"):
        self.mcq_parser = mcq_parser
        # The scores of all the scanned students' works.
        # See the property `.class_scores` and its docstring for more information.
        self.work_scores: dict[tuple[StudentName, StudentId], float] = {}

    @property
    def max_score(self):
        """Return the maximal global score that can be obtained, considering the questions' weight."""
        return self.mcq_parser.config.max_score

    def _get_raw_question_score(self, question: Question) -> tuple[float, ScoreData]:
        """
        Get the score obtained for the question, as well as a `ScoreData` instance with the question's main parameters.

        The question's weight is not taken in consideration here.
        """
        q = question.question_num
        cfg = self.mcq_parser.config

        mode = cfg.mode.get(q, cfg.mode["default"])
        if mode == ScoringStrategy.SKIP:
            # Can be used to skip a bogus question which would have been detected only after the exam.
            raise SkipQuestion

        try:
            func: ScoringFunc = getattr(ScoringImplementations, mode)
        except AttributeError:
            raise AttributeError(f"Unknown evaluation mode: {mode!r}.")

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

        ans_data = AnswersData(checked=answered, correct=correct_ones, all=all_answers)
        scores_data = ScoreData(
            correct=float(cfg.correct.get(q, cfg.correct["default"])),
            skipped=float(cfg.skipped.get(q, cfg.skipped["default"])),
            incorrect=float(cfg.incorrect.get(q, cfg.incorrect["default"])),
        )
        earn = func(ans_data, scores_data)

        floor = cfg.floor.get(q, cfg.floor["default"])
        assert floor is None or isinstance(floor, (float, int))
        if floor is not None and earn < floor:
            earn = floor
        ceil = cfg.ceil.get(q, cfg.ceil["default"])
        assert ceil is None or isinstance(ceil, (float, int))
        if ceil is not None and earn > ceil:
            earn = ceil
        return earn, scores_data

    def calculate_scores(self) -> None:
        """
        Calculate and update the scores for all students.
        """
        cfg = self.mcq_parser.config
        for doc_id, doc in self.mcq_parser.scan_data.used_docs_index.items():
            print(f"Test {doc_id} - {doc.student_name}")
            for q, question in doc.questions.items():
                try:
                    earn, score_data = self._get_raw_question_score(question)
                except SkipQuestion:
                    print(f"Question {q} skipped...")
                    continue

                if earn == score_data.correct:
                    color = TermColors.GREEN
                elif earn == score_data.incorrect:
                    color = TermColors.RED
                else:
                    color = TermColors.YELLOW
                print("-  " + term_color(f"Rating (Q{q}): {earn:g}", color=color))
                # Don't forget to include the weight of the question to calculate the global score.
                earn *= float(cfg.weight.get(q, cfg.weight["default"]))
                question.score = earn
        self.work_scores = {
            (doc.student_name, doc.student_id): doc.score
            for doc in self.mcq_parser.scan_data
            if doc.score is not None
        }

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
        """Print the scores on the terminal."""
        TerminalScoresPrinter(self).run()

    def generate_csv_file(self) -> None:
        """Generate a CSV file with the scores."""
        CsvScoresPrinter(self).run()

    def generate_xlsx_file(self) -> None:
        """Generate a XSLX file with the scores."""
        ExcelScoresPrinter(self).run()
