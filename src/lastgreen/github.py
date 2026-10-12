"""The GitHub REST API calls lastgreen needs, using only the standard library."""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from lastgreen import __version__
from lastgreen.report import CodeChange

Json = dict[str, Any]

_RUN_URL = re.compile(
    r"^https?://[^/]+/(?P<repo>[^/]+/[^/]+)/actions/runs/(?P<run>\d+)"
    r"(?:/attempts/(?P<attempt>\d+))?(?:/job/(?P<job>\d+))?/?(?:[?#].*)?$"
)
_REMOTE = re.compile(r"github\.com[:/](?P<repo>[^/]+/[^/]+?)(?:\.git)?/?$")
_REPO = re.compile(r"^[\w.-]+/[\w.-]+$")

# Files whose change usually explains a dependency or workflow difference.
_NOTABLE = re.compile(
    r"(^\.github/workflows/|(^|/)(uv\.lock|poetry\.lock|Pipfile\.lock|requirements[^/]*\.txt|"
    r"package-lock\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb?|Cargo\.lock|go\.sum|"
    r"Gemfile\.lock|composer\.lock)$)"
)
FAILED = ("failure", "timed_out")


class GitHubError(Exception):
    """A problem the user can act on; the message says what to do."""


class Api(Protocol):
    def get_json(self, path: str, params: dict[str, str] | None = None) -> Json: ...

    def get_text(self, path: str) -> str: ...


