# QE Task Artifacts

Tiny interface package for task-scoped artifact saving.

This package intentionally does not know about Celery, Django, S3, task IDs,
tokens, or the Quantum Elements SDK. It defines the narrow interface that
physics/QEAM code can accept when it wants to save files for the currently
running task.

```python
def run_experiment(payload, *, artifacts=None):
    result = compute(payload)
    if artifacts and artifacts.enabled():
        artifacts.save("artifacts/state.npy", result.state)
        artifacts.save("output/debug.json", result.debug)
    return result.summary
```

The worker provides the concrete implementation.
