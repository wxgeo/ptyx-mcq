# First, just write the question.

How many edges has a square ?

# Write now the answers.

# Note that wrong answers are introduced by `- `,
# while correct ones are introduced by `+ `.

- 1
- 2
- 3
+ 4

# Adjacent answers (like the four previous ones) will be shuffled.
# By separating answers with (at least) a blank line, you define answers blocks.
# Random shuffling occurs inside each answer block, but the order of the answers blocks
# themselves is kept unchanged.

# So here, since the following answer (`- none`) is separated
# from the four previous ones with (at least) a blank line,
# it will always appear after all the others.

- none

# Note: suppose now you discover during or after the examination that an answer
# was ambiguous, or even gibberish. :(
# To neutralize the corresponding answer, juste replace `+` or `-` with `!`,
# then compile again the document.
# Any answer starting with `!` will be ignored when calculating the score.


# Use the keyword `OR` to define a variant of the same question.
OR

How many edges has a circle ?
- 1
- 2
- 3
- 4
+ none
