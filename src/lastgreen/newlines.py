"""Lines in the failing step that never appeared in the passing run."""

from __future__ import annotations

from dataclasses import dataclass

from lastgreen.joblog import ERROR_PREFIX, JobLog, Step
from lastgreen.normalize import normalize

_IGNORED = ("##[endgroup]", "##[group]")


@dataclass(frozen=True)
class NewLine:
    line: int  # 1-based line number in the failing run's log
    text: str
    repeats: int = 1  # how many lines in the step share this template


def display(text: str) -> str:
    return "Error: " + text[len(ERROR_PREFIX) :] if text.startswith(ERROR_PREFIX) else text


def new_lines(step: Step, green: JobLog) -> list[NewLine]:
    """Every line of `step` whose normalized form is absent from the whole passing log,
    in order, collapsing repeats of the same template into the first occurrence.

    Comparing against the whole passing log rather than a line-by-line diff keeps the
    result stable when parallel tests print in a different order."""
    known = {normalize(text) for _, text in green.lines}
    first: dict[str, int] = {}
    found: list[NewLine] = []
    for number, text in step.lines:
        if not text.strip() or text.startswith(_IGNORED):
            continue
        template = normalize(text)
        if template in known:
            continue
        if template in first:
            index = first[template]
            found[index] = NewLine(found[index].line, found[index].text, found[index].repeats + 1)
            continue
        first[template] = len(found)
        found.append(NewLine(number, display(text)))
    return found
