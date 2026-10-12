from __future__ import annotations

import argparse
import http.server
import threading
from collections.abc import Iterator
from typing import Any, ClassVar

import pytest

from lastgreen import github
from lastgreen.cli import compare_run
from lastgreen.github import GitHubError, Json, RunRef, parse_run_ref
from tests.logbuilder import github_log

REPO = "octo/app"
STEPS = [
    ("Set up job", "success"),
    ("Run actions/checkout@v4", "success"),
    ("Set up Python", "success"),
    ("Install", "success"),
    ("Run tests", "failure"),
    ("Post Run actions/checkout@v4", "success"),
    ("Complete job", "success"),
]
FAILING = ("collected 2 items", "FAILED test_app.py::test_x - KeyError: 'id'", "1 failed")


class FakeApi:
    def __init__(self, routes: dict[str, Any], logs: dict[int, str]) -> None:
        self.routes = routes
        self.logs = logs
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    def get_json(self, path: str, params: dict[str, str] | None = None) -> Json:
        self.calls.append((path, params))
        key = path
        if params and "branch" in params:
            key += f"?branch={params['branch']}"
        if key not in self.routes:
            raise GitHubError(f"not found: {key}")
        value: Json = self.routes[key]
        return value

    def get_text(self, path: str) -> str:
        job_id = int(path.split("/")[-2])
        return self.logs[job_id]


def run(run_id: int, created: str, conclusion: str, sha: str, branch: str = "main") -> Json:
    return {
        "id": run_id,
        "run_attempt": 1,
        "workflow_id": 7,
        "head_branch": branch,
        "head_sha": sha * 40,
        "created_at": created,
        "conclusion": conclusion,
        "path": ".github/workflows/ci.yml",
        "html_url": f"https://github.com/{REPO}/actions/runs/{run_id}",
    }


def job(
    job_id: int, name: str, conclusion: str, steps: list[tuple[str, str]] | None = None
) -> Json:
    return {
        "id": job_id,
        "name": name,
        "conclusion": conclusion,
        "steps": [{"name": n, "conclusion": c} for n, c in steps or []],
    }


def jobs_page(*jobs: Json) -> Json:
    return {"total_count": len(jobs), "jobs": list(jobs)}


def scenario() -> FakeApi:
    """Run 30 fails in `test` and `lint`. Run 29 failed only in `lint`, so its `test` job is
    the last green one. Run 31 is newer than the failure and must be ignored."""
    red = run(30, "2026-10-11T10:00:00Z", "failure", "b")
    routes: dict[str, Any] = {
        f"/repos/{REPO}/actions/runs/30": red,
        f"/repos/{REPO}/actions/runs/30/attempts/1/jobs": jobs_page(
            job(300, "test", "failure", STEPS),
            job(301, "lint", "failure"),
        ),
        f"/repos/{REPO}": {"default_branch": "main"},
        f"/repos/{REPO}/actions/workflows/7/runs?branch=main": {
            "workflow_runs": [
                run(31, "2026-10-12T10:00:00Z", "success", "c"),
                red,
                run(29, "2026-10-10T10:00:00Z", "failure", "a"),
            ]
        },
        f"/repos/{REPO}/actions/runs/29/jobs": jobs_page(
            job(290, "test", "success"), job(291, "lint", "failure")
        ),
        f"/repos/{REPO}/compare/{'a' * 40}...{'b' * 40}": {
            "status": "ahead",
            "ahead_by": 1,
            "behind_by": 0,
            "commits": [{"sha": "b" * 40, "commit": {"message": "Bump pytest\n\nbody"}}],
            "files": [{"filename": "requirements.txt"}, {"filename": "app.py"}],
            "html_url": "https://github.com/octo/app/compare/a...b",
        },
    }
    logs = {
        290: github_log(),
        300: github_log(
            installed="iniconfig-2.1.0 pluggy-1.5.0 pytest-8.4.0",
            test_output=FAILING,
            failed=True,
        ),
    }
    return FakeApi(routes, logs)


def args(run_ref: str | None = None, **kw: Any) -> argparse.Namespace:
    return argparse.Namespace(run=run_ref, repo=kw.get("repo"), job=kw.get("job"))


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("123", RunRef(None, 123)),
        ("https://github.com/o/r/actions/runs/5", RunRef("o/r", 5)),
        ("https://github.com/o/r/actions/runs/5/attempts/2", RunRef("o/r", 5, 2)),
        ("https://github.com/o/r/actions/runs/5/job/9?pr=1", RunRef("o/r", 5, None, 9)),
    ],
)
def test_parse_run_ref(ref: str, expected: RunRef) -> None:
    assert parse_run_ref(ref) == expected


def test_parse_run_ref_rejects_other_urls() -> None:
    with pytest.raises(GitHubError, match="not a run"):
        parse_run_ref("https://github.com/o/r/pull/5")


def test_check_repo() -> None:
    assert github.check_repo("o/r") == "o/r"
    with pytest.raises(GitHubError):
        github.check_repo("o/r; rm -rf")