def find_token() -> str | None:
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(name):
            return os.environ[name]
    gh = shutil.which("gh")
    if not gh:
        return None
    try:
        result = subprocess.run(
            [gh, "auth", "token"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None


class Client:
    def __init__(self, token: str, api_url: str | None = None) -> None:
        self.token = token
        self.api_url = (
            api_url or os.environ.get("GITHUB_API_URL") or "https://api.github.com"
        ).rstrip("/")

    def _open(self, path: str, params: dict[str, str] | None, accept: str) -> bytes:
        url = self.api_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url)
        request.add_header("Accept", accept)
        request.add_header("User-Agent", f"lastgreen/{__version__}")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        # Unredirected: the logs endpoint redirects to blob storage, which must not get the token.
        request.add_unredirected_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body: bytes = response.read()
                return body
        except urllib.error.HTTPError as error:
            raise _explain(error, path) from None
        except urllib.error.URLError as error:
            raise GitHubError(f"could not reach {self.api_url}: {error.reason}") from None

    def get_json(self, path: str, params: dict[str, str] | None = None) -> Json:
        data: Json = json.loads(self._open(path, params, "application/vnd.github+json"))
        return data

    def get_text(self, path: str) -> str:
        return self._open(path, None, "application/vnd.github+json").decode("utf-8", "replace")


def _explain(error: urllib.error.HTTPError, path: str) -> GitHubError:
    detail = ""
    with contextlib.suppress(ValueError, AttributeError):
        detail = json.loads(error.read()).get("message", "")
    if error.code == 401:
        return GitHubError("GitHub rejected the token (401). Run `gh auth login` or set GH_TOKEN.")
    if error.code in (403, 429) and (
        error.headers.get("X-RateLimit-Remaining") == "0" or "rate limit" in detail.lower()
    ):
        return GitHubError("GitHub API rate limit reached; try again after it resets.")
    if path.endswith("/logs") and error.code in (404, 410):
        return GitHubError(
            "the job log is not available: logs expire (90 days by default) "
            "and need a token that can read the repository's Actions."
        )
    if error.code == 404:
        return GitHubError(
            f"not found: {path}. Check the repository and run, and that your "
            "token can read this repository."
        )
    return GitHubError(f"GitHub API error {error.code} for {path}: {detail or error.reason}")


@dataclass
class RunRef:
    repo: str | None
    run_id: int
    attempt: int | None = None
    job_id: int | None = None


def parse_run_ref(ref: str) -> RunRef:
    """Accept a run or job URL from the browser, or a bare run id."""
    if ref.isdigit():
        return RunRef(None, int(ref))
    match = _RUN_URL.match(ref.strip())
    if not match:
        raise GitHubError(
            f"not a run: {ref!r}. Pass a URL like https://github.com/OWNER/REPO/actions/runs/123 "
            "or a run id with --repo OWNER/REPO."
        )
    attempt, job = match.group("attempt"), match.group("job")
    return RunRef(
        match.group("repo"),
        int(match.group("run")),
        int(attempt) if attempt else None,
        int(job) if job else None,
    )


def check_repo(repo: str) -> str:
    if not _REPO.match(repo):
        raise GitHubError(f"--repo must look like OWNER/REPO, got {repo!r}")
    return repo


def _git(*args: str) -> str | None:
    git = shutil.which("git")
    if not git:
        return None
    try:
        result = subprocess.run(
            [git, *args], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def repo_from_git() -> str | None:
    remote = _git("remote", "get-url", "origin")
    match = _REMOTE.search(remote) if remote else None
    return match.group("repo") if match else None


def current_branch() -> str | None:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    return branch if branch and branch != "HEAD" else None


def latest_failed_run(api: Api, repo: str, branch: str | None) -> int:
    params = {"status": "failure", "per_page": "1"}
    if branch:
        params["branch"] = branch
    runs = api.get_json(f"/repos/{repo}/actions/runs", params)["workflow_runs"]
    if not runs:
        where = f" on branch {branch}" if branch else ""
        raise GitHubError(f"no failed workflow runs{where} in {repo}.")
    return int(runs[0]["id"])


def jobs(api: Api, repo: str, run_id: int, attempt: int | None = None) -> list[Json]:
    path = f"/repos/{repo}/actions/runs/{run_id}"
    path += f"/attempts/{attempt}/jobs" if attempt else "/jobs"
    found: list[Json] = []
    for page in range(1, 11):
        data = api.get_json(path, {"per_page": "100", "page": str(page)})
        found += data["jobs"]
        if len(found) >= data.get("total_count", 0) or not data["jobs"]:
            break
    return found


def failed_jobs(job_list: list[Json]) -> list[Json]:
    return [j for j in job_list if j.get("conclusion") in FAILED]


def find_green(
    api: Api, repo: str, red_run: Json, job_name: str, max_runs: int = 100, max_job_lists: int = 30
) -> tuple[Json, Json, str | None] | None:
    """The most recent earlier run of the same workflow in which a job with the same name
    succeeded: first on the red run's branch, then on the default branch.
    Returns (run, job, note) where note explains a fallback."""
    for attempt in range(int(red_run.get("run_attempt") or 1) - 1, 0, -1):
        for job in jobs(api, repo, red_run["id"], attempt):
            if job["name"] == job_name and job.get("conclusion") == "success":
                return {**red_run, "run_attempt": attempt}, job, None

    branches: list[str] = [red_run["head_branch"]] if red_run.get("head_branch") else []
    default = api.get_json(f"/repos/{repo}").get("default_branch")
    if default and default not in branches:
        branches.append(default)

    budget = [max_job_lists]
    for branch in branches:
        found = _search_branch(api, repo, red_run, job_name, branch, max_runs, budget)
        if found:
            note = None
            if branch != red_run.get("head_branch"):
                note = (
                    f"no earlier green run of this job on {red_run.get('head_branch')}; "
                    f"compared with {branch}"
                )
            return found[0], found[1], note
    return None


def _search_branch(
    api: Api, repo: str, red_run: Json, job_name: str, branch: str, max_runs: int, budget: list[int]
) -> tuple[Json, Json] | None:
    path = f"/repos/{repo}/actions/workflows/{red_run['workflow_id']}/runs"
    seen = 0
    for page in range(1, max_runs // 50 + 2):
        params = {"branch": branch, "status": "completed", "per_page": "50", "page": str(page)}
        runs = api.get_json(path, params)["workflow_runs"]
        for run in runs:
            seen += 1
            if seen > max_runs or budget[0] <= 0:
                return None
            if run["id"] == red_run["id"] or run["created_at"] >= red_run["created_at"]:
                continue
            if run.get("conclusion") in ("skipped", "startup_failure", "action_required"):
                continue
            budget[0] -= 1
            for job in jobs(api, repo, run["id"]):
                if job["name"] == job_name and job.get("conclusion") == "success":
                    return run, job
        if len(runs) < 50:
            return None
    return None


def compare(api: Api, repo: str, base: str, head: str, workflow_path: str | None) -> CodeChange:
    data = api.get_json(f"/repos/{repo}/compare/{base}...{head}", {"per_page": "100"})
    commits = [
        (c["sha"][:7], c["commit"]["message"].splitlines()[0] if c["commit"]["message"] else "")
        for c in data.get("commits", [])
    ]
    files = [f["filename"] for f in data.get("files", [])]
    notable = [f for f in files if _NOTABLE.search(f) or f == workflow_path]
    return CodeChange(
        data["status"],
        int(data.get("ahead_by", 0)),
        int(data.get("behind_by", 0)),
        commits,
        notable,
        data.get("html_url", ""),
    )


def job_log(api: Api, repo: str, job_id: int) -> str:
    return api.get_text(f"/repos/{repo}/actions/jobs/{job_id}/logs")
