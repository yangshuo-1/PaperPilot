"""Data-root resolution contract (M0): outside the repository, XDG by default."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from paperpilot.datadir import (
    DATA_DIR_ENV,
    LEGACY_DATA_ROOT_ENV,
    checkout_root,
    default_data_dir,
)
from paperpilot.storage.paths import resolve_data_root


class DefaultDataDirTests(unittest.TestCase):
    def test_explicit_env_wins(self) -> None:
        with mock.patch.dict(os.environ, {DATA_DIR_ENV: "/tmp/pp-explicit", LEGACY_DATA_ROOT_ENV: "/tmp/legacy"}):
            self.assertEqual(default_data_dir(), Path("/tmp/pp-explicit"))

    def test_legacy_env_is_honoured_with_a_warning(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != DATA_DIR_ENV}
        env[LEGACY_DATA_ROOT_ENV] = "/tmp/pp-legacy"
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), redirect_stderr(stderr):
            self.assertEqual(default_data_dir(), Path("/tmp/pp-legacy"))
        self.assertIn(LEGACY_DATA_ROOT_ENV, stderr.getvalue())
        # The warning is printed once per process, not on every resolution.
        with mock.patch.dict(os.environ, env, clear=True), redirect_stderr(io.StringIO()):
            default_data_dir()

    def test_default_is_xdg_and_never_the_checkout(self) -> None:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {DATA_DIR_ENV, LEGACY_DATA_ROOT_ENV}
        }
        env["XDG_DATA_HOME"] = "/tmp/pp-xdg-home"
        with mock.patch.dict(os.environ, env, clear=True):
            resolved = default_data_dir()
        self.assertEqual(resolved, Path("/tmp/pp-xdg-home/paperpilot"))
        self.assertNotEqual(resolved, checkout_root())

    def test_storage_resolve_data_root_uses_the_same_default(self) -> None:
        with mock.patch.dict(os.environ, {DATA_DIR_ENV: "/tmp/pp-storage"}, clear=False):
            self.assertEqual(resolve_data_root(), Path("/tmp/pp-storage"))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(resolve_data_root(tmp), Path(tmp).resolve())


if __name__ == "__main__":
    unittest.main()
