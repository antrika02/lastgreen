# Security policy

lastgreen reads a GitHub token from `GH_TOKEN`, `GITHUB_TOKEN`, or `gh auth token`, and sends
it only to the GitHub API (`GITHUB_API_URL`, default `https://api.github.com`). When GitHub
redirects a log download to its storage service, the token is not forwarded. lastgreen only
reads: it never re-runs jobs or writes to a repository, and a token with read access to
Actions and contents is enough. It runs `git remote get-url origin` and
`git rev-parse --abbrev-ref HEAD` when no run is given. It stores nothing on disk.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub: open the **Security** tab of this
repository and choose **Report a vulnerability**. Do not open a public issue.

You can expect an acknowledgement within a week. Fixes are released as a new patch version
and noted in [CHANGELOG.md](CHANGELOG.md).

## Supported versions

Only the latest release receives fixes.
