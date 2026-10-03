import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import app
from backend.app.projects import ProjectStore
from backend.app.routers.projects import get_projects
from backend.app.routers.session_messages import get_session_messages
from backend.app.stores.session_messages import SessionMessageStore



# The application lifespan now resumes job runners. Tests must therefore never
# let the real app touch the repository data root, or they would relaunch real
# background jobs (and real LLM calls). Point the app at an empty temp root.
_APP_ROOT: tempfile.TemporaryDirectory | None = None


def setUpModule():
    global _APP_ROOT
    _APP_ROOT = tempfile.TemporaryDirectory()
    os.environ["PAPER_VALT_ROOT"] = _APP_ROOT.name
    get_settings.cache_clear()


def tearDownModule():
    os.environ.pop("PAPER_VALT_ROOT", None)
    get_settings.cache_clear()
    if _APP_ROOT is not None:
        _APP_ROOT.cleanup()

class ProjectRouterTests(unittest.TestCase):
    def test_project_and_session_routes_are_mounted_from_domain_routers(self):
        routes = {
            (path, method.upper()) for path, operations in app.openapi()["paths"].items() for method in operations
        }
        self.assertIn(("/api/projects", "GET"), routes)
        self.assertIn(("/api/projects/{project_id}/workspace/file", "PUT"), routes)
        self.assertIn(("/api/projects/{project_id}/sessions", "POST"), routes)
        self.assertIn(("/api/sessions/{session_id}/governance", "GET"), routes)
        self.assertIn(("/api/sessions/{session_id}/messages", "GET"), routes)
        self.assertIn(("/api/sessions/{session_id}/messages", "POST"), routes)

    def test_project_router_preserves_workspace_path_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            references = root / "references"
            references.mkdir()
            (references / "paper_index.jsonl").write_text('{"id":"paper"}\n', encoding="utf-8")
            store = ProjectStore(references / "projects_sessions.json")
            app.dependency_overrides[get_projects] = lambda: store
            try:
                with TestClient(app) as client:
                    response = client.post("/api/projects", json={"name": "Review", "description": "", "goal": "Read"})
                    self.assertEqual(response.status_code, 200)
                    project_id = response.json()["id"]
                    self.assertEqual(client.get("/api/projects").json()[0]["id"], project_id)
                    escaped = client.put(
                        f"/api/projects/{project_id}/workspace/file",
                        json={"path": "../outside.md", "content": "blocked"},
                    )
                    self.assertEqual(escaped.status_code, 400)
            finally:
                app.dependency_overrides.clear()

    def test_session_message_history_is_legacy_safe_idempotent_and_isolated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            references = root / "references"
            references.mkdir()
            (references / "paper_index.jsonl").write_text('{"id":"paper"}\n', encoding="utf-8")
            store = ProjectStore(references / "projects_sessions.json")
            project = store.create_project("Review", "", "Read")
            old_session = store.create_session(project["id"], "Old", "Existing events only")
            other_session = store.create_session(project["id"], "Other", "Isolation")
            message_store = SessionMessageStore(root)
            app.dependency_overrides[get_projects] = lambda: store
            app.dependency_overrides[get_session_messages] = lambda: message_store
            try:
                with TestClient(app) as client:
                    empty = client.get(f"/api/sessions/{old_session['id']}/messages")
                    self.assertEqual(empty.status_code, 200)
                    self.assertEqual(empty.json(), {"session_id": old_session["id"], "messages": []})

                    payload = {"id": "client-message-1", "role": "user", "content": "先读摘要"}
                    first = client.post(f"/api/sessions/{old_session['id']}/messages", json=payload)
                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(len(first.json()["messages"]), 1)
                    self.assertEqual(first.json()["messages"][0]["content"], "先读摘要")

                    retry = client.post(f"/api/sessions/{old_session['id']}/messages", json=payload)
                    self.assertEqual(retry.status_code, 200)
                    self.assertEqual(retry.json(), first.json())

                    other = client.post(
                        f"/api/sessions/{other_session['id']}/messages",
                        json={"role": "user", "content": "另一条消息"},
                    )
                    self.assertEqual(other.status_code, 200)
                    self.assertEqual(
                        client.get(f"/api/sessions/{old_session['id']}/messages").json()["messages"][0]["id"],
                        "client-message-1",
                    )
                    self.assertEqual(len(client.get(f"/api/sessions/{other_session['id']}/messages").json()["messages"]), 1)
                    self.assertTrue(
                        (root / "projects" / project["id"] / "sessions" / old_session["id"] / "messages.json").is_file()
                    )
            finally:
                app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main(verbosity=2)
