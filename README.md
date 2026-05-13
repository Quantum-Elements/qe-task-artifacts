# QE Task Artifacts

Tiny interface package for task-scoped artifact saving.

QEAM / physics code should not need to know about Celery, S3, task IDs, or
auth tokens to drop a file alongside a running task. This package lets you
save artifacts with **one decorator and one function call**.

## Installation

```bash
pip install "qe-task-artifacts @ git+https://github.com/Quantum-Elements/qe-task-artifacts.git@v0.2.0"
```

## TL;DR — the only pattern you need

Add `@with_artifacts` to your function. Inside, call `save_artifact(...)`.

```python
from qe_task_artifacts import with_artifacts, save_artifact


@with_artifacts
def error_budget(input_data, gate, *, gates_def=None, pulses_def=None):
    report = compute(input_data, gate, gates_def, pulses_def)

    save_artifact("output/error_report.json", report, format="json")
    save_artifact("output/ptm.npy", report["ptm"], format="numpy")

    return report
```

That's it. No `artifacts=` parameter to thread through your signatures. No
`if artifacts.enabled()` guards required. When the function runs inside a
task on the worker, artifacts land in the task's S3 folder. When it runs in
a unit test, a notebook, or a local script, the saves are silent no-ops.

## How it works

- `@with_artifacts` wraps your function so the call site can optionally pass
  an `artifacts=` keyword. When given, it's parked in a `ContextVar` for the
  duration of the call.
