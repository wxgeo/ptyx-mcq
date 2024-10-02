# mypy: disable-error-code = "arg-type"

import random

from ptyx_mcq.scan.score_management.evaluation_strategies import (
    EvaluationStrategies,
    AnswersData,
    ScoreData,
)


# noinspection PyTypeChecker
def test_legacy_correct_minus_incorrect_1():
    scores = ScoreData(correct=6, skipped=0, incorrect=-1)
    answers = AnswersData(checked={1, 2}, correct={1, 2}, all={1, 2, 3, 4})
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 6
    answers = AnswersData(checked={1, 2}, correct={1}, all={1, 2, 3, 4})
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 0
    answers = AnswersData(checked={1, 2}, correct=set(), all={1, 2, 3, 4})
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == -1
    answers = AnswersData(checked=set(), correct=set(), all={1, 2, 3, 4})
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 6
    answers = AnswersData(checked={1}, correct={1, 2}, all={1, 2, 3, 4})
    # half the score
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 3
    answers = AnswersData(checked={1, 3}, correct={1, 2, 3}, all={1, 2, 3, 4, 5, 6})
    # 2/3 of the score
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 4
    answers = AnswersData(checked={1, 2, 4}, correct={1, 2, 3}, all={1, 2, 3, 4, 5, 6})
    # 1/3 of the score
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 2


# noinspection PyTypeChecker
def test_legacy_correct_minus_incorrect_0():
    scores = ScoreData(correct=6, skipped=0, incorrect=0)
    answers = AnswersData(checked={1, 2}, correct={1, 2}, all={1, 2, 3, 4})
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 6
    answers = AnswersData(checked={1, 2}, correct={1}, all={1, 2, 3, 4})
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 0
    answers = AnswersData(checked={1, 2}, correct=set(), all={1, 2, 3, 4})
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 0
    answers = AnswersData(checked=set(), correct=set(), all={1, 2, 3, 4})
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 6
    answers = AnswersData(checked={1}, correct={1, 2}, all={1, 2, 3, 4})
    # half the score
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 3
    answers = AnswersData(checked={1, 3}, correct={1, 2, 3}, all={1, 2, 3, 4, 5, 6})
    # 2/3 of the score
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 4
    answers = AnswersData(checked={1, 2, 4}, correct={1, 2, 3}, all={1, 2, 3, 4, 5, 6})
    # 1/3 of the score
    assert EvaluationStrategies.special_correct_minus_incorrect(answers=answers, score=scores) == 2


# noinspection PyTypeChecker
def test_correct_minus_incorrect():
    scores = ScoreData(correct=6, skipped=0, incorrect=-2)
    answers = AnswersData(checked={1, 2}, correct={1, 2}, all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 6
    answers = AnswersData(checked={3, 4}, correct={1, 2}, all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == -2
    answers = AnswersData(checked={1}, correct={1, 2}, all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 3
    answers = AnswersData(checked={1, 3}, correct={1, 2}, all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 0
    answers = AnswersData(checked={1, 3}, correct={1}, all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 4
    answers = AnswersData(checked={1, 2, 3, 4}, correct={1}, all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 0

    # Special cases: all answers should be checked
    answers = AnswersData(checked={1, 2, 3, 4}, correct={1, 2, 3, 4}, all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 6
    answers = AnswersData(checked={1, 2}, correct={1, 2, 3, 4}, all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 0
    answers = AnswersData(checked=set(), correct={1, 2, 3, 4}, all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == -2

    # Special cases: no answers should be checked
    answers = AnswersData(checked=set(), correct=set(), all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 6
    answers = AnswersData(checked={1, 2}, correct=set(), all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 0
    answers = AnswersData(checked={1, 2, 3, 4}, correct=set(), all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == -2


def rand_subset(s: set, size: int = None) -> set:
    if size is None:
        return {elt for elt in s if random.random() < 0.5}
    elif size == len(s):
        return s.copy()
    elif size > len(s):
        raise ValueError(
            f"Incorrect size ({size} > {len(s)}). A subset can't be larger than the original set."
        )
    return set(random.choices(list(s), k=size))


# noinspection PyTypeChecker
def get_random_answers_data(
    number_of_answers: int = 6,
    number_of_checked_answers: int = None,
    number_of_correct_answers: int = None,
) -> AnswersData:
    all_answers = set(range(number_of_answers))
    correct_answers = rand_subset(all_answers, size=number_of_correct_answers)
    checked_answers = rand_subset(all_answers, size=number_of_checked_answers)
    return AnswersData(checked=checked_answers, correct=correct_answers, all=all_answers)  # type: ignore


# noinspection PyTypeChecker
def random_evaluation(
    strategy: str,
    scores: ScoreData,
    number_of_answers: int = 6,
    number_of_checked_answers: int | float | None = None,
    number_of_correct_answers: int | float | None = None,
    loops: int = 10000,
):
    if isinstance(number_of_checked_answers, float) and 0 < number_of_checked_answers < 1:
        number_of_checked_answers = int(number_of_checked_answers * number_of_answers)
    if not (isinstance(number_of_checked_answers, int) or number_of_checked_answers is None):
        raise ValueError(number_of_checked_answers)
    if isinstance(number_of_correct_answers, float) and 0 < number_of_correct_answers < 1:
        number_of_correct_answers = int(number_of_correct_answers * number_of_answers)
    if not (isinstance(number_of_correct_answers, int) or number_of_correct_answers is None):
        raise ValueError(number_of_correct_answers)
    total = 0
    for i in range(loops):
        answers = get_random_answers_data(
            number_of_answers=number_of_answers,
            number_of_checked_answers=number_of_checked_answers,
            number_of_correct_answers=number_of_correct_answers,
        )
        total += getattr(EvaluationStrategies, strategy)(answers=answers, score=scores)
    return 100 * total / loops


# noinspection PyTypeChecker
def test_random_evaluation():
    """This is used mainly for simulations, and is not meant for unit tests."""
    # ---------------------------------------------------------------
    # Parameters:
    correct = 1
    incorrect = 0
    loops = 1000  # at least 1000 for sensible results
    # `number_of_checked_answers` and `number_of_correct_answers` values can be either :
    # - `None`: the number of checked/correct answers will be set each time randomly
    # - an integer: the number of checked/correct answers
    # - a float between 0 and 1: the proportion of checked/correct answers among all answers
    number_of_checked_answers = None
    number_of_correct_answers = None
    # ---------------------------------------------------------------
    random.seed(594135875)
    scores = ScoreData(correct=correct, skipped=0, incorrect=incorrect)

    for strategy in (
        "special_correct_minus_incorrect",
        "special_correct_minus_incorrect_quadratic",
        "correct_minus_incorrect",
        "correct_minus_incorrect_quadratic",
    ):

        def print_results(number_of_answers):
            print(
                random_evaluation(
                    strategy,
                    scores=scores,
                    number_of_answers=number_of_answers,
                    number_of_checked_answers=number_of_checked_answers,
                    number_of_correct_answers=number_of_correct_answers,
                    loops=loops,
                )
            )

        print()
        print(f"Strategy {strategy}:")
        print_results(number_of_answers=4)
        print_results(number_of_answers=6)
        print_results(number_of_answers=8)
        print_results(number_of_answers=10)
