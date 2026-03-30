import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from gui_build_profile import (
    PROFILE_KIND_CUSTOM_DERIVED,
    PROFILE_KIND_CUSTOM_UNMATCHED,
    PROFILE_KIND_EXACT,
    build_profile_payload,
    resolve_build_profile_state,
    restore_profile_base_preset,
)


class BuildProfileStateTests(unittest.TestCase):
    def test_exact_profile_keeps_named_preset_even_with_alias_match(self) -> None:
        state = resolve_build_profile_state(
            [24, 32, 36, 48, 64, 96, 128, 192],
            "point",
            base_preset_label="HiDPI KDE",
        )

        self.assertEqual(state.kind, PROFILE_KIND_EXACT)
        self.assertEqual(state.label, "HiDPI KDE")
        self.assertIn("Pixel / Glitch", state.detail)

    def test_manual_edits_preserve_custom_from_base_preset(self) -> None:
        state = resolve_build_profile_state(
            [24, 32, 36, 48, 64, 96, 128, 192],
            "lanczos",
            base_preset_label="HiDPI KDE",
        )

        self.assertEqual(state.kind, PROFILE_KIND_CUSTOM_DERIVED)
        self.assertEqual(state.label, "Custom from HiDPI KDE")
        self.assertIn("Smooth / Anti-aliased", state.detail)

    def test_unmatched_manual_settings_are_custom(self) -> None:
        state = resolve_build_profile_state(
            [24, 40, 80],
            "mitchell",
            base_preset_label=None,
        )

        self.assertEqual(state.kind, PROFILE_KIND_CUSTOM_UNMATCHED)
        self.assertEqual(state.label, "Custom")
        self.assertIn("do not currently match", state.detail)

    def test_restore_profile_base_preset_prefers_saved_payload(self) -> None:
        state = resolve_build_profile_state(
            [24, 32, 36, 48, 64],
            "point",
            base_preset_label="Standard Linux",
        )
        payload = build_profile_payload(state)

        restored = restore_profile_base_preset(payload, state.target_sizes, state.scale_filter)

        self.assertEqual(restored, "Standard Linux")


if __name__ == "__main__":
    unittest.main()
