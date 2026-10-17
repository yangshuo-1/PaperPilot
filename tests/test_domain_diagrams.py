import unittest
from pathlib import Path

from paperpilot.domain.diagrams import validate_ir


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "design" / "ir-schema.v1.json"


def _evidence(quote: str, *, page: int = 1) -> dict[str, object]:
    return {"section": "3.2", "page": page, "quote": quote}


def _valid_ir(*, diagram_type: str = "workflow") -> dict[str, object]:
    return {
        "version": 1,
        "type": diagram_type,
        "title": "Method workflow",
        "nodes": [
            {
                "id": "input",
                "label": "Input",
                "role": "input",
                "evidence": _evidence("Input data is normalized."),
            },
            {
                "id": "model",
                "label": "Model",
                "role": "model",
                "evidence": _evidence("The model learns representations."),
            },
        ],
        "edges": [
            {
                "from": "input",
                "to": "model",
                "label": "representations",
                "evidence": _evidence("Input data is normalized."),
            }
        ],
    }


class DiagramValidationTests(unittest.TestCase):
    def test_valid_ir_passes(self):
        issues = validate_ir(
            _valid_ir(),
            source_text="Input data is normalized. The model learns representations.",
            schema_path=SCHEMA_PATH,
        )

        self.assertEqual(issues, [])

    def test_missing_evidence_is_rejected(self):
        ir = _valid_ir()
        del ir["nodes"][0]["evidence"]

        issues = validate_ir(
            ir,
            source_text="Input data is normalized.",
            schema_path=SCHEMA_PATH,
        )

        codes = {issue.code for issue in issues}
        self.assertIn("SCHEMA_VIOLATION", codes)
        self.assertIn("EVIDENCE_MISSING", codes)

    def test_fabricated_quote_is_rejected(self):
        ir = _valid_ir()
        ir["nodes"][0]["evidence"]["quote"] = "This sentence is fabricated."

        issues = validate_ir(
            ir,
            source_text="Input data is normalized.",
            schema_path=SCHEMA_PATH,
        )

        self.assertIn("QUOTE_NOT_FOUND", {issue.code for issue in issues})

    def test_dangling_edge_is_rejected(self):
        ir = _valid_ir()
        ir["edges"][0]["to"] = "missing"

        issues = validate_ir(
            ir,
            source_text="Input data is normalized. The model learns representations.",
            schema_path=SCHEMA_PATH,
        )

        self.assertIn("DANGLING_EDGE", {issue.code for issue in issues})

    def test_self_loop_is_rejected(self):
        ir = _valid_ir()
        ir["edges"][0]["from"] = "model"
        ir["edges"][0]["to"] = "model"

        issues = validate_ir(
            ir,
            source_text="Input data is normalized. The model learns representations.",
            schema_path=SCHEMA_PATH,
        )

        self.assertIn("SELF_LOOP", {issue.code for issue in issues})

    def test_workflow_cycle_is_rejected(self):
        ir = _valid_ir()
        ir["edges"].append(
            {
                "from": "model",
                "to": "input",
                "label": "feedback",
                "evidence": _evidence("The model learns representations."),
            }
        )

        issues = validate_ir(
            ir,
            source_text="Input data is normalized. The model learns representations.",
            schema_path=SCHEMA_PATH,
        )

        self.assertIn("CYCLE", {issue.code for issue in issues})

    def test_quote_whitespace_difference_passes(self):
        ir = _valid_ir()
        ir["nodes"][0]["evidence"]["quote"] = "Input data\nis normalized."
        ir["edges"][0]["evidence"]["quote"] = "Input data\nis normalized."

        issues = validate_ir(
            ir,
            source_text="Input data is normalized. The model learns representations.",
            schema_path=SCHEMA_PATH,
        )

        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
