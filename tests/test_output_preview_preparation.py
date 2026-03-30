import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_from_slot_mapping as build_from_slot_mapping_module
import xcursor_builder as xcursor_builder_module


class OutputPreviewPreparationTests(unittest.TestCase):
    def test_prepare_scaled_frames_for_size_matches_full_path_for_selected_nominal_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            generated_dir = root / "generated"

            small_png = root / "small.png"
            wide_png = root / "wide.png"
            exact_png = root / "exact48.png"
            large_png = root / "large96.png"
            for png_path in (small_png, wide_png, exact_png, large_png):
                png_path.write_bytes(b"png")

            image_sizes = {
                str(small_png.resolve()): (24, 24),
                str(wide_png.resolve()): (64, 32),
                str(exact_png.resolve()): (48, 48),
                str(large_png.resolve()): (96, 96),
            }

            def fake_identify_png_size(source_png: Path) -> tuple[int, int]:
                return image_sizes[str(Path(source_png).resolve())]

            def fake_ensure_scaled_png(
                source_png: Path,
                scaled_dir: Path,
                target_size: int,
                scale_filter: str,
            ) -> Path:
                scaled_dir.mkdir(parents=True, exist_ok=True)
                output_path = scaled_dir / f"{Path(source_png).stem}_{scale_filter}_{target_size}.png"
                if not output_path.exists():
                    output_path.write_bytes(b"scaled")
                    source_width, source_height = image_sizes[str(Path(source_png).resolve())]
                    output_width = target_size
                    output_height = max(1, int(round(source_height * target_size / source_width)))
                    image_sizes[str(output_path.resolve())] = (output_width, output_height)
                return output_path

            metadata = {
                "source": "demo.cur",
                "asset_type": "cur",
                "frames": [
                    {
                        "frame_index": 0,
                        "delay_ms": 50,
                        "entries": [
                            {
                                "png": str(small_png),
                                "width": 24,
                                "height": 24,
                                "hotspot_x": 6,
                                "hotspot_y": 7,
                                "entry_index": 1,
                                "image_size": 24,
                            },
                            {
                                "png": str(wide_png),
                                "width": 64,
                                "height": 32,
                                "hotspot_x": 32,
                                "hotspot_y": 16,
                                "entry_index": 2,
                                "image_size": 64,
                            },
                        ],
                    },
                    {
                        "frame_index": 1,
                        "delay_ms": 80,
                        "entries": [
                            {
                                "png": str(exact_png),
                                "width": 48,
                                "height": 48,
                                "hotspot_x": 10,
                                "hotspot_y": 11,
                                "entry_index": 1,
                                "image_size": 48,
                            },
                            {
                                "png": str(large_png),
                                "width": 96,
                                "height": 96,
                                "hotspot_x": 20,
                                "hotspot_y": 22,
                                "entry_index": 2,
                                "image_size": 96,
                            },
                        ],
                    },
                ],
            }

            with (
                mock.patch.object(
                    xcursor_builder_module,
                    "identify_png_size",
                    side_effect=fake_identify_png_size,
                ),
                mock.patch.object(
                    xcursor_builder_module,
                    "ensure_scaled_png",
                    side_effect=fake_ensure_scaled_png,
                ),
            ):
                full_prepared = xcursor_builder_module.prepare_scaled_frames(
                    metadata,
                    [24, 48, 96],
                    scale_filter="point",
                    generated_dir=generated_dir,
                )
                preview_prepared = xcursor_builder_module.prepare_scaled_frames_for_size(
                    metadata,
                    48,
                    scale_filter="point",
                    generated_dir=generated_dir,
                )

            full_frames_for_selected_size = [
                frame
                for frame in full_prepared["frames"]
                if int(frame.get("nominal_size", frame["width"])) == 48
            ]

            self.assertEqual(preview_prepared["source"], full_prepared["source"])
            self.assertEqual(preview_prepared["asset_type"], full_prepared["asset_type"])
            self.assertEqual(preview_prepared["scale_filter"], full_prepared["scale_filter"])
            self.assertEqual(preview_prepared["frames"], full_frames_for_selected_size)

            first_frame = preview_prepared["frames"][0]
            self.assertEqual(first_frame["entry_index"], 2)
            self.assertEqual(first_frame["native_width"], 64)
            self.assertEqual(first_frame["native_height"], 32)
            self.assertEqual(first_frame["width"], 48)
            self.assertEqual(first_frame["height"], 24)
            self.assertEqual(first_frame["hotspot_x"], 24)
            self.assertEqual(first_frame["hotspot_y"], 12)

            second_frame = preview_prepared["frames"][1]
            self.assertEqual(second_frame["entry_index"], 1)
            self.assertEqual(second_frame["width"], 48)
            self.assertEqual(second_frame["height"], 48)
            self.assertEqual(second_frame["hotspot_x"], 10)
            self.assertEqual(second_frame["hotspot_y"], 11)

    def test_prepare_output_preview_metadata_uses_preview_only_builder_for_selected_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "cursor.cur"
            source_path.write_bytes(b"cur")
            frame_png = root / "frame.png"
            frame_png.write_bytes(b"png")

            metadata = {
                "source": str(source_path),
                "asset_type": "cur",
                "frames": [
                    {
                        "frame_index": 0,
                        "delay_ms": 50,
                        "entries": [
                            {
                                "png": str(frame_png),
                                "width": 32,
                                "height": 32,
                                "hotspot_x": 4,
                                "hotspot_y": 5,
                                "entry_index": 1,
                            }
                        ],
                    }
                ],
            }
            prepared_preview = {
                "source": str(source_path),
                "asset_type": "cur",
                "scale_filter": "point",
                "frames": [
                    {
                        "png": str(frame_png),
                        "delay_ms": 50,
                        "width": 32,
                        "height": 32,
                        "nominal_size": 32,
                        "hotspot_x": 4,
                        "hotspot_y": 5,
                        "frame_index": 0,
                        "entry_index": 1,
                        "native_width": 32,
                        "native_height": 32,
                    }
                ],
            }
            preview_root = root / "preview"

            with (
                mock.patch.object(
                    build_from_slot_mapping_module,
                    "prepare_scaled_frames",
                    side_effect=AssertionError("full multi-size preparation should not be used for preview"),
                ),
                mock.patch.object(
                    build_from_slot_mapping_module,
                    "prepare_scaled_frames_for_size",
                    return_value=prepared_preview,
                ) as preview_prepare_mock,
                mock.patch.object(
                    build_from_slot_mapping_module,
                    "localize_metadata_frames",
                    side_effect=lambda localized_metadata, _localized_dir: localized_metadata,
                ),
            ):
                preview = build_from_slot_mapping_module.prepare_output_preview_metadata(
                    source_path,
                    preview_root,
                    [24, 32, 64],
                    scale_filter="point",
                    preview_nominal_size=48,
                    source_metadata=metadata,
                    source_cache_root=preview_root.parent / "_source",
                )

            self.assertEqual(preview_prepare_mock.call_count, 1)
            called_metadata, called_size = preview_prepare_mock.call_args.args
            self.assertEqual(called_metadata, metadata)
            self.assertEqual(called_size, 32)
            self.assertEqual(preview_prepare_mock.call_args.kwargs["scale_filter"], "point")
            self.assertEqual(
                preview_prepare_mock.call_args.kwargs["generated_dir"],
                build_from_slot_mapping_module.unique_extract_dir(preview_root, source_path),
            )

            self.assertEqual(preview["available_nominal_sizes"], [24, 32, 64])
            self.assertEqual(preview["preview_nominal_size"], 32)
            self.assertEqual(len(preview["frames"]), 1)
            self.assertEqual(preview["frames"][0]["nominal_size"], 32)


if __name__ == "__main__":
    unittest.main()
