import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paperpilot.projects import ProjectStore


class Phase5ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        refs = self.root / "references"
        refs.mkdir()
        (refs / "paper_index.jsonl").write_text('{"id":"paper"}\n', encoding="utf-8")
        self.store = ProjectStore(refs / "projects.json")
        self.project = self.store.create_project("p", "", "goal")

    def tearDown(self):
        self.temp.cleanup()

    def session(self, title="s"):
        return self.store.create_session(self.project["id"], title, "goal")

    def test_stale_edit_then_confirm_and_ignore_persists(self):
        session = self.session()
        session = self.store.update_session(session["id"], {"status": "paused"})
        candidate = self.store.governance(session["id"])["candidates"][0]
        self.store.save_closeout(session["id"], {"summary": "s", "handoff": "h", "next_steps": ["n"]})
        self.store.governance_action(session["id"], "ignore", candidate["id"])
        with self.assertRaises(ValueError):
            self.store.governance_action(session["id"], "confirm_close")
        edited = self.store.save_closeout(session["id"], {"summary": "edited", "handoff": "h", "next_steps": ["n"]})
        self.assertEqual(edited["closeout"]["session_version"], edited["updated_at"])
        self.assertTrue(self.store.governance_action(session["id"], "confirm_close")["closeout"]["confirmed"])
        self.assertEqual(self.store.governance(session["id"])["candidates"], [])
        with self.assertRaises(ValueError):
            self.store.save_closeout(session["id"], {"summary": "again", "handoff": "h", "next_steps": ["n"]})
        with patch("paperpilot.projects.llm.chat_once"):
            with self.assertRaises(ValueError):
                self.store.generate_closeout(session["id"])

    def test_relation_decision_evidence_timeline_and_no_overwrite(self):
        left, right = self.session("left"), self.session("right")
        self.store.link_session(left["id"], {"kind": "paper", "ref": "paper"})
        self.store.link_session(right["id"], {"kind": "paper", "ref": "paper"})
        relation = self.store.relations(self.project["id"])[0]
        self.assertEqual(relation["evidence"], {"shared_papers": ["paper"]})
        self.store.decide_relation(self.project["id"], relation["id"], True)
        with self.assertRaises(ValueError):
            self.store.decide_relation(self.project["id"], relation["id"], False)
        project = self.store.project(self.project["id"])
        self.assertEqual(project.get("relation_decisions", {})[relation["id"]]["accepted"], True)

    def test_ai_schema_and_orphan_citations(self):
        session = self.session()
        self.store.link_session(session["id"], {"kind": "paper", "ref": "paper"})
        raw = '{"summary":"ok","handoff":"next","next_steps":["do"]}'
        with patch("paperpilot.projects.llm.chat_once", return_value=raw), patch("paperpilot.projects.llm.llm_status", return_value={"model": "test"}):
            result = self.store.generate_closeout(session["id"])
        self.assertEqual([x["ref"] for x in result["closeout"]["citations"]], ["paper"])
        with patch("paperpilot.projects.llm.chat_once", return_value='{"summary": 1,"handoff":"x","next_steps":[]}'):
            with self.assertRaises(ValueError):
                self.store.generate_closeout(session["id"])

    def test_typed_artifact_negative_paths(self):
        self.assertTrue(self.store.link_session(self.session()["id"], {"kind": "artifact", "ref": "/etc/passwd"})["links"][-1]["orphaned"])
        self.assertTrue(self.store.link_session(self.session()["id"], {"kind": "artifact", "ref": "takeaway:../item"})["links"][-1]["orphaned"])

    def test_archive_closes_candidate_view_without_deleting_sources(self):
        session = self.session()
        self.store.governance_action(session["id"], "archive")
        self.assertEqual(self.store.governance(session["id"])["candidates"], [])
        self.assertEqual(self.store.session(session["id"])["status"], "active")
        with self.assertRaises(ValueError):
            self.store.save_closeout(session["id"], {"summary": "x", "handoff": "h", "next_steps": ["n"]})
        with self.assertRaises(ValueError):
            self.store.governance_action(session["id"], "archive")

    def test_workspace_writes_reads_and_rejects_traversal(self):
        workspace = self.store.workspace(self.project["id"])
        self.assertEqual(workspace["root"], f"projects/{self.project['id']}")
        entry = self.store.write_workspace_file(self.project["id"], "notes/reading-log.md", "# Reading log\n")
        self.assertEqual(entry["path"], "notes/reading-log.md")
        self.assertEqual(self.store.read_workspace_file(self.project["id"], "notes/reading-log.md"), "# Reading log\n")
        self.assertIn("notes/reading-log.md", {item["path"] for item in self.store.workspace(self.project["id"])["entries"]})
        with self.assertRaises(ValueError):
            self.store.write_workspace_file(self.project["id"], "../outside.md", "nope")
        with self.assertRaises(ValueError):
            self.store.read_workspace_file(self.project["id"], "notes/../outside.md")

    def test_session_workspace_is_created_and_isolated(self):
        session = self.session()
        self.assertEqual(session["workspace_root"], f"projects/{self.project['id']}/sessions/{session['id']}")
        session_path = self.root / "projects" / self.project["id"] / "sessions" / session["id"]
        self.store.write_workspace_file(self.project["id"], f"sessions/{session['id']}/note.md", "session note")
        self.assertEqual(self.store.read_workspace_file(self.project["id"], f"sessions/{session['id']}/note.md"), "session note")
        self.store.delete_session(session["id"])
        self.assertFalse(session_path.exists())

    def test_project_deletion_removes_only_its_workspace(self):
        other = self.store.create_project("other", "", "goal")
        self.store.write_workspace_file(self.project["id"], "notes/project.md", "project")
        self.store.write_workspace_file(other["id"], "notes/other.md", "other")
        self.store.delete_project(self.project["id"])
        self.assertFalse((self.root / "projects" / self.project["id"]).exists())
        self.assertTrue((self.root / "projects" / other["id"] / "notes" / "other.md").is_file())

    def test_latest_job_requires_an_existing_paper(self):
        from paperpilot.takeaway_jobs import TakeawayJobRunner
        from paperpilot.translation_jobs import TranslationJobRunner
        from types import SimpleNamespace

        job_store = SimpleNamespace(
            settings=SimpleNamespace(references_dir=self.root / "references"),
            get_paper=lambda _paper_id: (_ for _ in ()).throw(KeyError("missing")),
        )

        with self.assertRaises(KeyError):
            TakeawayJobRunner(job_store).latest_for_paper("missing")
        with self.assertRaises(KeyError):
            TranslationJobRunner(job_store).latest_for_paper("missing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
