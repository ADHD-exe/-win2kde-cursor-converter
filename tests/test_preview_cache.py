import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from preview_cache import BoundedCache, cache_artifact_dir, source_dependency_token


class PreviewCacheTests(unittest.TestCase):
    def test_json_dependency_token_changes_when_referenced_png_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            png_path = root / "frame.png"
            json_path = root / "cursor.json"
            cache_root = root / "_preview-cache"

            png_path.write_bytes(b"first-version")
            json_path.write_text(
                json.dumps(
                    {
                        "frames": [
                            {
                                "delay_ms": 50,
                                "entries": [
                                    {
                                        "png": "frame.png",
                                        "width": 32,
                                        "height": 32,
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            first_token = source_dependency_token(json_path)
            first_dir = cache_artifact_dir(cache_root, json_path)

            png_path.write_bytes(b"second-version")

            second_token = source_dependency_token(json_path)
            second_dir = cache_artifact_dir(cache_root, json_path)

            self.assertNotEqual(first_token, second_token)
            self.assertNotEqual(first_dir, second_dir)

    def test_bounded_cache_evicts_least_recently_used_entry(self) -> None:
        cache = BoundedCache[str, int](max_entries=2)

        cache.set("one", 1)
        cache.set("two", 2)
        self.assertEqual(cache.get("one"), 1)

        cache.set("three", 3)

        self.assertIn("one", cache)
        self.assertIn("three", cache)
        self.assertNotIn("two", cache)


if __name__ == "__main__":
    unittest.main()
