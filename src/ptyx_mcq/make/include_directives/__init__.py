"""Parser used to include files in a ptyx file.

Ptyx-mcq accept the following syntax to include a file:

    -- path/to/file

There must be at least one space after the two dashed.

To disable an include, add a `!` just before the dashes:

    !-- path/to/file

    --

(You may also simply comment the line using the `#` character with a space after,
which is the usual syntax to comment pTyX code, but this is less convenient).

By default, when relative, paths to files refer to the directory where the ptyx file
is located.

The following syntax allows to change the directory where the files are searched.
-- DIR: /path/to/main/directory
This will change the search directory for every subsequent path, at least
until another `-- DIR:` directive occurs (search directory may be changed
several times).

The files list may be semi-automatically updated using `.update()` method,
which search for new files and missing files in the default directory,
and in any directory declared through the `-- DIR:` directive.

Directives may be prefixed with comments: @<comment>:<directive>,
where <comment> is a single word (\\w+).

New files will be added with the `@new:` prefix:

    @new: -- path/relative/to/declared/directory/file.ex

Files not found will appear with the `@missing:` prefix,
and the directive will be disabled with `!`:

    @missing: !-- declared/path/file.ex

Coefficients may be appended to directives, using `:` as separator:

    -- path/to/file.ex:2

An evaluation method may be provided too:

    -- path/to/file.ex:2,all

Or without setting the coefficient:

    -- path/to/file.ex:all

If the path contain colons, the final colons are mandatory:

    -- strang:e/pa:th/w:ith/c:o:l:o:n:s.ex:

"""
