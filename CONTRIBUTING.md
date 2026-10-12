# Contributing

Thanks for helping. Wrong or noisy results are bugs, and they are the most useful reports.

## Reporting a problem

Include the command you ran, what lastgreen printed, and what you expected. If the output was
wrong, attach the smallest excerpts of the two logs that reproduce it (`lastgreen diff`
works on saved files). Check excerpts for secrets first: GitHub masks registered secrets as
`***`, but not everything a build prints.

## Development

You need [uv](https://docs.astral.sh/uv/). The repository pins Python 3.12 for development in
`.python-version`; lastgreen itself supports 3.10 and newer.

```sh
uv sync                     # create .venv with exact versions from uv.lock
uv run pytest               # all tests, about a second, no network
uv run ruff check . && uv run ruff format --check . && uv run mypy   # lint, format, types
uv run lastgreen diff examples/green.log examples/red.log           # try it
```

`uv run ruff format .` fixes formatting. The runtime uses only the standard library; please
keep it that way.

## Layout

| File | What it does |
| --- | --- |
| `src/lastgreen/joblog.py` | Cleans log lines and splits a GitHub job log into steps |
| `src/lastgreen/normalize.py` | Reduces a line to a template that ignores volatile values |
| `src/lastgreen/environment.py` | Runner, action, package, and version-line extraction and comparison |
| `src/lastgreen/newlines.py` | Lines of the failing step that are absent from the passing log |
| `src/lastgreen/github.py` | GitHub API client, run lookup, and the search for the green run |
| `src/lastgreen/report.py` | Text, Markdown, and JSON output |
| `src/lastgreen/cli.py` | Arguments and the end-to-end flow |

## Adding a package format

1. Add a pattern to `_PACKAGE_LINES` in `src/lastgreen/environment.py` with two groups:
   package name and version. It is matched against each cleaned log line.
2. Add the installer's real output, before and after an upgrade, to `test_package_formats`
   in `tests/test_environment.py`.
3. Run the tests and the linters, and add a line to the Unreleased section of CHANGELOG.md.

## Pull requests

Keep each pull request to one change, with tests. Tests must not use the network: use the
fake API in `tests/test_github.py` and the log builder in `tests/logbuilder.py`.
