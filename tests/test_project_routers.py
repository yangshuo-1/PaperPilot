import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.projects import ProjectStore
from backend.app.routers.projects import get_projects


class ProjectRouterTests(unittest.TestCase):
    def test_project_and_session_routes_are_mounted_from_domain_routers(self):
        routes = {
            (path, method.upper()) for path, operations in app.openapi()["paths"].items() for method in operations
        }
        self.assertIn(("/api/projects", "GET"), routes)
        self.assertIn(("/api/projects/{project_id}/workspace/file", "PUT"), routes)
        self.assertIn(("/api/projects/{project_id}/sessions", "POST"), routes)
        self.assertIn(("/api/sessions/{session_id}/governance", "GET"), routes)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
