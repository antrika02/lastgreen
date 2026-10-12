# lastgreen

[![ci](https://github.com/thanatchon36/lastgreen/actions/workflows/ci.yml/badge.svg)](https://github.com/thanatchon36/lastgreen/actions/workflows/ci.yml)

Your CI went red, and the diff looks harmless. lastgreen finds the last green run of the same
GitHub Actions job, downloads both logs, and tells you what changed between them: the runner
image, action commits, tool and package versions, the commits in between, and the log lines
that only appear in the failing step.

```sh
uvx --from git+https://github.com/thanatchon36/lastgreen lastgreen https://github.com/OWNER/REPO/actions/runs/RUN_ID
```

Paste the URL of a failed run (or of one of its jobs). Run inside a clone with no URL and it
picks the latest failed run on your current branch. You need [uv](https://docs.astral.sh/uv/)
and a GitHub token: GitHub only serves Actions logs to authenticated requests, even for
public repositories. lastgreen uses `GH_TOKEN` or `GITHUB_TOKEN` if set, otherwise
`gh auth token`. It has no dependencies outside the Python standard library (3.10+), and the
only network requests it makes are to the GitHub API and to the log download URLs it returns.

## Example

This is a real failure in [pypa/pip](https://github.com/pypa/pip/actions/runs/33264798602):
a Windows test shard went red after a merge that only bumped a GitHub Action.

```text
$ lastgreen https://github.com/pypa/pip/actions/runs/33264798602 --max-lines 6
red    run 33264798602 attempt 1  tests / 3.14 / Windows / 1  a3dfd76  2026-08-29 17:07
green  run 32676283451 attempt 1  tests / 3.14 / Windows / 1  6154f11  2026-08-24 00:18
code   2 commits between green and red
         f01efc9 chore: Bump re-actors/alls-green in the github-actions group
         a3dfd76 Merge pull request #14288 from pypa/dependabot/github_actions/github-actions-a0e36ab01e
         changed: .github/workflows/ci.yml
note   also failed: tests / 3.10 / macos-latest, check (compare one with --job NAME)

Environment changes (4)
  runner image              windows-2025-vs2026 20260818.207.1 → windows-2025-vs2026 20260824.214.3
  package platformdirs      4.11.3 → 4.11.5
  package python_discovery  1.5.2 → 1.6.0
  package virtualenv        21.7.4 → 21.7.7

New lines in failing step "Run tests (shard 1 of 3)" (first 6 of 124)
  1937  [gw0] [ 74%] RERUN tests/functional/test_truststore.py::test_no_truststore_can_install[GitHub]  (x3)
  1965  [gw0] [ 75%] FAILED tests/functional/test_truststore.py::test_no_truststore_can_install[GitHub]
  2365  [gw0] [ 94%] PASSED tests/functional/test_install_report.py::test_install_report_editable_local_path_with_extras
  2472  [gw2] [100%] PASSED tests/functional/test_install_vcs_git.py::test_git_install_branch_again_after_branch_changes
  2474  ================================== FAILURES ===================================
  2475  ___________________ test_no_truststore_can_install[GitHub] ____________________
```

The code change touched only a workflow file, but the job also ran on a new Windows image and
installed newer versions of virtualenv, platformdirs, and python-discovery. Line numbers point
into the failing job's log. GitHub deletes logs after 90 days by default, so this exact command
stops working at the end of November 2026.

To try lastgreen without a token, compare the two logs bundled in [`examples/`](examples), a
synthetic project whose tests broke after a pytest upgrade:

```sh
git clone https://github.com/thanatchon36/lastgreen && cd lastgreen
uvx --from . lastgreen diff examples/green.log examples/red.log
```

```text
Environment changes (5)
  runner image                     ubuntu-24.04 20260928.322.1 → ubuntu-24.04 20261005.329.1
  action actions/setup-python      v5 5fda3b9 → v5 a26af69
  Successfully set up CPython (…)  3.12.6 → 3.12.7
  package pluggy                   1.5.0 → 1.6.0
  package pytest                   8.3.3 → 8.4.0

New lines in failing step "Run pytest -q" (11)
  51  ..................E......................                                [100%]
  52  ==================================== ERRORS ====================================
  53  ____________________ ERROR at setup of test_reserve_stock _____________________
  54  file /home/runner/work/inventory/inventory/tests/test_orders.py, line 41
  55    async def test_reserve_stock(db):
  56  E       fixture 'db' not found
  57  >       available fixtures: cache, capfd, capsys, event_loop_policy, monkeypatch, tmp_path
  58  =========================== short test summary info ============================
  59  ERROR tests/test_orders.py::test_reserve_stock
  60  39 passed, 1 error in 1.91s
  61  Error: Process completed with exit code 1.
```

## Why

A job that passed on Monday and fails on Tuesday ran in a different environment, even when
nobody touched the workflow:

- GitHub rebuilds its hosted runner images about once a week, and you cannot pin an older one.
- `actions/setup-python@v5` and other tag references move to new commits.
- `python-version: 3.12`, `pip install pytest`, and unlocked dependencies resolve to whatever
  is newest that day.

All of this is written in the two logs, mixed into several thousand lines of timestamps,
progress bars, and temporary paths. Diffing them by hand means downloading both, stripping
timestamps, and still wading through noise. lastgreen does that comparison and prints only
what differs.

## Use cases

- **"Nothing changed but CI broke."** See at a glance whether the runner image, a tool, or a
  dependency moved, and to what.
- **Triage a dependency upgrade.** The package table lists every version that changed between
  the passing and failing install, including transitive ones.
- **Read a long failing log quickly.** The new lines section skips everything that also
  appeared in the passing run, so the first lines shown are usually the error.
- **Any CI, offline.** `lastgreen diff GREEN.log RED.log` works on two saved logs from
  GitLab, Jenkins, Buildkite, or a local build. Step detection and the runner sections are
  specific to GitHub; package and version detection and the new lines work on any text log.
- **Post the comparison where people look.** `--format markdown` renders tables for an issue,
  a pull request comment, or a job summary (see below).

## Usage

```text
lastgreen [RUN] [options]          compare a failed GitHub Actions job with its last green run
lastgreen diff GREEN.log RED.log   compare two log files from any CI

  RUN             run URL, job URL, or run id (with --repo)
  --repo O/R      repository, when RUN is a bare id or there is no RUN
  --job NAME      job to compare (default: the first failed job)
  --format F      text (default), markdown, or json
  --max-lines N   new log lines to show (default 30; json always includes all)
```

Exit status is 0 when a comparison was printed, 1 when it could not be made (with the reason on
stderr), and 2 for invalid arguments.

### Run it automatically on failure

This workflow runs after your `ci` workflow fails and writes the comparison to its job summary.
It needs read access to Actions and contents, nothing else:

```yaml
name: lastgreen
on:
  workflow_run:
    workflows: [ci]
    types: [completed]

permissions:
  actions: read
  contents: read

jobs:
  compare:
    if: github.event.workflow_run.conclusion == 'failure'
    runs-on: ubuntu-latest
    steps:
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
      - env:
          GH_TOKEN: ${{ github.token }}
          RUN_URL: ${{ github.event.workflow_run.html_url }}
        run: |
          uvx --from git+https://github.com/thanatchon36/lastgreen@v0.1.0 \
            lastgreen "$RUN_URL" --format markdown >> "$GITHUB_STEP_SUMMARY"
```

## How it works

1. **Find the pair.** From the failed run, lastgreen takes the first failed job (or `--job`)
   and walks back through earlier runs of the same workflow on the same branch until that job
   name succeeded, then tries the default branch. A run that failed overall still counts if
   this job passed in it. It looks at up to 100 runs.
2. **Read the environment.** From each log it collects the runner image, OS, and runner
   version from the job preamble, and the commit every action resolved to. It reads package
   versions from installer output: pip, uv, tox, poetry, cargo, go, bundler, and pnpm. Any
   other line that appears exactly once in both logs and differs only in a version number,
   such as `git version 2.55.0` or `Successfully set up CPython (3.12.7)`, is reported too,
   so tools without a rule are still caught.
3. **Find new lines.** Every line of the failing step is reduced to a template (timestamps,
   durations, hashes, UUIDs, memory addresses, temporary names, and numbers removed). Lines
   whose template never occurs anywhere in the passing log are shown in order, with repeats
   collapsed. Comparing against the whole log rather than line by line keeps the result
   stable when parallel tests print in a different order.
4. **Show the commits.** The GitHub compare API lists the commits between the two runs and
   flags changed workflow files and lockfiles.

## Limitations

- GitHub Actions is the only CI it can fetch from; for others, save the logs and use `diff`.
- Logs must still exist (90 days by default) and the token must be able to read the
  repository's Actions.
- Jobs are matched by exact name. A renamed job or matrix entry has no earlier green run.
- Version detection is heuristic. A line that occurs more than once in a log is ignored for
  tool versions, and a two-part number counts only on a line that says "version", so some
  changes are missed rather than invented. npm and yarn print no per-package versions during
  install, so their packages are not listed.
- New lines include anything that is new, not only errors: a test added in the same commit
  shows up as a new `PASSED` line.
- A comparison makes between 8 and about 45 API requests, one after another; the pip
  example above took about 14 seconds.

## Roadmap

- Compare every failed job of a run in one report.
- Use the jobs API step timestamps to split logs for steps whose header is not `Run …`.
- More package formats (Maven, Gradle, NuGet, Composer).
- A second baseline: the most recent green run of the same commit, to separate flaky
  failures from real ones.

## Contributing

Bug reports with two log excerpts that produce a wrong or noisy result are the most useful.
See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests, and how to add a package format.

## License

[MIT](LICENSE)
