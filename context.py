from __future__ import division, unicode_literals, absolute_import, print_function

from config import sympy

if sympy is not None:
    from sympy import sympify, SympifyError
else:
    SympifyError = None
    sympy = None
    print("I couldn't find sympy...  doing my best without it.")

class SpecialDict(dict):
    auto_sympify = False
    op_mode = None

    def __setitem__(self, key, value):
        if self.auto_sympify:
            try:
                value = sympify(value)
            except SympifyError:
                print('Warning: sympy error. Switching to standard evaluation mode.')
        dict.__setitem__(self, key, value)

    def copy(self):
        return SpecialDict(dict.copy(self))


global_context = SpecialDict()

