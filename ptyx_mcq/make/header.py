import csv
from pathlib import Path
from string import ascii_letters
from typing import Sequence, List, Optional, Dict, Union, Tuple

from ..parameters import (
    CELL_SIZE_IN_CM,
    MARGIN_LEFT_IN_CM,
    MARGIN_RIGHT_IN_CM,
    PAPER_FORMAT,
    MARGIN_BOTTOM_IN_CM,
    MARGIN_TOP_IN_CM,
    CALIBRATION_SQUARE_POSITION,
    CALIBRATION_SQUARE_SIZE,
)
from ..tools.config_parser import (
    get_answers_with_status,
    Configuration,
    DocumentId,
    ApparentAnswerNumber,
    ApparentQuestionNumber,
    StudentName,
    StudentId,
)

PACKAGES = [
    "inputenc",
    "fontenc:T1",
    "ragged2e",
    "geometry",
    "pifont",
    "textcomp",
    "nopageno",
    "tikz",
    "everypage",
    "tabularx",
    "amsmath",
    "amssymb",
    "colortbl",
]
ZREF_PACKAGES = ["zref-user", "zref-abspos", "zref-abspage", "zref-lastpage"]
TIKZ_LIB = ["calc", "math"]


class IdentifiantError(RuntimeError):
    pass


def _byte_as_codebar(byte: Union[int, str], n=0) -> str:
    """Generate LaTeX code (TikZ) for byte number `n` in ID band.

    - `byte` is a number between 0 and 255, or some LaTeX code resulting
      in such a number.
      If the number is above 255, encoding will be wrong.
    - `n` should be incremented at each call, so as not to overwrite
      a previous codebar.
    """
    if isinstance(byte, int) and byte > 255:
        raise NotImplementedError("Value can't exceed 255 for one byte.")
    return rf"""
    \n={byte};
    \j={n};
    for \i in {{1,...,8}}{{%
            \r = int(Mod(\n,2));
            \n = int(\n/2);
            {{\draw[fill=color\r] ({{\i*0.25+2*\j}},0) rectangle ({{\i*0.25+0.25+2*\j}},0.25);
             }};
            }};"""


