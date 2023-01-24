from dataclasses import dataclass
from math import nan, isnan


@dataclass
class AnswersData:
    checked: set[int]
    correct: set[int]
    all: set[int]

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


def all(answers: AnswersData, score: ScoreData) -> float:
    """Return the maximal score if all the correct answers are checked, else give the minimal score.
    """
    ok = answers.checked == answers.correct
    if ok:
        return score.correct
    elif not answers.checked:
        return score.skipped
    else:
        return score.incorrect


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


# def floored_proportional(answers: AnswersData, score: ScoreData) -> float:
#     return max(0, proportional(answers, score))


# def floored_half_proportional(answers: AnswersData, score: ScoreData) -> float:
#     if (answers.checked == answers.correct):
#         return score.correct
#     else:
#         return 0.5*floored_proportional(answers, score)


def _checked_among_correct_proportion(answers: AnswersData) -> float:
    """Return the proportion of checked answers among correct ones.

    If there was no correct answer, return 1.0 if no answer was checked, 0.0 else.
    """
    if len(answers.correct) == 0:
        return float(len(answers.checked) == 0)
    return len(answers.checked & answers.correct) / len(answers.correct)


def partial_answers_linear(answers: AnswersData, score: ScoreData) -> float:
    """Return 0 if an incorrect answer was checked, else the proportion of correct answers"""
    if answers.checked & answers.incorrect:
        return score.incorrect
    else:
        return round(_checked_among_correct_proportion(answers) * score.correct, 2)


def partial_answers_quadratic(answers: AnswersData, score: ScoreData) -> float:
    if answers.checked & answers.incorrect:
        return score.incorrect
    else:
        return round(_checked_among_correct_proportion(answers) ** 2 ** score.correct, 2)


# def floored_partial_anwers(answers: AnswersData, score: ScoreData) -> float:
#     return max(0, partial_answers(answers, score))


modes = (some, all, proportional, partial_answers_linear, partial_answers_quadratic)