- The worker (e.g. `julia-celery-worker`'s `TaskFileContext`) sets the same
  `ContextVar` automatically when a task starts. So in production you get a
  writer "for free" -- no need to plumb `artifacts=` through `tasks.py`.
- `save_artifact(name, obj, format=...)` reads from the `ContextVar` and
  dispatches to the active writer.
- If no writer is active, `save_artifact` checks `writer.enabled()` (which is
  `False` for the default `NoopArtifactWriter`) and silently does nothing.

## Path conventions

Artifact `name`s are POSIX paths, **relative** to the task's folder:

- `input/...` — task inputs (params, source circuits)
- `output/...` — terminal results
- `artifacts/...` — intermediate / diagnostic outputs

Rules enforced by the worker: max depth 4, no `..`, no leading `/`.

## Supported formats

`format=` is an optional hint understood by the worker:

| `format`             | Use it for                                       |
| -------------------- | ------------------------------------------------ |
| `"json"`             | dicts/lists of JSON-serializable values          |
| `"numpy"`            | a single `np.ndarray` → `.npy`                   |
| `"numpy_compressed"` | a dict of arrays → `.npz`                        |
| `"pickle"`           | any other Python object (fallback)               |
| `"text"`             | plain text (also: `write_text(name, str)`)       |
| `"bytes"`            | raw bytes (also: `write_bytes(name, b)`)         |

If you omit `format`, the worker infers it from the file extension
(`.json`, `.npy`, `.npz`, `.pkl`, `.qasm`, `.txt`, ...).

## More examples

### Save during a calibration sweep

```python
from qe_task_artifacts import with_artifacts, save_artifact, write_text


@with_artifacts
def cz_pulse_calibrate(input_data, gate, *, gates_def=None, pulses_def=None, mode="auto"):
    sweep = run_sweep(...)
    save_artifact(
        "artifacts/sweep_raw.npz",
        {"x": sweep.x, "y": sweep.y},
        format="numpy_compressed",
    )

    fit = fit_curve(sweep)
    save_artifact("artifacts/fit.json", fit.to_dict(), format="json")

    result = build_result(fit)
    save_artifact("output/result.json", result, format="json")
    write_text("output/summary.txt", result["summary"])
    return result
```

### Skip expensive diagnostics when no writer is active

For data whose only purpose is being saved, gate the *computation* on the
active writer's `enabled()`:

```python
from qe_task_artifacts import with_artifacts, save_artifact, current_artifacts


@with_artifacts
def error_budget(input_data, gate, **_):
    report = compute_error_budget(input_data, gate)
    save_artifact("output/error_report.json", report, format="json")

    if current_artifacts().enabled():
        traces = compute_expensive_diagnostics(report)   # only on workers
        save_artifact("artifacts/diagnostics.npz", traces, format="numpy_compressed")

    return report
```

### Nested calls just work

`save_artifact` reads from the `ContextVar`, so any helper called from a
`@with_artifacts` function can save without taking the writer as a parameter:

```python
@with_artifacts
def calibrate_coupler_flux_bias(input_data, coupler_ids):
    for coupler_id in coupler_ids:
        _calibrate_one(input_data, coupler_id)


def _calibrate_one(input_data, coupler_id):
    fit = fit_one(input_data, coupler_id)
    save_artifact(f"artifacts/{coupler_id}/fit.json", fit, format="json")
```

## Testing

By default `save_artifact` no-ops, so most tests need to do nothing:

```python
def test_error_budget_runs():
    out = error_budget(input_data, "CZ_0_1")
    assert out["success"] is True
```

To assert that specific artifacts are written, pass a recording writer
explicitly via `artifacts=`:

```python
class RecordingArtifacts:
    def __init__(self):
        self.calls = []

    def save(self, name, obj, *, format=None):
        self.calls.append(("save", name, format))

    def write_text(self, name, text):
        self.calls.append(("text", name))

    def write_bytes(self, name, data):
        self.calls.append(("bytes", name))

    def enabled(self):
        return True


def test_error_budget_saves_ptm():
    rec = RecordingArtifacts()
    error_budget(input_data, "CZ_0_1", artifacts=rec)
    assert ("save", "output/ptm.npy", "numpy") in rec.calls
```

`ArtifactWriter` is a runtime-checkable `Protocol`, so any object with the
four required methods is accepted (no inheritance needed).

## Worker integration

The worker provides the concrete `ArtifactWriter` and is responsible for
publishing it via `set_current_artifacts(self)` inside its task-scoped
context manager. The reference implementation is `TaskFileContext` in
`julia-celery-worker/app/task_files.py`. Once that's in place, every
`@with_artifacts`-decorated QEAM function automatically targets the running
task -- no per-call wiring needed in `tasks.py`.

## FAQ

**Do I have to add `artifacts=None` to my function signature?**
No. `@with_artifacts` consumes the kwarg before your function sees it.

**Can I forget the decorator and still call `save_artifact`?**
Yes -- it'll no-op safely. Nothing will be saved, though. The decorator is
how `artifacts=` from a caller (and the worker's context) get attached.

**Where do the files actually go?**
The worker provides the concrete writer, which uploads to the task's S3
folder under the task ID. Your code doesn't see any of that.

**What about the old `@accepts_artifacts` / `artifacts=None` parameter style?**
Still supported for backwards compatibility (`accepts_artifacts`,
`call_with_optional_artifacts`, `supports_artifacts` remain exported). New
code should use `@with_artifacts` + `save_artifact()`.

## Public API

| Symbol | Purpose |
| --- | --- |
| `with_artifacts` | Decorator. Enables `save_artifact(...)` inside the function body. **Use this.** |
| `save_artifact(name, obj, format=...)` | Save via the active writer. No-ops when none. |
| `write_text(name, text)` / `write_bytes(name, data)` | Text/binary equivalents. |
| `current_artifacts()` | Return the active writer (for `enabled()` checks). |
| `ArtifactWriter` | The `Protocol` that concrete writers (worker side) implement. |
| `NoopArtifactWriter` | Writer that accepts calls and does nothing. Used as the default. |
| `set_current_artifacts(writer)` / `reset_current_artifacts(token)` | Worker hook: publish/unpublish the active writer in the `ContextVar`. |
| `accepts_artifacts` / `call_with_optional_artifacts` / `supports_artifacts` | Legacy parameter-style helpers. Kept for backwards compatibility. |
