"""
AutoQCM

This extension enables computer corrected tests.

An example:

    #LOAD{autoqcm}
    #SEED{8737545887}

    ===========================
    sty=my_custom_sty_file
    scores=1 0 0
    mode=all
    ids=~/my_students.csv
    ===========================


    <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    ======= Mathematics ===========

    * 1+1 =
    - 1
    + 2
    - 3
    - 4

    - an other answer

    ======= Litterature ==========

    * "to be or not to be", but who actually wrote that ?
    + W. Shakespeare
    - I. Newton
    - W. Churchill
    - Queen Victoria
    - Some bloody idiot

    * Jean de la Fontaine was a famous french
    - pop singer
    - dancer
    + writer
    - detective
    - cheese maker

    > his son is also famous for
    @{\color{blue}%s}
    - dancing french cancan
    - conquering Honolulu
    - walking for the first time on the moon
    - having breakfast at Tiffany

    + none of the above is correct

    >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>


One may include some PTYX code of course.

    """

#TODO: support things like `#NEW INT(2,10) a, b, c, d WITH a*b - c*d != 0`.

from functools import partial
from os.path import join, basename, dirname

from .generate import generate_ptyx_code
from .header import packages_and_macros, ID_band, extract_ID_NAME_from_csv, \
                    extract_NAME_from_csv, student_ID_table, \
                    students_checkboxes
from .. import extended_python
import randfunc
from utilities import print_sympy_expr


def test_singularity_and_append(code, l, question):
    _code_ = code.strip()
    if _code_ in l:
        msg= [
        'ERROR: Same answer proposed twice in MCQ !',
        'Answer "%s" appeared at least twice for the same question.' % _code_,
        'Question was:',
        repr(question),
        '',
        'Nota: if this is really desired behaviour, insert',
        'following lines in the header of the ptyx file:',
        '#PYTHON',
        'ALLOW_SAME_ANSWER_TWICE=True',
        '#END',
        ]
        n = max(len(s) for s in msg)
        stars = (n + 4)*'*'
        print(stars)
        for s in msg:
            print('* ' + s)
        print(stars)
        raise RuntimeError('Same answer proposed twice in MCQ '
                           '(see message above for more information) !')
    else:
        l.append(_code_)
    return code


# ------------------
#    CUSTOM TAGS
# ------------------

def _parse_QCM_tag(self, node):
    self.autoqcm_correct_answers = []
    self.n_questions = 0
    self.n_max_answers = 0
    self._parse_children(node.children)

def _parse_ANSWERS_BLOCK_tag(self, node):
    self.write('\n\n\\begin{minipage}{\\textwidth}\n\\begin{flushleft}')
    self._parse_children(node.children)
    self.write('\n\\end{flushleft}\n\\end{minipage}')

def _parse_END_QCM_tag(self, node):
    data = self.autoqcm_data
    context = self.context
    n = context['NUM']
    data['answers'][n] = self.autoqcm_correct_answers
    # Those are supposed to have same value for each test,
    # so we don't save test number:
    data['n_questions'] = len(self.autoqcm_correct_answers)
    data['n_max_answers'] = self.n_max_answers

    # Now, we know the number of questions and of answers per question for
    # the whole MCQ, so we can generate the table for the answers.
    # ~ args, kw = data['table_for_answers_options']
    # ~ kw['answers'] = int(kw.get('answers', data['n_max_answers']))
    # ~ kw['questions'] = int(kw.get('questions', data['n_questions']))
    # ~ if context.get('WITH_ANSWERS'):
        # ~ kw['correct_answers'] = data['answers'][n]
    # ~ latex = generate_table_for_answers(*args, **kw)
    # orientation must be stored for scan later.
    # ~ data['flip'] = bool(kw.get('flip', False))
    #XXX: If flip is not the same for all tests, only last flip value
    # will be stored, which may lead to errors (though it's highly unlikely
    # that user would adapt flip value depending on subject number).



def _parse_NEW_QUESTION_tag(self, node):
    self.autoqcm_correct_answers.append([])
    self.autoqcm_answer_number = 0
    self.auto_qcm_answers = []
    self.context['APPLY_TO_ANSWERS'] = None
    # This is used to improve message error when an error occured.
    self.current_question = l = []
    def remember_last_question(code, l):
        l.append(code)
        return code
    self._parse_children(node.children, function=partial(remember_last_question, l=l))


