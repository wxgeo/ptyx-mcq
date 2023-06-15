from ptyx_mcq.scan.evaluation_strategies import EvaluationStrategies, AnswersData, ScoreData


# noinspection PyTypeChecker
def test_correct_minus_incorrect():
    scores = ScoreData(correct=6, skipped=0, incorrect=-1)
    answers = AnswersData(checked={1, 2}, correct={1, 2}, all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 6
    answers = AnswersData(checked={1, 2}, correct={1}, all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 0
    answers = AnswersData(checked={1, 2}, correct=set(), all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 0
    answers = AnswersData(checked=set(), correct=set(), all={1, 2, 3, 4})
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 6
    answers = AnswersData(checked={1}, correct={1, 2}, all={1, 2, 3, 4})
    # half the score
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 3
    answers = AnswersData(checked={1, 3}, correct={1, 2, 3}, all={1, 2, 3, 4, 5, 6})
    # 2/3 of the score
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 4
    answers = AnswersData(checked={1, 2, 4}, correct={1, 2, 3}, all={1, 2, 3, 4, 5, 6})
    # 1/3 of the score
    assert EvaluationStrategies.correct_minus_incorrect(answers=answers, score=scores) == 2
