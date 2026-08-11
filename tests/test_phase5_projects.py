from pathlib import Path

from backend.app.projects import ProjectStore


def test_governance_closeout_and_terminal_lifecycle(tmp_path: Path):
    store = ProjectStore(tmp_path / "references" / "projects.json")
    project = store.create_project("p", "", "goal")
    session = store.create_session(project["id"], "s", "goal")
    session = store.update_session(session["id"], {"status": "paused"})
    candidate = store.governance(session["id"])["candidates"][0]
    store.governance_action(session["id"], "ignore", candidate["id"])
    store.save_closeout(session["id"], {"summary": "s", "handoff": "h", "next_steps": ["n"]})
    assert store.governance_action(session["id"], "confirm_close")["closeout"]["confirmed"] is True


def test_typed_artifact_paths_and_relation_decision(tmp_path: Path):
    refs = tmp_path / "references"; refs.mkdir(); (refs / "paper_index.jsonl").write_text('{"id":"paper"}\n')
    store = ProjectStore(refs / "projects.json"); project = store.create_project("p", "", "")
    assert store.link_project(project["id"], {"kind": "paper", "ref": "paper"})["links"][-1]["orphaned"] is False
    assert store.link_project(project["id"], {"kind": "artifact", "ref": "/etc/passwd"})["links"][-1]["orphaned"] is True
