# Questions and answers can be generated using Python programming language, like here.
# First, note that Python code is surrounded by lines of dots (at least 4 dots).

........................................
# Generate two positive or negative random integers, using special keyword `let`.
# Except from `let` special syntax, everything else is regular Python code.
let a, b in -5..5 with a*b < 0

# The proposed answers must be in a list:
all_answers = list(range(-25,26))

# The correct ones too:
correct_answers = [a*b]

# Uncomment the following line if you want the answers to be in random order.
# shuffle(all_answers)
........................................

# First, generate the question.
# Note that `#*` tag is a shortcut for `\times`.
# (In fact, it is a smarter \times, since it will add parentheses around second expression if needed).

The value of $#a#*#b$ is~:

# Now, let generate the answers using `#ANSWERS_LIST` tag.
# It takes two arguments:
# - the list of all the proposed answers
# - the list of the correct ones
# Note that when using `#ANSWERS_LIST`, the answers are not shuffled by default,
# but you may shuffle them with python of course, using `shuffle(all_answers)`.

#ANSWERS_LIST{all_answers}{correct_answers}

# Note that:
# - each answer must appear only once
# - each correct answer must appear in answer list.

# If some answers must be neutralized (i.e. ignored), maybe because there was an error
# in their content, you may add a neutralized_answers list, just like this:
# #ANSWERS_LIST[neutralized_answers]{all_answers}{correct_answers}