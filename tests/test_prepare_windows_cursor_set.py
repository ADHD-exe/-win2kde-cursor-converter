import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import prepare_windows_cursor_set as prepare_windows_cursor_set_module


class PrepareWindowsCursorSetTests(unittest.TestCase):
    def test_appstart_is_not_a_generic_default_pointer_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir)
            appstart = source_dir / "appstart.ani"
            appstart.write_bytes(b"")

            candidates = prepare_windows_cursor_set_module.heuristic_slot_candidates(source_dir, [appstart])

            self.assertEqual(candidates["default_pointer"], [])
            self.assertEqual(len(candidates["progress"]), 1)
            self.assertEqual(candidates["progress"][0]["path"], appstart.resolve())

    def test_animated_progress_only_overrides_default_pointer_when_opted_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir)
            arrow = source_dir / "arrow.cur"
            appstart = source_dir / "appstart.ani"
            arrow.write_bytes(b"")
            appstart.write_bytes(b"")

            analysis = {
                "install_inf": None,
                "warnings": [],
                "slot_candidates": {
                    "default_pointer": [
                        {
                            "path": str(arrow.resolve()),
                            "score": 5,
                            "reason": "filename heuristic matched Default Pointer",
                            "low_priority_hits": 0,
                            "depth": 0,
                        }
                    ],
                    "progress": [
                        {
                            "path": str(appstart.resolve()),
                            "score": 8,
                            "reason": "filename heuristic matched Progress",
                            "low_priority_hits": 0,
                            "depth": 0,
                        }
                    ],
                },
            }

            with mock.patch.object(prepare_windows_cursor_set_module, "parse_install_inf", return_value=(None, {})):
                with mock.patch.object(
                    prepare_windows_cursor_set_module,
                    "analyze_cursor_pack",
                    return_value=analysis,
                ):
                    chosen_default, diagnostics_default = prepare_windows_cursor_set_module.choose_slot_assignments(
                        source_dir,
                        [arrow, appstart],
                    )
                    self.assertEqual(chosen_default["default_pointer"], arrow.resolve())
                    self.assertEqual(chosen_default["progress"], appstart.resolve())
                    self.assertEqual(diagnostics_default["overrides"], [])

                    chosen_opt_in, diagnostics_opt_in = prepare_windows_cursor_set_module.choose_slot_assignments(
                        source_dir,
                        [arrow, appstart],
                        prefer_animated_default_pointer=True,
                    )
                    self.assertEqual(chosen_opt_in["default_pointer"], appstart.resolve())
                    self.assertEqual(chosen_opt_in["progress"], appstart.resolve())
                    self.assertEqual(len(diagnostics_opt_in["overrides"]), 1)
                    self.assertEqual(diagnostics_opt_in["overrides"][0]["target"], "default_pointer")


if __name__ == "__main__":
    unittest.main()
