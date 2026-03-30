import sys
import threading
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from gui_task_runner import RequestTracker
from preview_cache import BoundedCache


class RequestTrackerTests(unittest.TestCase):
    def test_generations_are_independent_per_family(self) -> None:
        tracker = RequestTracker()

        first_preview = tracker.next("preview")
        second_preview = tracker.next("preview")
        first_build = tracker.next("build")

        self.assertEqual(first_preview.generation, 1)
        self.assertEqual(second_preview.generation, 2)
        self.assertEqual(first_build.generation, 1)
        self.assertFalse(tracker.is_current(first_preview))
        self.assertTrue(tracker.is_current(second_preview))
        self.assertTrue(tracker.is_current(first_build))

    def test_invalidate_marks_older_token_stale(self) -> None:
        tracker = RequestTracker()

        token = tracker.next("candidate-preview")
        generation = tracker.invalidate("candidate-preview")

        self.assertEqual(generation, 2)
        self.assertFalse(tracker.is_current(token))
        self.assertEqual(tracker.current("candidate-preview"), 2)


class BoundedCacheThreadSafetyTests(unittest.TestCase):
    def test_bounded_cache_survives_basic_concurrent_access(self) -> None:
        cache = BoundedCache[str, int](max_entries=8)
        barrier = threading.Barrier(5)
        errors: list[BaseException] = []

        def worker(worker_id: int) -> None:
            try:
                barrier.wait()
                for step in range(200):
                    key = f"{worker_id}-{step % 12}"
                    cache.set(key, step)
                    _ = cache.get(key)
                    _ = key in cache
                    _ = len(cache)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(worker_id,)) for worker_id in range(4)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertLessEqual(len(cache), 8)


if __name__ == "__main__":
    unittest.main()
