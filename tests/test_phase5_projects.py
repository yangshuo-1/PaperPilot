import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from backend.app.projects import ProjectStore


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
        with patch("backend.app.projects.llm.chat_once", return_value=raw), patch("backend.app.projects.llm.llm_status", return_value={"model": "test"}):
            result = self.store.generate_closeout(session["id"])
        self.assertEqual([x["ref"] for x in result["closeout"]["citations"]], ["paper"])
        with patch("backend.app.projects.llm.chat_once", return_value='{"summary": 1,"handoff":"x","next_steps":[]}'):
            with self.assertRaises(ValueError):
                self.store.generate_closeout(session["id"])

    def test_typed_artifact_negative_paths(self):
        self.assertTrue(self.store.link_session(self.session()["id"], {"kind": "artifact", "ref": "/etc/passwd"})["links"][-1]["orphaned"])
        self.assertTrue(self.store.link_session(self.session()["id"], {"kind": "artifact", "ref": "takeaway:../item"})["links"][-1]["orphaned"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