def id_band(doc_id: int, calibration=True) -> str:
    """Generate top banner of the page to be scanned later.

    `doc_id` is the integer which identifies each document.

    This top banner is made of:
    - four squares for calibration (top left, top right,
      bottom left, bottom right, at 1 cm of the border).
      If `calibration` is False, those squares are not displayed.

    - an identification band (kind of codebar) midway between
      the top squares.
      This ID band is used to encode both the MCQ ID number and the page
      number. They will be read automatically later.

    NB:
    - There is no need to provide the page number, since it will be
      handled directly by LaTeX.
    - Page number can't exceed 255.
    - Document number can't exceed 65535.
    """
    if doc_id >= 2**16:
        raise ValueError(f"Document number can't exceed 65535 (current id: {doc_id}).")
    latex = [
        r"\newcommand\CustomHeader{%"
        "\n    "
        r"\begin{tikzpicture}[remember picture,overlay,black,"  # Set default color to black !
        r"every node/.style={inner sep=0,outer sep=-0.2}]"
    ]
    if calibration:
        pos = CALIBRATION_SQUARE_POSITION
        pos2 = CALIBRATION_SQUARE_POSITION + CALIBRATION_SQUARE_SIZE
        latex.append(
            rf"""
        \draw[fill=black] ([xshift={pos}cm,yshift=-{pos}cm]current page.north west)
            rectangle ([xshift={pos2}cm,yshift=-{pos2}cm]current page.north west);
        \draw[fill=black] ([xshift=-{pos}cm,yshift=-{pos}cm]current page.north east)
            rectangle ([xshift=-{pos2}cm,yshift=-{pos2}cm]current page.north east);
        \draw[fill=black] ([xshift={pos}cm,yshift={pos}cm]current page.south west)
            rectangle ([xshift={pos2}cm,yshift={pos2}cm]current page.south west);
        \draw[fill=black] ([xshift=-{pos}cm,yshift={pos}cm]current page.south east)
            rectangle ([xshift=-{pos2}cm,yshift={pos2}cm]current page.south east);"""
        )
    latex.append(
        r"""\node at ([yshift=-1cm]current page.north) [anchor=north] {
            \begin{tikzpicture}
            \definecolor{color0}{rgb}{1,1,1}
            \definecolor{color1}{rgb}{0,0,0}
            \draw[fill=black] (0,0) rectangle (0.25,0.25);
            \tikzmath {"""
    )
    latex.append(_byte_as_codebar(r"\thepage"))
    latex.append(_byte_as_codebar(doc_id % 256, n=1))
    latex.append(_byte_as_codebar(doc_id // 256, n=2))
    latex.append(
        rf"""}}
        \node[anchor=west] at  ({{2.5+2*\j}},0.1)
            {{\scriptsize\textbf{{\#{doc_id}}}~:~{{\thepage}}/\zpageref{{LastPage}}}};
        \end{{tikzpicture}}}};

        \draw[dotted]  ([xshift=-1cm,yshift=-2cm]current page.north east)
            -- ([xshift=1cm,yshift=-2cm]current page.north west)
            node [pos=0.25,fill=white]
            {{\,\,\scriptsize\textuparrow\,\,\textsc{{N'écrivez rien au
            dessus de cette ligne}}\,\,\textuparrow\,\,}}
            node [pos=0.75,fill=white]
            {{\,\,\scriptsize\textuparrow\,\,\textsc{{N'écrivez rien au
            dessus de cette ligne}}\,\,\textuparrow\,\,}};
    \end{{tikzpicture}}}}"""
    )
    return "".join(latex)


def extract_students_id_and_name_from_csv(csv_path: Path, script_path: Path) -> Dict[StudentId, StudentName]:
    """`csv_path` is the path of the CSV file who contains students names and ids.
    The first column of the CSV file must contain the ids.

    Return a dictionnary containing the students ID and corresponding names.
    """
    csv_path = csv_path.expanduser()
    if not csv_path.is_absolute():
        csv_path = (script_path.parent / csv_path).absolute()
    # XXX: support ODS and XLS files ?
    # soffice --convert-to cvs filename.ods
    # https://ask.libreoffice.org/en/question/2641/convert-to-command-line-parameter/
    ids: Dict[StudentId, StudentName] = {}
    # Read CSV file and generate the dictionary {id: "student name"}.
    with open(csv_path) as f:
        dialect = csv.Sniffer().sniff(f.read(1024))
        f.seek(0)
        for row in csv.reader(f, dialect):
            first_cell, *row = row
            studient_id = StudentId(first_cell.strip())
            name = StudentName(" ".join(item.strip() for item in row))
            if studient_id in ids and ids[studient_id] != name:
                raise RuntimeError(f"Error: same ID {studient_id!r} for different students in {csv_path!r} !")
            ids[studient_id] = name
    return ids


def extract_students_name_from_csv(csv_path: Path, script_path: Path) -> List[StudentName]:
    """`csv_path` is the path of the CSV file who contains students names.

    Return a list of students names.
    """
    csv_path = csv_path.expanduser()
    if not csv_path.is_absolute():
        csv_path = (script_path.parent / csv_path).absolute()

    names: List[StudentName] = []
    # Read CSV file and generate the dictionary {id: "student name"}.
    with open(csv_path) as f:
        for row in csv.reader(f):
            names.append(StudentName(" ".join(item.strip() for item in row)))
    return names


def students_checkboxes(names: Sequence[str], _n_student=None) -> str:
    """Generate a list of all students, where student can check his name.

    `names` is a list of students names.
    `_n_student` is used to prefill the table (for debugging).
    """
    content = [
        r"""
        \vspace{-1em}
        \begin{center}
        \begin{tikzpicture}[scale=.25]
        \draw [fill=black] (-2,0) rectangle (-1,1) (-1.5,0) node[below]
        {\tiny\rotatebox{-90}{\texttt{\textbf{Noircir la case}}}};"""
    ]

    # Generate the corresponding names' table in LaTeX.
    b = None
    for i, name in enumerate(reversed(names)):
        # Truncate long names.
        if len(name) >= 15:
            _name = name[:13].strip()
            if " " not in name[12:13]:
                _name += "."
            name = _name
        a = 2 * i
        b = a + 1
        c = a + 0.5
        color = "black" if _n_student == len(names) - i else "white"
        content.append(
            rf"""\draw[fill={color}] ({a},0) rectangle ({b},1) ({c},0)
            node[below] {{\tiny \rotatebox{{-90}}{{\texttt{{{name}}}}}}};"""
        )
    if b is None:
        # No names.
        return ""
    b += 1
    content.append(
        rf"""\draw[rounded corners] (-3,2) rectangle ({b}, -6.5);
        \draw[] (-0.5,2) -- (-0.5,-6.5);
        \end{{tikzpicture}}
        \end{{center}}
        \vspace{{-1em}}
        """
    )
    return "\n".join(content)


def student_id_table(id_length: int, max_ndigits: int, digits: List[Tuple[str, ...]]) -> str:
    """Generate a table where the student will write its identification number.

    The table have a row for each digit, where the student check corresponding
    digit to indicate its number.

    Parameters:
    - the length of an ID,
    - the maximal number of different digits in an ID caracter,
    - a list of sets corresponding to the different digits used for each ID caracter.

    Return: LaTeX code.
    """
    content: List[str] = []
    write = content.append
    write("\n\n")
    write(r"\begin{tikzpicture}[baseline=-10pt,scale=.5]")
    write(r"\node[anchor=south west] at (-1, 0) {Numéro étudiant (INE)~:};")
    write(r"\draw[] (-1, 0) node {\zsavepos{ID-table}} rectangle (0,%s);" % (-id_length))
    for j in range(id_length):
        # One row for each digit of the student id number.
        for i, d in enumerate(sorted(digits[j])):
            write(
                rf"""\draw ({i},{-j}) rectangle ({i+1},{-j-1})
                    ({i+0.25},{-j-0.25}) node  {{\footnotesize\color{{black}}\textsf{{{d}}}}};"""
            )
        for i in range(i, max_ndigits):
            write(rf"""\draw ({i},{-j}) rectangle ({i+1},{-j-1});""")
    write(r"\draw[black,->,thick] (-0.5, -0.5) -- (-0.5,%s);" % (0.5 - id_length))
    write(r"\end{tikzpicture}")
    write(
        r"\hfill\begin{tikzpicture}[baseline=10pt]"
        r"\node[draw,rounded corners] {\begin{tabular}{p{8cm}}"
        r"\textsc{Nom~:}~\dotfill\\"
        r"Prénom~:~\dotfill\\"
        r"Groupe~:~\dotfill\\"
        r"Numéro d'étudiant:~\dotfill\\"
        r"\end{tabular}};\end{tikzpicture}"
        r"\write\mywrite{ID-table: "
        r"(\dimtomm{\zposx{ID-table}sp}, "
        r"\dimtomm{\zposy{ID-table}sp})}"
    )
    write("\n\n")
    return "\n".join(content)


def table_for_answers(config: Configuration, doc_id: Optional[DocumentId] = None) -> str:
    """Generate the table where students select correct answers.

    - `config` is a dict generated when compiling test.
    - `doc_id` is the document ID if correct answers should be shown.
      If `doc_id` is `None` (default), the table will be left empty.
    """
    content: List[str] = []
    write = content.append

    # Generate the table where students will answer.
    tkzoptions = ["scale=%s" % CELL_SIZE_IN_CM]

    if doc_id is None:
        assert len(config.ordering) >= 1
        # Get any dict value.
        d = next(iter(config.ordering.values()))
    else:
        d = config.ordering[doc_id]

    questions = d["questions"]
    answers = d["answers"]
    n_questions = len(questions)
    n_max_answers = max(len(nums) for nums in answers.values())
    flip = n_max_answers > n_questions
    if flip:
        tkzoptions.extend(["x={(0cm,-1cm)}", "y={(-1cm,0cm)}"])

    write(
        r"""
        \begin{tikzpicture}[%s]
        \draw[thin,fill=black] (-1,0) rectangle (0,1);"""
        % (",".join(tkzoptions))
    )

    for x1 in range(n_questions):
        x2 = x1 + 1
        x3 = 0.5 * (x1 + x2)
        write(rf"\draw[ultra thin] ({x1},0) rectangle ({x2},1) ({x3},0.5) " rf"node {{{x1 + 1}}};")

    # Find correct answers numbers for each question.
    if doc_id is not None:
        correct_ans = get_answers_with_status(config, correct=True, use_original_num=False)[doc_id]

    # i = -1
    for i in range(n_max_answers):
        name = ascii_letters[i]
        y1 = -i
        y2 = y1 - 1
        y3 = 0.5 * (y1 + y2)
        write("\n" rf"\draw[ultra thin] (-1,{y1}) rectangle (0,{y2}) (-0.5,{y3}) " rf"node {{{name}}};")
        for j in range(n_questions):
            x1 = j
            x2 = x1 + 1
            opt = ""
            if (
                doc_id is not None
                and ApparentAnswerNumber(i + 1) in correct_ans[ApparentQuestionNumber(j + 1)]
            ):
                opt = "fill=gray"
            write(rf"\draw [ultra thin,{opt}] ({x1},{y1}) rectangle ({x2},{y2});")

    write(rf"\draw [thick] (-1,1) rectangle ({x2},{y2});" "\n")
    #              %\draw [thick] (-1,0) -- ({x2},0);

    for i in range(0, x2):
        write(rf"\draw [thick] ({i},1) -- ({i},{y2});" "\n")

    write(r"\end{tikzpicture}\hfill\hfill\hfil" "\n")

    return "\n".join(content)


def _generate_package_includes(packages: list[str]) -> str:
    """Generate the LaTeX code corresponding to the inclusion of the given LaTeX packages."""
    lines: list[str] = []
    for pack in packages:
        if ":" in pack:
            pack, options = pack.split(":", 1)
            line = f"\\usepackage[{options}]{{{pack}}}"
        else:
            line = f"\\usepackage{{{pack}}}"
        lines.append(line)
    return "\n".join(lines)


def _generate_tikz_lib_includes(libs: list[str]) -> str:
    """Generate the LaTeX code corresponding to the inclusion of the given Tikz libraries."""
    return "\n".join(f"\\usetikzlibrary{{{lib}}}" for lib in libs)


def _checkbox_code(preview_mode: bool = False) -> str:
    """Generate the LaTeX code corresponding to a checkbox.

    If not in preview mode, the position of the box is stored.
    """
    if preview_mode:
        return r"""
\newcommand{\checkBox}[2]{%
    \begin{tikzpicture}[baseline=-12pt,color=black, thick]
        \draw[fill=#1] (0,0)
            node {}
            rectangle (.5,-.5);
    \end{tikzpicture}
}"""
    else:
        return r"""
\newcommand{\checkBox}[2]{%
    \begin{tikzpicture}[baseline=-12pt,color=black, thick]
        \draw[fill=#1] (0,0)
            node {\zsavepos{#2-ll}}
            rectangle (.5,-.5);
    \end{tikzpicture}%
    \write\mywrite{#2: p\thepage, (%
        \dimtomm{\zposx{#2-ll}sp},
        \dimtomm{\zposy{#2-ll}sp})%
    }%
}
\newwrite\mywrite
\openout\mywrite=\jobname.pos\relax
\AddEverypageHook{\CustomHeader}"""


def packages_and_macros(preview_mode: bool = False) -> tuple[str, str]:
    """Generate LaTeX default header (loading LaTeX packages and defining some custom macros)."""
    # https://tex.stackexchange.com/questions/37297/how-to-get-element-position-in-latex
    paper_format = f"{PAPER_FORMAT.lower()}paper"
    # LaTeX header is in two part, so as user may insert some customization here.

    first_part = rf"""\documentclass[{paper_format},twoside,10pt]{{article}}
\PassOptionsToPackage{{utf8}}{{inputenc}}
\PassOptionsToPackage{{document}}{{ragged2e}}
\PassOptionsToPackage{{left={MARGIN_LEFT_IN_CM}cm,
    right={MARGIN_RIGHT_IN_CM}cm,
    top={MARGIN_TOP_IN_CM}cm,bottom={MARGIN_BOTTOM_IN_CM}cm}}{{geometry}}
\parindent=0cm
\newcommand*\graysquared[1]{{\tikz[baseline=(char.base)]{{
    \node[fill=gray,shape=rectangle,draw,inner sep=2pt] (char) {{\color{{white}}\textbf{{#1}}}};}}}}
\newcommand*\whitesquared[1]{{\tikz[baseline=(char.base)]{{
    \node[fill=white,shape=rectangle,draw,inner sep=2pt] (char) {{\color{{black}}\textbf{{#1}}}};}}}}
\newcommand*\ptyxMCQcircled[1]{{\tikz[baseline=(char.base)]{{
    \node[shape=circle,fill=blue!20!white,draw,inner sep=2pt] (char) {{\textbf{{#1}}}};}}}}
\makeatletter
\newcommand{{\ptyxMCQsimfill}}{{%
\leavevmode \cleaders \hb@xt@ .50em{{\hss $\sim$\hss }}\hfill \kern \z@
}}
\makeatother
\newcounter{{answerNumber}}
\renewcommand{{\thesubsection}}{{\Alph{{subsection}}}}
"""
    packages = PACKAGES.copy()
    if preview_mode:
        packages.append("preview: active, tightpage")
    second_part = "\n".join(
        [
            _generate_package_includes(packages),
            _generate_tikz_lib_includes(TIKZ_LIB),
            "" if preview_mode else _generate_package_includes(ZREF_PACKAGES),
            r"""
\makeatletter
\newcommand\dimtomm[1]{%
    \strip@pt\dimexpr 0.351459804\dimexpr#1\relax\relax%
}
\makeatother""",
            _checkbox_code(preview_mode),
            r"""
\usepackage{enumitem} % To resume an enumeration.
\setenumerate[0]{label=\protect\ptyxMCQcircled{\arabic*}}
\newlength{\ptyxMCQTabLength}
\newcommand{\ptyxMCQTab}[2]{%
  \settowidth{\ptyxMCQTabLength}{#1{}#2}
  \ifdim \ptyxMCQTabLength<\textwidth%
  \begin{tabular}{l@{\,\,}l}#1&#2\end{tabular}%
  \else%
  \begin{tabularx}{\linewidth}{l@{\,\,}X}#1&#2\end{tabularx}%
  \fi%
}""",
        ]
    )
    return first_part, second_part


def answers_and_score(
    config: Configuration, name: str, identifier: DocumentId, score: Optional[float]
) -> str:
    """Generate plain LaTeX code corresponding to score and correct answers."""
    table = table_for_answers(config, identifier)
    if score is not None:
        max_score = config.max_score
        score_latex = (
            r"""\begin{tikzpicture}
            \node[draw,very thick,rectangle, rounded corners,red!70!black] (0,0) {
            \begin{Large}
            Score~: %(score)s/%(max_score)s
            \end{Large}};
            \end{tikzpicture}"""
            % locals()
        )
    else:
        score_latex = ""
    left = MARGIN_LEFT_IN_CM
    right = MARGIN_RIGHT_IN_CM
    top = MARGIN_TOP_IN_CM
    bottom = MARGIN_BOTTOM_IN_CM
    paper = PAPER_FORMAT
    return (
        r"""
    \documentclass[%(paper)s,10pt]{article}
    \usepackage[utf8]{inputenc}
    \usepackage[document]{ragged2e}
    \usepackage{nopageno}
    \usepackage{tikz}
    \usepackage[left=%(left)scm,right=%(right)scm,top=%(top)scm,bottom=%(bottom)scm]{geometry}
    \parindent=0cm
    \usepackage{textcomp}

    \begin{document}
    \begin{Large}\textsc{%(name)s}\end{Large}
    \hfill%(score_latex)s

    \bigskip

    Solution~:
    \medskip

    %(table)s

    \end{document}
    """
        % locals()
    )
