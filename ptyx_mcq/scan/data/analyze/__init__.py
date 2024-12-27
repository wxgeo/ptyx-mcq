"""
Analyze the data extracted from the input pdf.

This means:
- detecting checkboxes
- evaluating checkboxes state
- retrieving student name and identifier
"""

from ptyx_mcq.scan.data.analyze.checkboxes import analyze_checkboxes
from ptyx_mcq.scan.data.analyze.student_names import read_student_id_and_name

__all__ = ["analyze_checkboxes", "read_student_id_and_name"]
