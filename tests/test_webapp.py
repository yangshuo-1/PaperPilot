"""Tests for the prebuilt-SPA hosting path (M0 P0.2)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from paperpilot import webapp

INDEX_HTML = "<!doctype html><html><body><div id=\"root\"></div></body></html>"


class WebAppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "index.html").write_text(INDEX_HTML, encoding="utf-8")
        assets = self.root / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log('boot');", encoding="utf-8")

    def _client(self) -> TestClient:
        app = FastAPI()

        @app.get("/api/health")
        async def health() -> dict[str, bool]:
            return {"ok": True}

        with mock.patch.object(webapp, "web_dir", return_value=self.root):
            served = webapp.mount_web(app)
        self.assertEqual(served, self.root)
        return TestClient(app)

    def test_root_serves_index(self) -> None:
        response = self._client().get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="root"', response.text)

    def test_client_route_falls_back_to_index(self) -> None:
        # BrowserRouter deep links must render the shell instead of 404ing.
        response = self._client().get("/papers/2401.12345")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="root"', response.text)

    def test_bundle_asset_is_served(self) -> None:
        response = self._client().get("/assets/app.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("boot", response.text)

    def test_api_routes_win_and_unknown_api_path_is_404(self) -> None:
        client = self._client()
        self.assertEqual(client.get("/api/health").json(), {"ok": True})
        self.assertEqual(client.get("/api/definitely-missing").status_code, 404)

    def test_no_bundle_returns_none(self) -> None:
        with mock.patch.object(webapp, "web_dir", return_value=self.root / "missing"):
            self.assertIsNone(webapp.mount_web(FastAPI()))

    def test_dev_mode_flag(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(webapp.DEV_MODE_ENV, None)
            self.assertFalse(webapp.is_dev_mode())
            for value in ("1", "true", "YES", "on"):
                os.environ[webapp.DEV_MODE_ENV] = value
                self.assertTrue(webapp.is_dev_mode(), value)
            for value in ("0", "false", "no", "off", ""):
                os.environ[webapp.DEV_MODE_ENV] = value
                self.assertFalse(webapp.is_dev_mode(), value)


if __name__ == "__main__":
    unittest.main()