# ~ def _parse_TABLE_FOR_ANSWERS_tag(self, node):
    # ~ self.autoqcm_data['table_for_answers_options'] = self._parse_options(node)
    # ~ # Don't parse it now, since we don't know the number of questions
    # ~ # and of answers per question for now.
    # ~ # Write the tag name as a bookmark... it will be replaced by latex
    # ~ # code eventually when closing MCQ (see: _parse_END_QCM_tag).
    # ~ self.write('#TABLE_FOR_ANSWERS')


def _parse_PROPOSED_ANSWER_tag(self, node):
    # TODO: functions should be compiled only once for each question block,
    # not for every answer (though it is probably not be a bottleneck in
    # code execution).
    apply = self.context.get('APPLY_TO_ANSWERS')
    f = None
    if apply:
        # Apply template or function to every answer.
        # Support:
        # - string templates. Ex: \texttt{%s}
        # - functions to apply. Ex: f
        if '%s' in apply:
            f = (lambda s: (apply % s))
        else:
            #~ for key in sorted(self.context):
                #~ print ('* ' + repr(key))
            f = self.context[apply]

    func = f

    if not self.context.get('ALLOW_SAME_ANSWER_TWICE'):
        # This function is used to verify that each answer is unique.
        # This avoids proposing twice the same answer by mistake, which
        # may occur easily when using random values.
        func = g = partial(test_singularity_and_append, l=self.auto_qcm_answers,
                                        question=self.current_question[0])
        if f is not None:
            # Compose functions. Function f should be applied first,
            # since it is not necessarily injective.
            func = (lambda s: g(f(s)))

    self.write(r'\begin{tabular}[t]{l}')
    self._parse_children(node.children, function=func)
    self.write(r'\end{tabular}\quad%' '\n')


# ~ def _parse_NEW_ANSWER_tag(self, node):
    # ~ is_correct = (node.arg(0) == 'True')
    # ~ # Add counter for each answer.
    # ~ self.write(r'\stepcounter{answerNumber}')
    # ~ # When the pdf with solutions will be generated, incorrect answers
    # ~ # will be preceded by a white square, while correct ones will
    # ~ # be preceded by a gray one.
    # ~ if self.context.get('WITH_ANSWERS') and not is_correct:
        # ~ self.write(r'\whitesquared')
    # ~ else:
        # ~ self.write(r'\graysquared')
    # ~ self.write(r'{\alph{answerNumber}}')
    # ~ if is_correct:
        # ~ self.autoqcm_correct_answers[-1].append(self.autoqcm_answer_number)
    # ~ self.autoqcm_answer_number += 1
    # ~ if self.autoqcm_answer_number > self.n_max_answers:
        # ~ self.n_max_answers = self.autoqcm_answer_number

def _parse_NEW_ANSWER_tag(self, node):
    is_correct = (node.arg(0) == 'True')
    _add_check_box(self, is_correct)


def _add_check_box(self, is_correct):
    # ~ # Add counter for each answer.
    # ~ self.write(r'\stepcounter{answerNumber}')
    # When the pdf with solutions will be generated, incorrect answers
    # will be preceded by a white square, while correct ones will
    # be preceded by a gray one.
    # Question number
    q = len(self.autoqcm_correct_answers)
    # Answer number
    a = self.autoqcm_answer_number
    cb_id = 'Q%s-%s' % (q, a)
    if self.context.get('WITH_ANSWERS') and not is_correct:
        self.write(r'\checkBox{white}{%s}{%s}' % (cb_id, is_correct))
    else:
        self.write(r'\checkBox{gray}{%s}{%s}' % (cb_id, is_correct))
    # ~ self.write(r'{\alph{answerNumber}}')
    if is_correct:
        self.autoqcm_correct_answers[-1].append(self.autoqcm_answer_number)
    self.autoqcm_answer_number += 1
    if self.autoqcm_answer_number > self.n_max_answers:
        self.n_max_answers = self.autoqcm_answer_number


def _parse_L_ANSWERS_tag(self, node):
    """#L_ANSWERS{list}{correct_answer} generate answers from a python list.

    Example:
    #L_ANSWERS{l}{l[0]}
    Note that if list or correct_answer are not strings, they will be
    converted automatically to math mode latex code (1/2 -> '$\frac{1}{2}$').
    """
    raw_l = self.context[node.arg(0).strip()]
    def conv(v):
        if isinstance(v, str):
            return v
        return '$%s$' % print_sympy_expr(v)
    correct_answer = conv(eval(node.arg(1).strip(), self.context))

    # Test that first argument seems correct
    # (it must be a list of unique answers including the correct one).
    if not isinstance(raw_l, (list, tuple)):
        raise RuntimeError('#L_ANSWERS: first argument must be a list of answers.')
    l = []
    for v in raw_l:
        test_singularity_and_append(conv(v), l, self.current_question[0])
    if correct_answer not in l:
        raise RuntimeError('#L_ANSWERS: correct answer is not in proposed answers list !')

    # Shuffle and generate LaTeX.
    randfunc.shuffle(l)
    self.write('\n\n\\begin{minipage}{\\textwidth}\n\\begin{flushleft}')
    for ans in l:
        is_correct = (ans == correct_answer)
        _add_check_box(self, is_correct)
        self.write(r'\begin{tabular}[t]{c}%s\end{tabular}\quad' % ans)
        self.write('%\n')
    self.write('\n\\end{flushleft}\n\\end{minipage}')


