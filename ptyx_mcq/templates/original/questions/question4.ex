#LOAD{mcq}
# The following number is used to initialize the pseudorandom numbers generator.
# Feel free to change it.
#SEED{124456}

===========================
sty = amssymb, amsmath, [table]xcolor, alltt
correct = 1
incorrect = 0
skipped = 0
# floor = 0
# ceil = 1
mode=correct_minus_incorrect_linear
id format=8 digits
---------------------------
# You may include here raw LaTeX code (definition of new LaTeX commands for example).
# It will be appended to the LaTeX preamble.

===========================

# You may include raw LaTeX code here as well.
# It will then be added ** after ** the LaTeX preamble.



<<<<<<<<<<<<<<<<<
* Select the correct code:

# If `@@` is used the line before an answer, the following answers will be displayed in verbatim mode:
# a fixed-width font is used, spaces are kept intact and latex special characters like `{` or `$`
# are escaped.
# This is useful to display code:

@@
+ public double getNorm() {
	int i, sum = 0;
	for (i=0; i<counts.length; i++) {
		sum += counts[i]*counts[i]; }
	return Math.sqrt(sum); }

- public double getNorm() {
	int i, sum = 0;
	for (i=0; i<counts.length; i++) {
		sum += counts[i]*counts[i]; }
	return Math.pow(sum, 2); }

# To remove verbatim formatting for an answer (and any following), write a single `@` the line before:

@
- No answer is correct
>>>>>>>>>>>>>>>>>