# New algorithms for calculating scores

## Rational
Currently, all evaluation algorithms use only basic metrics: the number of correct answers, of incorrect answers, and of checked and unchecked answers among the previous category.

While this working great in most cases, this is not always meaningful. In particular, this is unsatisfactory for question like "What is the number of...".

For this kind of question, the correct answer should lead to the maximal score, but the distance between the checked answer and the correct one should also be considered when evaluating the answer.

## Proposition
Instead of associating only a boolean with each answer, it should be possible to associate a value with each answer, indicating the score earn for each checked answer.
If several answers are checked, the score should be the average of the scores of each checked answer.
