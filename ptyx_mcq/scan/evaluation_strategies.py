from dataclasses import dataclass
from math import nan, isnan

from ptyx_mcq.tools.config_parser import OriginalAnswerNumber


@dataclass
class AnswersData:
    checked: set[OriginalAnswerNumber]
    correct: set[OriginalAnswerNumber]
    all: set[OriginalAnswerNumber]

    @property
    def unchecked(self):
        return self.all - self.checked

    @property
    def incorrect(self):
        return self.all - self.correct


@dataclass
class ScoreData:
    correct: float
    skipped: float
    incorrect: float = nan

    def __post_init__(self):
        if isnan(self.incorrect):
            self.incorrect = -self.correct


class EvaluationStrategies:
    """This class provides a collection of evaluation strategies.

     Those will be used to calculate the score for each question.

    Each strategy should be defined as a static method within the `EvaluationStrategies` class,
    with two required parameters:
    - the answers data (of type `AnswersData`),
    - the scores configuration (of type `ScoreData`).

    Note that only static methods within the `EvaluationStrategies` class will be recognized as
    evaluation strategies, so you may safely define auxiliary class methods without interfering.
    """

    @classmethod
    def get_all_strategies(cls) -> list[str]:
        return [name for name, func in vars(cls).items() if isinstance(func, staticmethod)]

    @classmethod
    def formatted_info(cls, name):
        lines = []
        for line in getattr(cls, name).__doc__.strip().split("\n"):
            lines.append("│ " + line.strip())
        return "\n".join(lines)

    @staticmethod
    def some(answers: AnswersData, score: ScoreData) -> float:
        """Return the maximal score if any of the correct answers and no incorrect answer is checked.

        If an incorrect answer is checked, return minimal score."""
        # Answer is valid if and only if :
        # (proposed ≠ ∅ and proposed ⊆ correct) or (proposed = correct = ∅)
        ok = (answers.checked and answers.checked.issubset(answers.correct)) or (
            not answers.checked and not answers.correct
        )
        if ok:
            return score.correct
        elif not answers.checked:
            return score.skipped
        else:
            return score.incorrect

    @staticmethod
    def all(answers: AnswersData, score: ScoreData) -> float:
        """Return the maximal score if all the correct answers are checked, else give the minimal score."""
        ok = answers.checked == answers.correct
        if ok:
            return score.correct
        elif not answers.checked:
            return score.skipped
        else:
            return score.incorrect

    @staticmethod
    def proportional(answers: AnswersData, score: ScoreData) -> float:
        """Returned score is a pondered mean of minimal and maximal scores.

        Minimal and maximal scores are defined respectively in the header of the ptyx file
        with `correct` and `incorrect` keywords.

        The score returned is (1 - k) * minimal_score + k * maximal_score,
        where k is the proportion of correct answers (i.e. boxes left blank when proposed answer
        was incorrect and boxes checked when proposed answer was correct).
        """
        count_ok = len(answers.checked & answers.correct) + len(answers.unchecked & answers.incorrect)
        proportion = count_ok / len(answers.all)
        return round(score.incorrect + proportion * (score.correct - score.incorrect), 2)

    @staticmethod
    def partial_answers(answers: AnswersData, score: ScoreData) -> float:
        """Return 0 if an incorrect answer was checked, else the proportion of correct answers."""
        return _partial_answers(answers, score)

    @staticmethod
    def partial_answers_quadratic(answers: AnswersData, score: ScoreData) -> float:
        """Return 0 if an incorrect answer was checked, else the squared proportion of correct answers."""
        return _partial_answers(answers, score, exposant=2)

    @staticmethod
    def correct_minus_incorrect(answers: AnswersData, score: ScoreData) -> float:
        """If the proportion of correct answers is less than 0.5, as is typically the case,
        return the difference between the proportion of correctly checked answers
        and the proportion of incorrectly checked answers.

        Otherwise, if the proportion of correct answers is greater than 0.5,
        return the difference between the proportion of correctly unchecked answers
        and the proportion of incorrectly unchecked answers.

        The idea behind this algorithm is that, if the proportion of correct answers is greater than 0.5,
        the exercise's difficulty lies in determining which answers should be left unchecked.
        """
        return _correct_minus_incorrect(answers, score)

    @staticmethod
    def correct_minus_incorrect_quadratic(answers: AnswersData, score: ScoreData) -> float:
        """Same algorithm as for `correct_minus_incorrect`, but the result is squared.

        This makes very unlikely for a student answering randomly to gain significant score.
        """
        return _correct_minus_incorrect(answers, score, exposant=2)


def _checked_among_correct_proportion(answers: AnswersData) -> float:
    """Return the proportion of checked answers among correct ones.

    If there was no correct answer, return 1.0 if no answer was checked, 0.0 else.
    """
    if len(answers.correct) == 0:
        return float(len(answers.checked) == 0)
    return len(answers.checked & answers.correct) / len(answers.correct)


def _partial_answers(answers: AnswersData, score: ScoreData, exposant=1.0) -> float:
    """Return 0 if an incorrect answer was checked, else the proportion of correct answers."""
    if answers.checked & answers.incorrect:
        return score.incorrect
    else:
        return round(_checked_among_correct_proportion(answers) ** exposant * score.correct, 2)


def _correct_proportion(answers: AnswersData) -> float:
    """Return the proportion of correct answers."""
    assert len(answers.all) > 0
    proportion = len(answers.checked) / len(answers.all)
    assert 0 <= proportion <= 1
    return proportion


def _correct_minus_incorrect(answers: AnswersData, score: ScoreData, exposant=1.0) -> float:
    ratio_correctly_checked = max(
        0.0,
        (len(answers.checked & answers.correct) - len(answers.checked & answers.incorrect))
        / len(answers.correct),
    )
    ratio_correctly_unchecked = max(
        0.0,
        (len(answers.unchecked & answers.incorrect) - len(answers.unchecked & answers.correct))
        / len(answers.incorrect),
    )
    if _correct_proportion(answers) <= 0.5:
        assert ratio_correctly_unchecked < ratio_correctly_checked <= 1
        ratio = ratio_correctly_checked
    else:
        assert ratio_correctly_checked < ratio_correctly_unchecked <= 1
        ratio = ratio_correctly_unchecked
    assert ratio <= 1
    return max(0.0, round(ratio**exposant * score.correct, 2))
