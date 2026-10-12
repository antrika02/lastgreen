"""Split a CI job log into clean lines and steps."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

# GitHub prefixes every line with an ISO 8601 timestamp with 7 fractional digits.
_TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z ?")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_STEP_START = re.compile(r"^##\[group\](Run .+)$")
_POST_STEP = "Post job cleanup."
ERROR_PREFIX = "##[error]"

SETUP_STEP = "Set up job"
POST_STEP = "Post job cleanup"

Line = tuple[int, str]
"""A 1-based line number in the original log and the line's cleaned text."""


@dataclass
class Step:
    name: str
    lines: list[Line] = field(default_factory=list)

    def has_error(self) -> bool:
        return any(text.startswith(ERROR_PREFIX) for _, text in self.lines)


@dataclass
class JobLog:
    lines: list[Line]
    steps: list[Step]

    def step(self, name: str) -> Step | None:
        return next((s for s in self.steps if s.name == name), None)


def clean_line(raw: str) -> str:
    return _ANSI.sub("", _TIMESTAMP.sub("", raw, count=1)).rstrip()


def parse(text: str) -> JobLog:
    """Parse a log. GitHub job logs are split at their `##[group]Run …` step headers;
    any other log becomes a single step named "log"."""
    lines = [(i, clean_line(raw)) for i, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1)]
    steps = [Step(SETUP_STEP)]
    for line in lines:
        text = line[1]
        match = _STEP_START.match(text)
        if match:
            steps.append(Step(match.group(1).strip()))
        elif text == _POST_STEP and steps[-1].name != POST_STEP:
            steps.append(Step(POST_STEP))
        steps[-1].lines.append(line)
    if len(steps) == 1:
        steps[0].name = "log"
    return JobLog(lines, steps)


def apply_step_names(log: JobLog, api_steps: Sequence[tuple[str, str | None]]) -> None:
    """Rename `Run <command>` sections to the step names the API reports.

    `api_steps` is (name, conclusion) in order. Skipped steps write nothing to the log,
    and the setup, completion, and post steps are not `Run` sections, so they are left
    out before aligning. If the counts disagree the log's own headers are kept."""
    names = [
        name
        for name, conclusion in api_steps
        if conclusion != "skipped"
        and name not in (SETUP_STEP, "Complete job")
        and not name.startswith("Post ")
    ]
    sections = [s for s in log.steps if s.name not in (SETUP_STEP, POST_STEP)]
    if len(names) == len(sections):
        for section, name in zip(sections, names, strict=True):
            section.name = name


def failing_step(log: JobLog, name: str | None = None) -> Step:
    """The step named `name` if present, else the first step with an error annotation
    (ignoring post-job cleanup), else the last step that ran."""
    if name:
        named = log.step(name)
        if named:
            return named
    candidates = [s for s in log.steps if s.name != POST_STEP] or log.steps
    return next((s for s in candidates if s.has_error()), candidates[-1])
