import unittest

from qe_task_artifacts import (
    NoopArtifactWriter,
    accepts_artifacts,
    call_with_optional_artifacts,
    supports_artifacts,
)


class CompatTests(unittest.TestCase):
    def test_supports_explicit_artifacts_parameter(self):
        def fn(payload, *, artifacts=None):
            return payload

        self.assertTrue(supports_artifacts(fn))

    def test_supports_kwargs(self):
        def fn(payload, **kwargs):
            return payload

        self.assertTrue(supports_artifacts(fn))

    def test_does_not_support_plain_function(self):
        def fn(payload):
            return payload

        self.assertFalse(supports_artifacts(fn))

    def test_call_with_optional_artifacts_passes_only_when_supported(self):
        artifacts = NoopArtifactWriter()

        def old_fn(payload):
            return {"payload": payload}

        def new_fn(payload, *, artifacts=None):
            return {"payload": payload, "enabled": artifacts.enabled()}

        self.assertEqual(
            call_with_optional_artifacts(old_fn, {"x": 1}, artifacts=artifacts),
            {"payload": {"x": 1}},
        )
        self.assertEqual(
            call_with_optional_artifacts(new_fn, {"x": 1}, artifacts=artifacts),
            {"payload": {"x": 1}, "enabled": False},
        )

    def test_accepts_artifacts_decorator_ignores_artifacts_for_old_functions(self):
        @accepts_artifacts
        def old_fn(payload):
            return payload

        self.assertTrue(supports_artifacts(old_fn))
        self.assertEqual(
            old_fn({"x": 1}, artifacts=NoopArtifactWriter()),
            {"x": 1},
        )


if __name__ == "__main__":
    unittest.main()
