import json
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


class BuildFromSlotMappingTests(unittest.TestCase):
    def test_build_theme_from_mapping_preserves_unrelated_output_root_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mapping_path = root / "mapping.json"
            source_path = root / "arrow.cur"
            output_root = root / "output"
            unrelated_file = output_root / "keep.txt"

            source_path.write_bytes(b"")
            output_root.mkdir()
            unrelated_file.write_text("keep me", encoding="utf-8")
            mapping_path.write_text(
                json.dumps(
                    {
                        "resolved_role_map": {
                            "left_ptr": str(source_path),
                        }
                    }
                ),
                encoding="utf-8",
            )

            def fake_localize_metadata_frames(_metadata: dict, localized_dir: Path) -> dict:
                localized_dir.mkdir(parents=True, exist_ok=True)
                png_path = localized_dir / "frame.png"
                png_path.write_bytes(b"png")
                return {
                    "source": str(source_path),
                    "asset_type": "cur",
                    "scale_filter": "point",
                    "frames": [
                        {
                            "png": str(png_path),
                            "delay_ms": 50,
                            "width": 32,
                            "height": 32,
                            "nominal_size": 32,
                            "hotspot_x": 0,
                            "hotspot_y": 0,
                        }
                    ],
                }

            def fake_build_cursor_file(_config_path: Path, _frames_dir: Path, output_path: Path) -> None:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b"cursor")

            def fake_write_theme_metadata(theme_dir: Path, theme_name: str, comment: str) -> None:
                theme_dir.mkdir(parents=True, exist_ok=True)
                (theme_dir / "index.theme").write_text(
                    f"[Icon Theme]\nName={theme_name}\nComment={comment}\n",
                    encoding="utf-8",
                )

            with mock.patch.object(build_from_slot_mapping_module, "load_source_metadata", return_value={"frames": []}):
                with mock.patch.object(build_from_slot_mapping_module, "prepare_scaled_frames", return_value={"frames": []}):
                    with mock.patch.object(
                        build_from_slot_mapping_module,
                        "localize_metadata_frames",
                        side_effect=fake_localize_metadata_frames,
                    ):
                        with mock.patch.object(
                            build_from_slot_mapping_module,
                            "build_cursor_file",
                            side_effect=fake_build_cursor_file,
                        ):
                            with mock.patch.object(
                                build_from_slot_mapping_module,
                                "write_theme_metadata",
                                side_effect=fake_write_theme_metadata,
                            ):
                                with mock.patch.object(build_from_slot_mapping_module, "HASH_ALIASES", {}):
                                    manifest = build_from_slot_mapping_module.build_theme_from_mapping(
                                        mapping_path,
                                        output_root,
                                        "CursorForgeTest",
                                    )

            theme_dir = output_root / "CursorForgeTest"
            build_root = output_root / "_cursorforge-build" / "CursorForgeTest"

            self.assertTrue(unrelated_file.exists())
            self.assertEqual(unrelated_file.read_text(encoding="utf-8"), "keep me")
            self.assertTrue(theme_dir.exists())
            self.assertTrue((theme_dir / "cursors" / "left_ptr").exists())
            self.assertTrue((build_root / "configs" / "left_ptr.conf").exists())
            self.assertTrue((build_root / "build-manifest.json").exists())
            self.assertEqual(manifest["theme_dir"], str(theme_dir))
            self.assertEqual(manifest["build_root"], str(build_root))
            self.assertEqual(manifest["manifest_path"], str(build_root / "build-manifest.json"))
            self.assertFalse((output_root / "_extracted").exists())
            self.assertFalse((output_root / "_configs").exists())


if __name__ == "__main__":
    unittest.main()
