from lastgreen.analyze import compare_logs
from lastgreen.newlines import NewLine
from tests.logbuilder import github_log

FAILING_TESTS = (
    "collected 12 items",
    "FAILED tests/test_app.py::test_login - AttributeError: 'Client' has no attribute 'post_json'",
    "FAILED tests/test_app.py::test_logout - AttributeError: 'Client' has no attribute 'post_json'",
    "2 failed, 10 passed in 0.52s",
)


def test_new_lines_in_failing_step() -> None:
    report = compare_logs(github_log(), github_log(test_output=FAILING_TESTS, failed=True))
    assert report.step == "Run pytest -q"
    assert report.new_lines == [
        NewLine(
            33,
            "FAILED tests/test_app.py::test_login - AttributeError: "
            "'Client' has no attribute 'post_json'",
        ),
        NewLine(
            34,
            "FAILED tests/test_app.py::test_logout - AttributeError: "
            "'Client' has no attribute 'post_json'",
        ),
        NewLine(35, "2 failed, 10 passed in 0.52s"),
        NewLine(36, "Error: Process completed with exit code 1."),
    ]


def test_repeated_new_lines_collapse() -> None:
    output = ("collected 3 items", *["ERROR at setup of test_db_1 - ConnectionRefused"] * 3)
    report = compare_logs(github_log(), github_log(test_output=output, failed=True))
    assert report.new_lines[0].repeats == 3


def test_api_step_names_pick_the_failed_step() -> None:
    steps = [
        ("Set up job", "success"),
        ("Run actions/checkout@v4", "success"),
        ("Run actions/setup-python@v5", "success"),
        ("Install dependencies", "failure"),
        ("Run tests", "skipped"),
        ("Complete job", "success"),
    ]
    # Only three Run sections in the red log ran: tests were skipped.
    red = github_log().split("##[group]Run pytest -q")[0]
    report = compare_logs(github_log(), red, steps, "Install dependencies")
    assert report.step == "Install dependencies"


def test_environment_changes_and_new_lines_together() -> None:
    report = compare_logs(
        github_log(),
        github_log(
            installed="iniconfig-2.1.0 pluggy-1.5.0 pytest-8.4.0",
            test_output=FAILING_TESTS,
            failed=True,
        ),
    )
    assert [(c.name, c.old, c.new) for c in report.changes] == [("pytest", "8.3.3", "8.4.0")]
    assert len(report.new_lines) == 4
