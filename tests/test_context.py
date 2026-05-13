import unittest

from qe_task_artifacts import (
    current_artifacts,
    reset_current_artifacts,
    save_artifact,
    set_current_artifacts,
    supports_artifacts,
    with_artifacts,
    write_bytes,
    write_text,
)


class RecordingWriter:
    """Minimal ArtifactWriter for assertions."""

    def __init__(self, *, enabled: bool = True):
        self._enabled = enabled
        self.calls = []

    def save(self, name, obj, *, format=None):
        self.calls.append(("save", name, format))
        return {"name": name}

    def write_text(self, name, text):
        self.calls.append(("text", name, text))
        return {"name": name}

    def write_bytes(self, name, data):
        self.calls.append(("bytes", name, len(data)))
        return {"name": name}

    def enabled(self):
        return self._enabled


class WithArtifactsTests(unittest.TestCase):
    def test_save_artifact_noops_without_writer(self):
        @with_artifacts
        def fn():
            return save_artifact("output/result.json", {"ok": True})

        self.assertIsNone(fn())

    def test_save_artifact_uses_explicit_writer(self):
        @with_artifacts
        def fn():
            save_artifact("output/result.json", {"ok": True}, format="json")
            write_text("output/summary.txt", "hello")
            write_bytes("output/blob.bin", b"\x00\x01")
            return "done"

        writer = RecordingWriter()
        result = fn(artifacts=writer)
        self.assertEqual(result, "done")
        self.assertEqual(
            writer.calls,
            [
                ("save", "output/result.json", "json"),
                ("text", "output/summary.txt", "hello"),
                ("bytes", "output/blob.bin", 2),
            ],
        )

    def test_save_artifact_skips_when_writer_disabled(self):
        @with_artifacts
        def fn():
            return save_artifact("output/result.json", {"ok": True})

        writer = RecordingWriter(enabled=False)
        self.assertIsNone(fn(artifacts=writer))
        self.assertEqual(writer.calls, [])

    def test_decorator_is_detected_by_supports_artifacts(self):
        @with_artifacts
        def fn():
            return None

        self.assertTrue(supports_artifacts(fn))

    def test_nested_helpers_inherit_writer(self):
        def helper():
            save_artifact("artifacts/inner.json", {"x": 1}, format="json")

        @with_artifacts
        def fn():
            helper()
            save_artifact("output/result.json", {"ok": True}, format="json")
            return "ok"

        writer = RecordingWriter()
        fn(artifacts=writer)
        self.assertEqual(
            writer.calls,
            [
                ("save", "artifacts/inner.json", "json"),
                ("save", "output/result.json", "json"),
            ],
        )

    def test_decorator_restores_previous_writer(self):
        outer = RecordingWriter()
        token = set_current_artifacts(outer)
        try:

            @with_artifacts
            def fn(inner_writer):
                save_artifact("output/inner.json", {}, format="json")
                self.assertIs(current_artifacts(), inner_writer)

            inner = RecordingWriter()
            fn(inner, artifacts=inner)
            self.assertIs(current_artifacts(), outer)
        finally:
            reset_current_artifacts(token)

    def test_picks_up_ambient_writer_when_no_kwarg(self):
        writer = RecordingWriter()

        @with_artifacts
        def fn():
            save_artifact("output/ambient.json", {}, format="json")
            return "ok"

        token = set_current_artifacts(writer)
        try:
            result = fn()
        finally:
            reset_current_artifacts(token)

        self.assertEqual(result, "ok")
        self.assertEqual(writer.calls, [("save", "output/ambient.json", "json")])

    def test_current_artifacts_default_is_disabled(self):
        self.assertFalse(current_artifacts().enabled())


if __name__ == "__main__":
    unittest.main()
