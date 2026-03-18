from dataclasses import dataclass
from math import nan, isnan

from ptyx_mcq.tools.config_parser import OriginalAnswerNumber


class IncorrectScoreParameter(RuntimeError):
    """Error raised when a score parameter is incoherent with chosen evaluation strategy."""


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

        Typically, you should set minimal_score = -maximal_score, if you want an average
        score of zero when answering randomly.

        The formula for the calculated score is `(1 - k) * minimal_score + k * maximal_score`,
        where k is the proportion of correct answers (correctly checked or unchecked boxes).

        This means that if all answers are correct, the score will be equal to the maximal score;
        if all answers are incorrect, the score will be equal to the minimal score;
        and if some answers are correct and others are incorrect, the score will be somewhere in between.
        """
        count_ok = len(answers.checked & answers.correct) + len(answers.unchecked & answers.incorrect)
        proportion = count_ok / len(answers.all)
        return round(score.incorrect + proportion * (score.correct - score.incorrect), 2)

    @staticmethod
    def partial_answers(answers: AnswersData, score: ScoreData) -> float:
        """Return `score.incorrect` if an incorrect answer was checked,
        else the proportion of correct answers multiplied by `score.correct`."""
        return _partial_answers(answers, score)

    @staticmethod
    def partial_answers_quadratic(answers: AnswersData, score: ScoreData) -> float:
        """Same algorithm as for `partial_answers`, but the ratio is squared.

        This makes more unlikely for a student answering randomly to gain significant score."""
        return _partial_answers(answers, score, exposant=2)

    @staticmethod
    def special_correct_minus_incorrect(answers: AnswersData, score: ScoreData) -> float:
        """This algorithm is designed for multiple-choice questions that feature null scores
        for incorrect answers.

        It aims at keeping the average gain low for random answers, while not making use of negative
        scores for incorrect answers.

        This requires enough answers to work well (typically n >= 6 at least),
        and for the student to not know the number of correct answers.

        The following table gives an approximation of the average score per question
        when answering randomly, if the maximal score = +1 and the minimal score is 0,
        and half of the answers are correct (worst case):

            ┌───────────────────┬───────┬───────┬───────┬───────┐
            │   number of boxes │   4   │   6   │   8   │  10   │
            ├───────────────────┼───────┼───────┼───────┼───────┤
            │   average score   │ 0.16  │ 0.11  │ 0.09  │ 0.07  │
            ├───────────────────┼───────┼───────┼───────┼───────┤
            │ average score for │ 0.11  │ 0.06  │ 0.04  │ 0.03  │
            │ quadratic version │       │       │       │       │
            └───────────────────┴───────┴───────┴───────┴───────┘

        Note that if there is only one correct answer per question, there can't be
        partially correct answers, and the average score is simply 1/n,
        where n is the number of boxes (the same is true for the quadratic version):

            ┌───────────────────┬───────┬───────┬───────┬───────┐
            │   number of boxes │   4   │   6   │   8   │  10   │
            ├───────────────────┼───────┼───────┼───────┼───────┤
            │   average score   │ 0.25  │ 0.17  │ 0.13  │ 0.10  │
            └───────────────────┴───────┴───────┴───────┴───────┘

        If the proportion of correct answers is less than 0.5, as is typically the case,
        return the difference between the number of correctly checked answers
        and the number of incorrectly checked answers, divided by the total number
        of correct answers if any.

        Otherwise, if the proportion of correct answers is greater than 0.5,
        return the difference between the number of correctly unchecked answers
        and the number of incorrectly unchecked answers, divided by the total number
        of incorrect answers if any.

        The idea behind this algorithm is that, if the proportion of correct answers
        is greater than 0.5, the exercise's difficulty lies in determining
        which answers should be left unchecked.

        This value will be eventually floored to keep it in the range [-1,1].

        If the result is positive, return result * score.correct.
        Else, return -abs(result) * score.incorrect.
        """
        return _special_correct_minus_incorrect(answers, score)

    @staticmethod
    def special_correct_minus_incorrect_quadratic(answers: AnswersData, score: ScoreData) -> float:
        """Same algorithm as for `special_correct_minus_incorrect`, but the ratio are squared.

        This makes more unlikely for a student answering randomly to gain significant score.
        """
        return _special_correct_minus_incorrect(answers, score, exponent=2)

    @staticmethod
    def correct_minus_incorrect(answers: AnswersData, score: ScoreData) -> float:
        """Return the proportion of checked answers among correct ones, minus the proportion of
        checked answers between incorrect ones.

        This algorithm works better when minimal score is the opposite of the maximal score
        (-1 and +1 for example), since the average score when answering randomly will be 0.

        If there are no correct answers, or if all answers are correct, the previous formula
        can't obviously be applied.
        In that case, the score is only based on the proportion of rightly checked or unchecked
        answers among all answers:
          - If this proportion is higher than 1/2, then the result will be a fraction of `score.correct`.
          - Else, the result will be a fraction of `score.incorrect`.
        """
        return _correct_minus_incorrect(answers, score)

    @staticmethod
    def correct_minus_incorrect_quadratic(answers: AnswersData, score: ScoreData) -> float:
        """Same algorithm as for `correct_minus_incorrect`, but the ratio difference is squared.

        This makes more unlikely for a student answering randomly to gain significant score.
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
    """See: `EvaluationStrategies.partial_answers`."""
    if answers.checked & answers.incorrect:
        return score.incorrect
    else:
        return round(_checked_among_correct_proportion(answers) ** exposant * score.correct, 2)


def _special_correct_minus_incorrect(answers: AnswersData, score: ScoreData, exponent=1.0) -> float:
    """See: `EvaluationStrategies.special_correct_minus_incorrect`."""
    if score.incorrect > 0:
        raise IncorrectScoreParameter(
            f"The score for an incorrect answer must be zero or negative, yet {score.incorrect} > 0."
        )
    diff = 1 - len(answers.incorrectly_answered) / max(1, min(len(answers.correct), len(answers.incorrect)))
    diff = max(-1.0, diff)
    assert -1 <= diff <= 1, diff
    result = abs(diff) ** exponent * (score.correct if diff > 0 else score.incorrect)
    return round(result, 2)


def _correct_minus_incorrect(answers: AnswersData, score: ScoreData, exponent=1.0) -> float:
    """See: `EvaluationStrategies.correct_minus_incorrect`."""
    if score.incorrect > 0:
        raise IncorrectScoreParameter(
            f"The score for an incorrect answer must be zero or negative, yet {score.incorrect} > 0."
        )
    if len(answers.correct) == 0 or len(answers.incorrect) == 0:
        if len(answers.correct) == 0:
            # No answers should have been checked.
            p = len(answers.unchecked) / len(answers.all)
        else:
            # All answers should have been checked.
            p = len(answers.checked) / len(answers.all)
        # No answer is correct (p = 1)              -> score.correct
        # Half of the answers are correct (p = 0.5) -> 0
        # No answers are correct (p = 0)            -> score.incorrect
        if p > 0.5:
            return (2 * (p - 0.5)) ** exponent * score.correct
        else:
            return (2 * (0.5 - p)) ** exponent * score.incorrect

    else:
        correct_ratio = len(answers.checked & answers.correct) / len(answers.correct)
        assert correct_ratio <= 1
        incorrect_ratio = len(answers.checked & answers.incorrect) / len(answers.incorrect)
        assert incorrect_ratio <= 1
        diff = correct_ratio - incorrect_ratio
        assert -1 <= diff <= 1
        return abs(diff) ** exponent * (score.correct if diff > 0 else score.incorrect)