def test_compare_run_end_to_end() -> None:
    api = scenario()
    report = compare_run(args(f"https://github.com/{REPO}/actions/runs/30"), api)
    assert report.red is not None and report.green is not None
    assert (report.red.run_id, report.green.run_id) == (30, 29)
    assert report.step == "Run tests"
    assert [(c.name, c.old, c.new) for c in report.changes] == [("pytest", "8.3.3", "8.4.0")]
    assert [n.text for n in report.new_lines][:2] == [
        "FAILED test_app.py::test_x - KeyError: 'id'",
        "1 failed",
    ]
    assert report.code is not None
    assert report.code.commits == [("bbbbbbb", "Bump pytest")]
    assert report.code.notable_files == ["requirements.txt"]
    assert report.notes == ["also failed: lint (compare one with --job NAME)"]
    # Run 31 is newer than the failure and its jobs are never fetched.
    assert all("/runs/31/" not in path for path, _ in api.calls)


def test_falls_back_to_default_branch_with_note() -> None:
    api = scenario()
    api.routes[f"/repos/{REPO}/actions/runs/30"] = run(
        30, "2026-10-11T10:00:00Z", "failure", "b", branch="feature"
    )
    api.routes[f"/repos/{REPO}/actions/workflows/7/runs?branch=feature"] = {"workflow_runs": []}
    report = compare_run(args("30", repo=REPO), api)
    assert report.green is not None and report.green.run_id == 29
    assert "compared with main" in report.notes[0]


def test_own_repository_action_is_not_drift() -> None:
    api = scenario()
    api.logs[290] = (
        github_log() + f"Download action repository '{REPO}@{'a' * 40}' (SHA:{'a' * 40})\n"
    )
    api.logs[300] = (
        api.logs[300] + f"Download action repository '{REPO}@{'b' * 40}' (SHA:{'b' * 40})\n"
    )
    report = compare_run(args("30", repo=REPO), api)
    assert all(c.kind != "action" for c in report.changes)


def test_compare_failure_becomes_a_note() -> None:
    api = scenario()
    del api.routes[f"/repos/{REPO}/compare/{'a' * 40}...{'b' * 40}"]
    report = compare_run(args("30", repo=REPO), api)
    assert report.code is None
    assert report.notes[-1].startswith("could not compare commits")


def test_no_green_run() -> None:
    api = scenario()
    api.routes[f"/repos/{REPO}/actions/runs/29/jobs"] = jobs_page(job(290, "test", "failure"))
    with pytest.raises(GitHubError, match="no earlier successful run of job 'test'"):
        compare_run(args("30", repo=REPO), api)


def test_run_without_jobs() -> None:
    api = scenario()
    api.routes[f"/repos/{REPO}/actions/runs/30/attempts/1/jobs"] = jobs_page()
    with pytest.raises(GitHubError, match="invalid workflow file"):
        compare_run(args("30", repo=REPO), api)


def test_run_without_failed_jobs() -> None:
    api = scenario()
    api.routes[f"/repos/{REPO}/actions/runs/30/attempts/1/jobs"] = jobs_page(
        job(300, "test", "success")
    )
    with pytest.raises(GitHubError, match="no failed jobs"):
        compare_run(args("30", repo=REPO), api)


def test_unknown_job_name_lists_jobs() -> None:
    with pytest.raises(GitHubError, match="Jobs: lint, test"):
        compare_run(args("30", repo=REPO, job="build"), scenario())


def test_job_selected_by_name() -> None:
    api = scenario()
    api.routes[f"/repos/{REPO}/actions/runs/29/jobs"] = jobs_page(
        job(290, "test", "success"), job(291, "lint", "success")
    )
    api.logs[291] = github_log()
    api.logs[301] = github_log(failed=True)
    report = compare_run(args("30", repo=REPO, job="lint"), api)
    assert report.red is not None and report.red.job == "lint"


# A real HTTP round trip: the token must reach the API but not the log storage it redirects to.


class _Handler(http.server.BaseHTTPRequestHandler):
    seen: ClassVar[dict[str, str | None]] = {}

    def do_GET(self) -> None:
        _Handler.seen[self.path] = self.headers.get("Authorization")
        if self.path.startswith("/gone/"):
            self.send_response(404)
            self.end_headers()
            return
        if self.path.endswith("/logs"):
            self.send_response(302)
            self.send_header("Location", f"http://{self.headers['Host']}/blob")
            self.end_headers()
            return
        body = b"2026-10-07T14:03:05.7054779Z hello\n"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_token_is_not_forwarded_on_redirect(server: str) -> None:
    client = github.Client("secret-token", api_url=server)
    text = github.job_log(client, REPO, 1)
    assert text.endswith("hello\n")
    assert _Handler.seen[f"/repos/{REPO}/actions/jobs/1/logs"] == "Bearer secret-token"
    assert _Handler.seen["/blob"] is None


def test_missing_log_explains_retention(server: str) -> None:
    client = github.Client("t", api_url=server + "/gone")
    with pytest.raises(GitHubError, match="logs expire"):
        github.job_log(client, REPO, 1)
