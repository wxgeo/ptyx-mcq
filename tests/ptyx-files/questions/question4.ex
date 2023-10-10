* Select the correct code:

# If `@@` is used the line before an answer, the following answers will be displayed in verbatim mode:
# a fixed-width font is used, spaces are kept intact and latex special characters like `{` or `$`
# are escaped.
# By default, if the answer is on several lines, it is supposed to use the full page width.
# The width can be manually reduced using `{6cm}`, or `{.5}` which stands for ``{.5\linewidth}`.
# Combining verbatim mode and reduced width is useful to display code:

<->.45
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

# To remove verbatim formatting and width restrictions for an answer (and any following),
# just write a single `@` the line before:

@
- No answer is correct