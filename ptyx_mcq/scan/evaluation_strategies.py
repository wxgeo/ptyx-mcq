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

    @property
    def correctly_answered(self):
        return self.correct & self.checked | self.incorrect & self.unchecked

    @property
    def incorrectly_answered(self):
        return self.all - self.correctly_answered


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

    @staticmethod
    def some(answers: AnswersData, score: ScoreData) -> float:
        """If any of the correct answers have been selected and no incorrect answers
        have been selected, the function returns the maximal score.
        Otherwise, it returns the minimal score.

        The maximal score and minimal score are defined in the header of the ptyx file
        using the keywords "correct" and "incorrect", respectively."""
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
        """This function returns either the maximal score or the minimal score,
        depending on whether all correct answers are checked or not.

        If all correct answers are checked, the function returns the maximal score.
        Otherwise, it returns the minimal score."""
        ok = answers.checked == answers.correct
        if ok:
            return score.correct
        elif not answers.checked:
            return score.skipped
        else:
            return score.incorrect

    @staticmethod
    def proportional(answers: AnswersData, score: ScoreData) -> float:
        """The score returned by this function is calculated as a weighted average
        of the minimal and maximal scores.

        The minimal and maximal scores are specified in the header of the ptyx file
        using the keywords "correct" and "incorrect", respectively.

        The formula for the calculated score is `(1 - k) * minimal_score + k * maximal_score`,
        where k is the proportion of correct answers.
        This means that if all answers are correct, the score will be equal to the maximal score;
        if all answers are incorrect, the score will be equal to the minimal score;
        and if some answers are correct and others are incorrect, the score will be somewhere in between.

        To determine the value of k, the algorithm looks at the answers provided and checks
        which boxes were left blank when the proposed answer was incorrect,
        and which boxes were checked when the proposed answer was correct.
        The proportion of correct answers is then calculated as the ratio of the number of correct answers
        to the total number of answers.

        Overall, this function evaluates the quality of the answers provided, based on the specified
        minimal and maximal scores, and the proportion of correct answers.
        """
        count_ok = len(answers.checked & answers.correct) + len(answers.unchecked & answers.incorrect)
        proportion = count_ok / len(answers.all)
        return round(score.incorrect + proportion * (score.correct - score.incorrect), 2)

    @staticmethod
    def partial_answers(answers: AnswersData, score: ScoreData) -> float:
        """Return 0 if an incorrect answer was checked,
        else the proportion of correct answers."""
        return _partial_answers(answers, score)

    @staticmethod
    def partial_answers_quadratic(answers: AnswersData, score: ScoreData) -> float:
        """Return 0 if an incorrect answer was checked,
        else the squared proportion of correct answers."""
        return _partial_answers(answers, score, exposant=2)

    @staticmethod
    def correct_minus_incorrect(answers: AnswersData, score: ScoreData) -> float:
        """If the proportion of correct answers is less than 0.5, as is typically the case,
        return the difference between the proportion of correctly checked answers
        and the proportion of incorrectly checked answers.

        Otherwise, if the proportion of correct answers is greater than 0.5,
        return the difference between the proportion of correctly unchecked answers
        and the proportion of incorrectly unchecked answers.

        The idea behind this algorithm is that, if the proportion of correct answers
        is greater than 0.5, the exercise's difficulty lies in determining
        which answers should be left unchecked.

        Note that the
        """
        return _correct_minus_incorrect(answers, score)

    @staticmethod
    def correct_minus_incorrect_quadratic(answers: AnswersData, score: ScoreData) -> float:
        """Same algorithm as for `correct_minus_incorrect`, but the result is squared.

        This makes very unlikely for a student answering randomly to gain significant score.
        """
        return _correct_minus_incorrect(answers, score, exponent=2)


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


def _correct_minus_incorrect(answers: AnswersData, score: ScoreData, exponent=1.0) -> float:
    """If the proportion of correct answers is less than 0.5, as is typically the case,
    return the difference between the proportion of correctly checked answers
    and the proportion of incorrectly checked answers.

    Otherwise, if the proportion of correct answers is greater than 0.5,
    return the difference between the proportion of correctly unchecked answers
    and the proportion of incorrectly unchecked answers.

    The idea behind this algorithm is that, if the proportion of correct answers
    is greater than 0.5, the exercise's difficulty lies in determining
    which answers should be left unchecked.

    We then raise the result to the power of `exponent`.
    """
    ratio = 1 - len(answers.incorrectly_answered) / max(1, min(len(answers.correct), len(answers.incorrect)))
    return max(0.0, round(ratio**exponent * score.correct, 2))
