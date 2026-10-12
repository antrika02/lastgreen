import pytest

from lastgreen.normalize import normalize


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("12 passed in 0.41s", "12 passed in 1.07s"),
        ("cache key setup-uv-2-abc1234def", "cache key setup-uv-2-9f8e7d6aaa"),
        (
            "HOME='/home/runner/work/_temp/22664db0-75d0-4d58-a350-8ba0b5a6af48'",
            "HOME='/home/runner/work/_temp/aee1235a-d8fb-4828-a225-4de044ea7146'",
        ),
        ("started 2026-10-07 14:03:05.123", "started 2026-10-09T01:00:00Z"),
        ("<object at 0x7f3a2b1c>", "<object at 0x10ab>"),
        ("wrote /tmp/tmpk2j9_xq1/out", "wrote /tmp/tmpzz81abcd/out"),
        ("a   b", "a b"),
    ],
)
def test_volatile_parts_compare_equal(a: str, b: str) -> None:
    assert normalize(a) == normalize(b)


def test_words_are_kept() -> None:
    assert normalize("E   AttributeError: no attribute 'yield_fixture'") == (
        "E AttributeError: no attribute 'yield_fixture'"
    )


def test_plain_words_that_look_hexish_survive() -> None:
    # "deadbeef" has no digit, "accepted" is a word: neither is an id.
    assert normalize("accepted deadbeef") == "accepted deadbeef"


def test_scm_version_suffix() -> None:
    assert normalize("pytest-9.2.0.dev355+g2950bc239") == normalize(
        "pytest-9.2.0.dev351+ge84e0631a"
    )
