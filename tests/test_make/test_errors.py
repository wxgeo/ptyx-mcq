import pickle

from ptyx_mcq.make.extend_latex_generator import SameAnswerError


def test_SameAnswerError():
    err = SameAnswerError(answer="some text")
    assert pickle.loads(pickle.dumps(err)).answer == err.answer
