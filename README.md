pTyX MCQ Extension
==================

MCQ generation (PDF files) and automatic marking of scanned students answers.

Overview
--------
pTyX is a LaTeX precompiler, written in Python.
pTyX enables to generate LaTeX documents, using custom commands or plain python code.
One single pTyX file may generate many latex documents, with different values.
I developed and used pTyX to make several versions of a same test in exams,
for my student, to discourage cheating.
Since it uses sympy library, pTyX has symbolic calculus abilities too.

The `pTyX MCQ extension` makes it easy to use pTyX to generate Multiple Choice Questions 
in the form of pdf documents.
The students MCQ can then be scanned and automatically corrected and marked.

Installation
------------

Obviously, pTyX needs a working Python installation.
Python version 3.8 (at least) is required for pTyX MCQ to run.

Currently, pTyX is only supported on GNU/Linux.

The easiest way to install it is to use pip.

    $ pip install --user ptyx_mcq

Usage
-----

To generate a template, run:

    $ mcq new new_folder

This will generate a `new_folder` folder with a `new.ptyx` file inside,
which is the main configuration file.

This will also create a `new_folder/questions/` folder, where you should put all the exercises, 
as `.txt` files. 

A few text files are already included as examples.

See the next section (*MCQ file format*) for more information about those files format.

To compile the template, run:

    $ mcq make

For more options:

    $ mcq make --help

To automatically corrected the scanned students MCQs, but them as a pdf inside `new_folder/scan`.

Then run:
    
    $ mcq scan


MCQ file format
---------------

When running `mcq new`, a template folder will be generated, including a `new.ptyx` file.

(More to come...)
