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
    """Give the full score if any of the correct answers is checked while no incorrect answer is checked."""
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
    """Give the full score if exactly all the correct answers are checked."""
    ok = answers.checked == answers.correct
    if ok:
        return score.correct
    elif not answers.checked:
        return score.skipped
    else:
        return score.incorrect


def proportional(answers: AnswersData, score: ScoreData) -> float:
    """Give the full score if exactly all the correct answers are checked."""
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


def _proportion_of_correct(answers: AnswersData) -> float:
    return len(answers.checked & answers.correct) / len(answers.correct)


def partial_answers_linear(answers: AnswersData, score: ScoreData) -> float:
    if answers.checked & answers.incorrect:
        return score.incorrect
    else:
        return round(_proportion_of_correct(answers) * score.correct, 2)


def partial_answers_quadratic(answers: AnswersData, score: ScoreData) -> float:
    if answers.checked & answers.incorrect:
        return score.incorrect
    else:
        return round(_proportion_of_correct(answers) ** 2**score.correct, 2)


# def floored_partial_anwers(answers: AnswersData, score: ScoreData) -> float:
#     return max(0, partial_answers(answers, score))


modes = (some, all, proportional, partial_answers_linear, partial_answers_quadratic)
