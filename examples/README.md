# Example logs

`green.log` and `red.log` are synthetic GitHub Actions job logs for a small project called
inventory, in the format the logs API returns (timestamps, `##[group]` markers, colour codes).
Between the two runs the runner image, `actions/setup-python`, CPython, pluggy, and pytest
changed, and one test lost its fixture. They are short enough to read in full.

```sh
uv run lastgreen diff examples/green.log examples/red.log
```