def _parse_DEBUG_AUTOQCM_tag(self, node):
    ans = self.autoqcm_correct_answers
    print('---------------------------------------------------------------')
    print('AutoQCM answers:')
    print(ans)
    print('---------------------------------------------------------------')
    self.write(ans)


def _parse_QCM_HEADER_tag(self, node):
    """Parse HEADER.

    HEADER raw format is the following:
    ===========================
    sty=my_custom_sty_file
    scores=1 0 0
    mode=all
    ids=~/my_students.csv
    ===========================
    """
    sty = ''
    WITH_ANSWERS = self.context.get('WITH_ANSWERS')
    if WITH_ANSWERS:
        self.context['format_ask'] = (lambda s: '')
    try:
        check_id_or_name = self.autoqcm_cache['check_id_or_name']
    except KeyError:
        code = ''
        # Read config
        for line in node.arg(0).split('\n'):
            if not line.strip():
                continue
            key, val = line.split('=', maxsplit=1)
            key = key.strip()
            val = val.strip()

            if key in ('scores', 'score'):
                # Set how many points are won/lost for a correct/incorrect answer.
                if ',' in val:
                    vals = val.split(',')
                else:
                    vals = val.split()
                vals = sorted(vals, key=float)
                self.autoqcm_data['correct'] = vals[-1]
                assert 1 <= len(vals) <= 3, 'One must provide between 1 and 3 scores '\
                        '(for correct answers, incorrect answers and no answer at all).'
                if len(vals) >= 2:
                    self.autoqcm_data['incorrect'] = vals[0]
                    if len(vals) >= 3:
                        self.autoqcm_data['skipped'] = vals[1]

            elif key == 'mode':
                self.autoqcm_data['mode'] = val

            elif key in ('names', 'name', 'students', 'student') and not WITH_ANSWERS:
                # val must be the path of a CSV file.
                students = extract_NAME_from_csv(val)
                code  = students_checkboxes(students)
                self.autoqcm_data['students_list'] = students

            elif key in ('id', 'ids') and not WITH_ANSWERS:
                # val must be the path of a CSV file.
                ids = extract_ID_NAME_from_csv(val)
                code = student_ID_table(ids)
                self.autoqcm_data['ids'] = ids

            elif key in ('sty', 'package'):
                sty = val

        check_id_or_name = (code if not self.context.get('WITH_ANSWERS') else '')
        self.autoqcm_cache['check_id_or_name'] = check_id_or_name
        check_id_or_name += r'''
        \vspace{1em}

        \tikz{\draw[dotted] ([xshift=2cm]current page.west) -- (current page.east);}
        '''

    try:
        header = self.autoqcm_cache['header']
    except KeyError:
        # TODO: Once using Python 3.6+ (string literals),
        # make packages_and_macros() return a tuple
        # (it's to painful for now because of.format()).
        if sty:
            sty = r'\usepackage{%s}' % sty
        header1, header2 = packages_and_macros()
        header = '\n'.join([header1, sty, header2, r'\begin{document}'])
        self.autoqcm_cache['header'] = header

    # Generate barcode
    # Barcode must NOT be put in the cache, since each document has a
    # unique ID.
    n = self.context['NUM']
    calibration=('AUTOQCM__SCORE_FOR_THIS_STUDENT' not in self.context)
    barcode = ID_band(ID=n, calibration=calibration)

    self.write('\n'.join([header, barcode, check_id_or_name]))






