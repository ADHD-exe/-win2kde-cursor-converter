import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import source_slot_mapper_gui as source_slot_mapper_gui_module


class DummyVar:
    def __init__(self, value: str):
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class SourceSlotMapperGuiHelperTests(unittest.TestCase):
    def test_load_cached_output_preview_reuses_cached_preview_without_regenerating(self) -> None:
        # Protects preview refreshes from rebuilding the same output preview when the cache key is unchanged.
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "arrow.cur"
            source_path.write_bytes(b"cursor")
            preview_root = root / "preview-cache"
            metadata_cache = source_slot_mapper_gui_module.BoundedCache[tuple, dict](max_entries=4)
            output_cache = source_slot_mapper_gui_module.BoundedCache[tuple, dict](max_entries=4)
            cached_preview = {
                "preview_nominal_size": 32,
                "scale_filter": "point",
                "frames": [{"png": str(root / "frame.png"), "delay_ms": 50, "width": 32, "height": 32}],
            }
            cache_key = source_slot_mapper_gui_module.output_preview_cache_key_for(
                source_path,
                preview_root,
                [24, 32],
                "point",
                32,
            )
            output_cache.set(cache_key, cached_preview)

            with mock.patch.object(source_slot_mapper_gui_module, "touch_output_preview_artifacts") as touch_artifacts:
                with mock.patch.object(
                    source_slot_mapper_gui_module,
                    "prepare_output_preview_metadata",
                ) as prepare_output_preview_metadata:
                    preview = source_slot_mapper_gui_module.load_cached_output_preview(
                        source_path,
                        preview_root,
                        [24, 32],
                        "point",
                        32,
                        metadata_cache,
                        output_cache,
                    )

            self.assertIs(preview, cached_preview)
            touch_artifacts.assert_called_once_with(preview_root, cached_preview)
            prepare_output_preview_metadata.assert_not_called()

    def test_prepare_source_preview_payload_returns_no_preview_when_frames_are_missing(self) -> None:
        # Protects the source-preview panel from crashing on metadata that resolves to no extracted frames.
        metadata_cache = source_slot_mapper_gui_module.BoundedCache[tuple, dict](max_entries=4)
        with mock.patch.object(source_slot_mapper_gui_module, "load_cached_source_metadata", return_value={"frames": []}):
            with mock.patch.object(source_slot_mapper_gui_module, "frames_from_source_metadata", return_value=[]):
                payload = source_slot_mapper_gui_module.prepare_source_preview_payload(
                    Path("/tmp/source.cur"),
                    Path("/tmp/preview-cache"),
                    32,
                    metadata_cache,
                )

        self.assertEqual(payload, {"reason": "No extracted frames available", "preview": None})

    def test_prepare_output_preview_payload_formats_animation_summary_and_warnings(self) -> None:
        # Protects the output-preview helper from dropping timing and filter details needed for review.
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            frame_one = root / "frame-1.png"
            frame_two = root / "frame-2.png"
            preview_root = root / "preview-cache"
            metadata_cache = source_slot_mapper_gui_module.BoundedCache[tuple, dict](max_entries=4)
            output_cache = source_slot_mapper_gui_module.BoundedCache[tuple, dict](max_entries=4)
            preview = {
                "preview_nominal_size": 32,
                "scale_filter": "point",
                "frames": [
                    {
                        "png": str(frame_one),
                        "delay_ms": 20,
                        "width": 32,
                        "height": 32,
                        "hotspot_x": 1,
                        "hotspot_y": 1,
                    },
                    {
                        "png": str(frame_two),
                        "delay_ms": 200,
                        "width": 32,
                        "height": 32,
                        "hotspot_x": 1,
                        "hotspot_y": 1,
                    },
                ],
            }

            with mock.patch.object(source_slot_mapper_gui_module, "load_cached_output_preview", return_value=preview):
                with mock.patch.object(
                    source_slot_mapper_gui_module,
                    "render_preview_thumbnail",
                    side_effect=[root / "thumb-1.png", root / "thumb-2.png"],
                ):
                    payload = source_slot_mapper_gui_module.prepare_output_preview_payload(
                        Path("/tmp/source.cur"),
                        preview_root,
                        32,
                        [24, 32],
                        "point",
                        metadata_cache,
                        output_cache,
                    )

        self.assertIsNone(payload["reason"])
        self.assertEqual(payload["preview"]["summary"], "2 frame(s) | 0.22s total | built path preview")
        self.assertIn("Nominal size 32px | emitted PNG 32x32 | filter point", payload["preview"]["frame_info"])
        self.assertIn("contains very fast frames", payload["preview"]["warning_text"])
        self.assertIn("animation loop is very short", payload["preview"]["warning_text"])
        self.assertEqual(len(payload["preview"]["thumbnail_paths"]), 2)

    def test_apply_prepare_selection_context_records_diagnostics_and_infers_remaining_paths(self) -> None:
        # Protects auto-fill diagnostics from losing fallback, override, and loaded-path provenance.
        app = type("DummyApp", (), {})()
        app.slot_paths = {slot["key"]: "" for slot in source_slot_mapper_gui_module.SLOT_DEFS}
        app.slot_paths.update(
            {
                "help": "/pack/help.cur",
                "progress": "/pack/appstart.ani",
                "hand": "/pack/link.cur",
                "default_pointer": "/pack/default.ani",
                "text": "/pack/text.cur",
            }
        )
        app.slot_selection_context = {}

        def infer_selection_context(slot_key: str, path: str) -> dict:
            return {
                "origin": "loaded",
                "path": path,
                "reason": f"loaded {slot_key}",
            }

        app._infer_selection_context = infer_selection_context

        source_slot_mapper_gui_module.MappingApp._apply_prepare_selection_context(
            app,
            {
                "diagnostics": {
                    "chosen_by_inf": {
                        "help": "/pack/help.cur",
                    },
                    "chosen_by_heuristic": {
                        "progress": {
                            "path": "/pack/appstart.ani",
                            "reason": "ranked first",
                            "score": 8,
                        }
                    },
                    "fallbacks": [
                        {
                            "target": "hand",
                            "source": "link_alias",
                            "path": "/pack/link.cur",
                        }
                    ],
                    "overrides": [
                        {
                            "target": "default_pointer",
                            "from": "/pack/arrow.cur",
                            "to": "/pack/default.ani",
                            "reason": "prefer animated progress/start cursor as the Linux default pointer",
                        }
                    ],
                }
            },
        )

        self.assertEqual(app.slot_selection_context["help"]["origin"], "inf")
        self.assertEqual(app.slot_selection_context["progress"]["origin"], "heuristic")
        self.assertEqual(app.slot_selection_context["progress"]["rank"], 1)
        self.assertEqual(app.slot_selection_context["hand"]["origin"], "fallback")
        self.assertEqual(app.slot_selection_context["hand"]["source_slot"], "link_alias")
        self.assertEqual(app.slot_selection_context["default_pointer"]["origin"], "override")
        self.assertEqual(app.slot_selection_context["default_pointer"]["from_path"], "/pack/arrow.cur")
        self.assertEqual(app.slot_selection_context["text"]["origin"], "loaded")

    def test_apply_selected_preset_updates_build_state_from_preset_definition(self) -> None:
        # Protects preset application from drifting away from the shared preset definitions.
        app = type("DummyApp", (), {})()
        app.build_preset_var = DummyVar("maximum-detail")
        app.target_sizes_var = DummyVar("")
        app.scale_filter_var = DummyVar("")
        app.preset_description_var = DummyVar("")
        app.preview_nominal_size_var = DummyVar("")
        app._suspend_refresh_traces = False
        app.profile_base_preset_label = None
        app.status_messages = []
        app.refresh_build_profile_state_calls = 0
        app.refresh_all_views_calls = 0

        def default_preview_size(target_sizes: list[int]) -> int:
            return 64

        def refresh_build_profile_state() -> None:
            app.refresh_build_profile_state_calls += 1

        def set_status(message: str) -> None:
            app.status_messages.append(message)

        def refresh_all_views() -> None:
            app.refresh_all_views_calls += 1

        app._default_preview_size = default_preview_size
        app._refresh_build_profile_state = refresh_build_profile_state
        app.set_status = set_status
        app._refresh_all_views = refresh_all_views

        source_slot_mapper_gui_module.MappingApp.apply_selected_preset(app)

        self.assertEqual(app.target_sizes_var.get(), "24, 32, 36, 48, 64, 96, 128, 192, 256")
        self.assertEqual(app.scale_filter_var.get(), "lanczos")
        self.assertEqual(app.build_preset_var.get(), "Maximum Detail")
        self.assertIn("Maximum Detail:", app.preset_description_var.get())
        self.assertEqual(app.preview_nominal_size_var.get(), "64")
        self.assertEqual(app.profile_base_preset_label, "Maximum Detail")
        self.assertEqual(app.refresh_build_profile_state_calls, 1)
        self.assertEqual(app.refresh_all_views_calls, 1)
        self.assertEqual(app.status_messages, ["Applied preset: Maximum Detail"])


if __name__ == "__main__":
    unittest.main()
