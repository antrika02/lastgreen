from lastgreen import joblog
from tests.logbuilder import github_log, stamp


def test_strips_bom_timestamps_and_ansi() -> None:
    log = joblog.parse(stamp(["\x1b[36;1mpytest -q\x1b[0m", "done"]))
    assert log.lines == [(1, "pytest -q"), (2, "done")]


def test_splits_github_steps() -> None:
    log = joblog.parse(github_log())
    assert [s.name for s in log.steps] == [
        "Set up job",
        "Run actions/checkout@v4",
        "Run actions/setup-python@v5",
        "Run pip install -r requirements.txt",
        "Run pytest -q",
        "Post job cleanup",
    ]


def test_plain_log_is_one_step() -> None:
    log = joblog.parse("compiling\nerror: boom\n")
    assert [s.name for s in log.steps] == ["log"]
    assert joblog.failing_step(log).name == "log"


def test_failing_step_prefers_error_annotation_over_last_step() -> None:
    log = joblog.parse(github_log(failed=True))
    assert joblog.failing_step(log).name == "Run pytest -q"


def test_failing_step_by_name_falls_back_when_missing() -> None:
    log = joblog.parse(github_log(failed=True))
    assert joblog.failing_step(log, "Run pip install -r requirements.txt").name.startswith(
        "Run pip"
    )
    assert joblog.failing_step(log, "No such step").name == "Run pytest -q"


def test_failing_step_without_error_is_last_step_before_cleanup() -> None:
    log = joblog.parse(github_log())
    assert joblog.failing_step(log).name == "Run pytest -q"


def test_apply_step_names_aligns_skipping_skipped_and_post_steps() -> None:
    log = joblog.parse(github_log())
    api = [
        ("Set up job", "success"),
        ("Run actions/checkout@v4", "success"),
        ("Set up Python", "success"),
        ("Lint", "skipped"),
        ("Install", "success"),
        ("Test", "failure"),
        ("Post Run actions/checkout@v4", "success"),
        ("Complete job", "success"),
    ]
    joblog.apply_step_names(log, api)
    assert [s.name for s in log.steps][1:5] == [
        "Run actions/checkout@v4",
        "Set up Python",
        "Install",
        "Test",
    ]


def test_apply_step_names_keeps_headers_when_counts_differ() -> None:
    log = joblog.parse(github_log())
    joblog.apply_step_names(log, [("Only one", "success")])
    assert log.steps[1].name == "Run actions/checkout@v4"
