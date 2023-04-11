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


class ScoresStrategies:
    @classmethod
    def get_modes_list(cls) -> list[str]:
        assert hasattr(cls, current_func := "get_modes_list"), "Please update function name here."
        return [name for name in vars(cls) if not name.startswith("_") and name != current_func]

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
    def partial_answers_linear(answers: AnswersData, score: ScoreData) -> float:
        """Return 0 if an incorrect answer was checked, else the proportion of correct answers"""
        if answers.checked & answers.incorrect:
            return score.incorrect
        else:
            return round(_checked_among_correct_proportion(answers) * score.correct, 2)

    @staticmethod
    def partial_answers_quadratic(answers: AnswersData, score: ScoreData) -> float:
        if answers.checked & answers.incorrect:
            return score.incorrect
        else:
            return round(_checked_among_correct_proportion(answers) ** 2 * score.correct, 2)

    @staticmethod
    def correct_minus_incorrect_linear(answers: AnswersData, score: ScoreData) -> float:
        ratio = max(
            0.0,
            (len(answers.checked & answers.correct) - len(answers.checked & answers.incorrect))
            / len(answers.correct),
        )
        assert 0 <= ratio <= 1
        return round(ratio * score.correct, 2)

    @staticmethod
    def correct_minus_incorrect_quadratic(answers: AnswersData, score: ScoreData) -> float:
        ratio = max(
            0.0,
            (len(answers.checked & answers.correct) - len(answers.checked & answers.incorrect))
            / len(answers.correct),
        )
        assert 0 <= ratio <= 1
        return round(ratio**2 * score.correct, 2)


def _checked_among_correct_proportion(answers: AnswersData) -> float:
    """Return the proportion of checked answers among correct ones.

    If there was no correct answer, return 1.0 if no answer was checked, 0.0 else.
    """
    if len(answers.correct) == 0:
        return float(len(answers.checked) == 0)
    return len(answers.checked & answers.correct) / len(answers.correct)
