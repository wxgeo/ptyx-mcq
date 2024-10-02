from ptyx_mcq.tools.extend_literal_eval import extended_literal_eval


def test_extend_literal_eval():
    assert extended_literal_eval("set()") == set()

    class A(list):
        def __eq__(self, other):
            return isinstance(other, A) and super().__eq__(other)

    a = extended_literal_eval("A((1, 2, inf))", {"A": A, "inf": float("inf")})
    assert type(a) is A
    assert a == A([1, 2, float("inf")])
    assert not (a == [1, 2, float("inf")])  # Do not test with !=, since it is not reimplemented.
