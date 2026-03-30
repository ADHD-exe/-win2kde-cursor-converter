import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from gui_workflow_summary import (
    READINESS_COMPARE_BEFORE_EXPORT,
    build_compare_guidance,
    build_readiness_snapshot,
    decision_lane,
)


class WorkflowSummaryTests(unittest.TestCase):
    def test_decision_lane_maps_known_states(self) -> None:
        self.assertEqual(decision_lane("build-ready"), "build-ready")
        self.assertEqual(decision_lane("build-ready with review"), "build-ready with review")
        self.assertEqual(decision_lane("compare before export"), READINESS_COMPARE_BEFORE_EXPORT)
        self.assertEqual(decision_lane("reduce preset or replace art"), "redraw/manual replacement required")

    def test_readiness_snapshot_prioritizes_compare_and_redraw_queue(self) -> None:
        slot_default = {"key": "default_pointer", "label": "Default Pointer"}
        slot_wait = {"key": "wait", "label": "Wait"}
        quality_entries = [
            (
                slot_default,
                {
                    "label": "acceptable",
                    "confidence": "medium",
                    "decision": "compare before export",
                    "warnings": ["Top candidates are near-tied."],
                    "actions": ["Compare top candidates before export."],
                },
                {"origin": "fallback", "source_slot": "progress"},
            ),
            (
                slot_wait,
                {
                    "label": "redraw recommended",
                    "confidence": "low",
                    "decision": "reduce preset or replace art",
                    "warnings": ["Native detail is too small."],
                    "actions": ["Replace or redraw this slot."],
                },
                None,
            ),
        ]

        snapshot = build_readiness_snapshot(
            quality_entries=quality_entries,
            pending_slots=[],
            selected_slot_count=2,
            resolved_role_count=4,
            target_sizes=[24, 32, 36, 48, 64, 96, 128, 192],
            size_error=None,
            mapping_error=None,
            pack_analysis={
                "hidpi_potential": {"rating": "weak"},
                "ambiguous_candidates": {"default_pointer": [{}]},
                "warnings": ["Pack-level warning"],
            },
            safe_preset_label="Standard Linux",
        )

        self.assertEqual(snapshot.readiness_headline, "Pack readiness: redraw/manual replacement required")
        self.assertIn("fallback-reused", snapshot.review_queue_headline)
        self.assertIn("Compare before export", snapshot.guidance_text)
        self.assertEqual(snapshot.suggested_preset, "Standard Linux")

    def test_compare_guidance_surfaces_fallback_and_hidpi_risk(self) -> None:
        summary, hint = build_compare_guidance(
            "Source vs Linux Output",
            slot_label="Default Pointer",
            current_profile_label="Custom from HiDPI KDE",
            current_quality={"label": "acceptable", "confidence": "medium", "decision": "compare before export"},
            selection_context={"origin": "fallback", "source_slot": "progress"},
            weak_hidpi=True,
            is_ambiguous=True,
        )

        self.assertIn("predicted Linux output", summary)
        self.assertIn("Progress", hint)
        self.assertIn("ambiguous", hint)
        self.assertIn("HiDPI", hint)


if __name__ == "__main__":
    unittest.main()