def main(text, compiler):
    # Generation algorithm is the following:
    # 1. Parse AutoQCM code, to convert it to plain pTyX code.
    #    Doing this, we now know the number of questions, the number
    #    of answers per question and the students names.
    #    However, we can't know for know the number of the correct answer for
    #    each question, since questions numbers and answers numbers too will
    #    change during shuffling, when compiling pTyX code (and keeping track of
    #    them through shuffling is not so easy).
    # 2. Generate syntax tree, and then compile pTyX code many times to generate
    #    one test for each student. For each compilation, keep track of correct
    #    answers.
    #    All those data are stored in `latex_generator.autoqcm_data['answers']`.
    #    `latex_generator.autoqcm_data['answers']` is a dict
    #    with the following structure:
    #    {1:  [          <-- test n°1 (test id is stored in NUM)
    #         [0,3,5],   <-- 1st question: list of correct answers
    #         [2],       <-- 2nd question: list of correct answers
    #         [1,5],     ...
    #         ],
    #     2:  [          <-- test n°2
    #         [2,3,4],   <-- 1st question: list of correct answers
    #         [0],       <-- 2nd question: list of correct answers
    #         [1,2],     ...
    #         ],
    #    }
    text = extended_python.main(text, compiler)
    # For efficiency, update only for last tag.
    compiler.add_new_tag('QCM', (0, 0, ['END_QCM']), _parse_QCM_tag, 'autoqcm', update=False)
    compiler.add_new_tag('NEW_QUESTION', (0, 0, ['@END', '@END_QUESTION']), _parse_NEW_QUESTION_tag, 'autoqcm', update=False)
    compiler.add_new_tag('NEW_ANSWER', (1, 0, None), _parse_NEW_ANSWER_tag, 'autoqcm', update=False)
    compiler.add_new_tag('END_QCM', (0, 0, None), _parse_END_QCM_tag, 'autoqcm', update=False)
    compiler.add_new_tag('QCM_HEADER', (1, 0, None), _parse_QCM_HEADER_tag, 'autoqcm', update=False)
    compiler.add_new_tag('PROPOSED_ANSWER', (0, 0, ['@END']), _parse_PROPOSED_ANSWER_tag, 'autoqcm', update=False)
    compiler.add_new_tag('ANSWERS_BLOCK', (0, 0, ['@END']), _parse_ANSWERS_BLOCK_tag, 'autoqcm', update=False)
    compiler.add_new_tag('L_ANSWERS', (2, 0, None), _parse_L_ANSWERS_tag, 'autoqcm', update=False)
    compiler.add_new_tag('DEBUG_AUTOQCM', (0, 0, None), _parse_DEBUG_AUTOQCM_tag, 'autoqcm', update=True)
    code = generate_ptyx_code(text)
    # Some tags may use cache, for code which don't change between two successive compilation.
    compiler.latex_generator.autoqcm_cache = {}
    # Default configuration:
    compiler.latex_generator.autoqcm_data = {'answers': {},
            'students': [],
            'ids': {},
            'correct': 1,
            'incorrect': 0,
            'skipped': 0,
            'mode': 'some',
            }
    assert isinstance(code, str)
    return code


def close(compiler):
    g = compiler.latex_generator
    answers = sorted(g.autoqcm_data['answers'].items())
    l = []
    l.append('MODE: %s' % g.autoqcm_data['mode'])
    l.append('CORRECT: %s' % g.autoqcm_data['correct'])
    l.append('INCORRECT: %s' % g.autoqcm_data['incorrect'])
    l.append('SKIPPED: %s' % g.autoqcm_data['skipped'])
    l.append('QUESTIONS: %s' % g.autoqcm_data['n_questions'])
    l.append('ANSWERS (MAX): %s' % g.autoqcm_data['n_max_answers'])
    # ~ l.append('FLIP: %s' % g.autoqcm_data['flip'])
    l.append('SEED: %s' % compiler.state['seed'])
    for n, correct_answers in answers:
        l.append(f'*** ANSWERS (TEST {n}) ***')
        for i, nums in enumerate(correct_answers):
            # Format: question -> correct answers
            # For example: 1 -> 1,3,4
            l.append('%s -> %s' % (i + 1, ','.join(str(j + 1) for j in nums)))

    l.append('*** STUDENTS LIST ***')
    for name in g.autoqcm_data['students']:
        l.append(name)

    l.append('*** IDS LIST ***')
    for id_, name in g.autoqcm_data['ids'].items():
        l.append('%s: %s' % (id_, name))

    path = compiler.state['path']
    folder = dirname(path)
    name = basename(path)
    for n in range(len(answers)):
        # XXX: what if files are not auto-numbered, but a list
        # of names is provided to Ptyx instead ?
        # (cf. command line options).
        filename = f'{name[:-5]}-{n + 1}.pos'
        full_path = join(folder, '.compile', name, filename)
        with open(full_path) as f:
            l.append(f'*** BOXES (TEST {n}) ***')
            l.append(f.read())

    config_file = path + '.autoqcm.config'
    with open(config_file, 'w') as f:
        f.write('\n'.join(l))
