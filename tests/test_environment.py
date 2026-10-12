from lastgreen import environment, joblog
from lastgreen.environment import Change
from tests.logbuilder import github_log, stamp


def changes(green: str, red: str) -> list[Change]:
    return environment.compare(
        environment.extract(joblog.parse(green)), environment.extract(joblog.parse(red))
    )


def test_identical_logs_have_no_changes() -> None:
    assert changes(github_log(), github_log(start_second=30)) == []


def test_runner_image_and_runner_version() -> None:
    found = changes(github_log(), github_log(image="20261004.325.1", runner="2.338.0"))
    assert found == [
        Change(
            "runner", "runner image", "ubuntu-24.04 20260927.320.1", "ubuntu-24.04 20261004.325.1"
        ),
        Change("runner", "runner version", "2.337.0", "2.338.0"),
    ]


def test_action_moved_to_new_commit() -> None:
    found = changes(
        github_log(), github_log(checkout_sha="11bd71901bbe5b1630ceea73d27597364c9af683")
    )
    assert found == [Change("action", "actions/checkout", "v4 3d3c42e", "v4 11bd719")]


def test_action_pinned_by_sha_shows_sha_only() -> None:
    sha_a, sha_b = "a" * 40, "b" * 40
    green = stamp([f"Download action repository 'o/act@{sha_a}' (SHA:{sha_a})"])
    red = stamp([f"Download action repository 'o/act@{sha_b}' (SHA:{sha_b})"])
    assert changes(green, red) == [Change("action", "o/act", "aaaaaaa", "bbbbbbb")]


def test_tools_found_without_specific_rules() -> None:
    found = changes(github_log(), github_log(python="3.12.7"))
    assert found == [Change("tool", "Successfully set up CPython (…)", "3.12.6", "3.12.7")]


def test_repeated_lines_are_not_used_for_tool_versions() -> None:
    # `git version` appears twice in each log, so it is ambiguous and skipped.
    found = changes(github_log(), github_log(git="2.56.0"))
    assert found == []


def test_pip_packages_upgraded_added_removed() -> None:
    green = github_log(installed="iniconfig-2.1.0 pluggy-1.5.0 pytest-8.3.3 tomli-2.0.1")
    red = github_log(installed="iniconfig-2.1.0 pluggy-1.6.0 pytest-8.4.0 typing_extensions-4.12.2")
    assert changes(green, red) == [
        Change("package", "pluggy", "1.5.0", "1.6.0"),
        Change("package", "pytest", "8.3.3", "8.4.0"),
        Change("package", "tomli", "2.0.1", None),
        Change("package", "typing_extensions", None, "4.12.2"),
    ]


def test_package_formats() -> None:
    green = stamp(
        [
            "typing: asgiref==3.12.1,blinker==1.9.0,flask @ file:///home/runner/work/x",
            " + ruff==0.6.1",
            "   Compiling serde v1.0.210",
            "go: downloading golang.org/x/sys v0.25.0",
            "Installing rake 13.2.1",
            "  - Installing requests (2.32.2)",
            "+ left-pad 1.3.0",
        ]
    )
    red = stamp(
        [
            "typing: asgiref==3.12.2,blinker==1.9.0,flask @ file:///home/runner/work/x",
            " - ruff==0.6.1",
            " + ruff==0.7.0",
            "   Compiling serde v1.0.211",
            "go: downloading golang.org/x/sys v0.26.0",
            "Installing rake 13.2.1",
            "  - Updating requests (2.32.2 -> 2.32.3)",
            "+ left-pad 1.3.1",
        ]
    )
    assert {(c.name, c.old, c.new) for c in changes(green, red)} == {
        ("asgiref", "3.12.1", "3.12.2"),
        ("ruff", "0.6.1", "0.7.0"),
        ("serde", "1.0.210", "1.0.211"),
        ("golang.org/x/sys", "v0.25.0", "v0.26.0"),
        ("requests", "2.32.2", "2.32.3"),
        ("left-pad", "1.3.0", "1.3.1"),
    }


def test_package_names_are_normalized_across_spellings() -> None:
    green = stamp(["Successfully installed Typing_Extensions-4.12.2"])
    red = stamp(["Successfully installed typing-extensions-4.12.2"])
    assert changes(green, red) == []


def test_sizes_percentages_and_ips_are_not_versions() -> None:
    green = stamp(
        [
            "Received 995092 of 995092 (100.0%), 1.5 MBs/sec",
            "Listening on 10.1.0.4:8080",
            "Took 2.5 s",
        ]
    )
    red = stamp(
        [
            "Received 995092 of 995092 (100.0%), 3.25 MBs/sec",
            "Listening on 10.1.0.17:8080",
            "Took 7.75 s",
        ]
    )
    assert changes(green, red) == []


def test_same_version_change_in_several_lines_is_grouped() -> None:
    green = stamp(
        [
            "Using CPython 3.12.6 interpreter at: /opt/Python/3.12.6/x64/bin/python3",
            "Successfully set up CPython (3.12.6)",
        ]
    )
    red = stamp(
        [
            "Using CPython 3.12.7 interpreter at: /opt/Python/3.12.7/x64/bin/python3",
            "Successfully set up CPython (3.12.7)",
        ]
    )
    assert changes(green, red) == [
        Change("tool", "Successfully set up CPython (…)", "3.12.6", "3.12.7", also=1)
    ]


def test_two_component_versions_need_a_version_cue() -> None:
    green = stamp(["Hosted Compute Agent Version: 20260901.588", "ratio 1.5"])
    red = stamp(["Hosted Compute Agent Version: 20261001.601", "ratio 2.5"])
    assert changes(green, red) == [
        Change("tool", "Hosted Compute Agent Version: …", "20260901.588", "20261001.601")
    ]
