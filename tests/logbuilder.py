"""Build small GitHub-style job logs for tests, in the format the logs API returns."""

from __future__ import annotations

from collections.abc import Iterable


def stamp(lines: Iterable[str], start_second: int = 0) -> str:
    out = []
    for i, line in enumerate(lines):
        second = start_second + i // 10
        out.append(f"2026-10-07T14:{second // 60:02d}:{second % 60:02d}.{i:07d}Z {line}")
    return "﻿" + "\n".join(out) + "\n"


def github_log(
    *,
    image: str = "20260927.320.1",
    runner: str = "2.337.0",
    checkout_sha: str = "3d3c42e5aac5ba805825da76410c181273ba90b1",
    python: str = "3.12.6",
    git: str = "2.55.0",
    installed: str = "iniconfig-2.1.0 pluggy-1.5.0 pytest-8.3.3",
    test_output: Iterable[str] = ("collected 12 items", "12 passed in 0.41s"),
    failed: bool = False,
    start_second: int = 0,
) -> str:
    lines = [
        f"Current runner version: '{runner}'",
        "##[group]Operating System",
        "Ubuntu",
        "24.04.5",
        "LTS",
        "##[endgroup]",
        "##[group]Runner Image",
        "Image: ubuntu-24.04",
        f"Version: {image}",
        "##[endgroup]",
        "Prepare all required actions",
        f"Download action repository 'actions/checkout@v4' (SHA:{checkout_sha})",
        "Download action repository 'actions/setup-python@v5' "
        "(SHA:5fda3b95a4ea91299a34e894583c3862153e4b97)",
        "Complete job name: test",
        "##[group]Run actions/checkout@v4",
        "with:",
        "  repository: example/app",
        "##[endgroup]",
        "[command]/usr/bin/git version",
        f"git version {git}",
        "Temporarily overriding HOME='/home/runner/work/_temp/"
        "22664db0-75d0-4d58-a350-8ba0b5a6af48' before making global git config changes",
        "##[group]Run actions/setup-python@v5",
        "##[endgroup]",
        f"Successfully set up CPython ({python})",
        "##[group]Run pip install -r requirements.txt",
        "\x1b[36;1mpip install -r requirements.txt\x1b[0m",
        "##[endgroup]",
        f"Successfully installed {installed}",
        "##[group]Run pytest -q",
        "\x1b[36;1mpytest -q\x1b[0m",
        "##[endgroup]",
        *test_output,
    ]
    if failed:
        lines.append("##[error]Process completed with exit code 1.")
    lines += ["Post job cleanup.", "[command]/usr/bin/git version", f"git version {git}"]
    return stamp(lines, start_second)
