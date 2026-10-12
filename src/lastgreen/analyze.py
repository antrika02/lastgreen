"""Compare two job logs: the offline core shared by both commands."""

from __future__ import annotations

from collections.abc import Sequence

from lastgreen import environment, joblog
from lastgreen.newlines import new_lines
from lastgreen.report import Report


def compare_logs(
    green_text: str,
    red_text: str,
    red_steps: Sequence[tuple[str, str | None]] = (),
    failed_step: str | None = None,
) -> Report:
    """`red_steps` and `failed_step` come from the jobs API when available; they give the
    failing log's sections their real names and pick the step that failed."""
    green = joblog.parse(green_text)
    red = joblog.parse(red_text)
    if red_steps:
        joblog.apply_step_names(red, red_steps)
    step = joblog.failing_step(red, failed_step)
    changes = environment.compare(environment.extract(green), environment.extract(red))
    return Report(step=step.name, changes=changes, new_lines=new_lines(step, green))
