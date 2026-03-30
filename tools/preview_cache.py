#!/usr/bin/env python3
"""Preview cache helpers for dependency tracking and bounded cache behavior."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Generic, TypeVar

from windows_cursor_tool import sanitize_path_component


MAX_PREVIEW_THUMB_FILES = 512
MAX_SOURCE_CACHE_DIRS = 48
MAX_OUTPUT_PREVIEW_DIRS = 48

K = TypeVar("K")
V = TypeVar("V")


def normalize_path(path: Path) -> Path:
    return path.expanduser().resolve()


def _file_cache_token(path: Path) -> str:
    from xcursor_builder import file_cache_token

    return file_cache_token(path)


def file_identity(path: Path) -> tuple[str, str]:
    resolved = normalize_path(path)
    return str(resolved), _file_cache_token(resolved)


def _json_dependency_paths(source_path: Path) -> tuple[Path, ...]:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"metadata JSON root must be an object: {source_path}")

    raw_frames = payload.get("frames", [])
    if not isinstance(raw_frames, list):
        raise ValueError(f"metadata JSON frames must be a list: {source_path}")

    dependencies = []
    seen = set()
    for frame_index, frame in enumerate(raw_frames):
        if not isinstance(frame, dict):
            raise ValueError(f"metadata frame {frame_index} must be an object: {source_path}")
        raw_entries = frame.get("entries", [frame])
        if not isinstance(raw_entries, list):
            raise ValueError(f"metadata frame {frame_index} entries must be a list: {source_path}")
        for entry_index, entry in enumerate(raw_entries, start=1):
            if not isinstance(entry, dict):
                raise ValueError(f"metadata frame {frame_index} entry {entry_index} must be an object: {source_path}")
            png_value = entry.get("png")
            if not png_value:
                continue
            png_path = Path(png_value).expanduser()
            if not png_path.is_absolute():
                png_path = source_path.parent / png_path
            normalized = normalize_path(png_path)
            normalized_text = str(normalized)
            if normalized_text in seen:
                continue
            seen.add(normalized_text)
            dependencies.append(normalized)

    return tuple(sorted(dependencies, key=lambda item: str(item)))


def source_dependency_paths(source_path: Path) -> tuple[Path, ...]:
    resolved = normalize_path(source_path)
    if resolved.suffix.lower() != ".json":
        return (resolved,)
    return (resolved, *_json_dependency_paths(resolved))


def source_dependency_token(source_path: Path) -> str:
    digest = hashlib.sha256()
    for dependency in source_dependency_paths(source_path):
        resolved_text, token = file_identity(dependency)
        digest.update(resolved_text.encode("utf-8"))
        digest.update(b"\0")
        digest.update(token.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def source_cache_identity(source_path: Path) -> tuple[str, str]:
    resolved = normalize_path(source_path)
    return str(resolved), source_dependency_token(resolved)


def cache_artifact_dir(base: Path, source_path: Path) -> Path:
    resolved = normalize_path(source_path)
    token = source_dependency_token(resolved)[:10]
    return normalize_path(base) / f"{sanitize_path_component(resolved.stem)}-{token}"


def touch_cache_path(path: Path) -> None:
    if not path.exists():
        return
    try:
        os.utime(path, None)
    except OSError:
        pass


def _remove_cache_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink(missing_ok=True)


def prune_cache_dir(cache_dir: Path, max_entries: int) -> None:
    if max_entries < 1:
        return

    resolved_dir = normalize_path(cache_dir)
    if not resolved_dir.exists():
        return

    entries = list(resolved_dir.iterdir())
    if len(entries) <= max_entries:
        return

    entries.sort(key=lambda item: (item.stat().st_mtime_ns, item.name))
    for stale_path in entries[: len(entries) - max_entries]:
        _remove_cache_path(stale_path)


class BoundedCache(Generic[K, V]):
    def __init__(self, max_entries: int):
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self.max_entries = max_entries
        self._entries: OrderedDict[K, V] = OrderedDict()
        self._lock = threading.RLock()

    def __contains__(self, key: K) -> bool:
        with self._lock:
            return key in self._entries

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def get(self, key: K) -> V | None:
        with self._lock:
            if key not in self._entries:
                return None
            self._entries.move_to_end(key)
            return self._entries[key]

    def set(self, key: K, value: V) -> V:
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
            self._entries[key] = value
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def discard_where(self, predicate: Callable[[K, V], bool]) -> int:
        with self._lock:
            keys_to_drop = [key for key, value in self._entries.items() if predicate(key, value)]
            for key in keys_to_drop:
                self._entries.pop(key, None)
            return len(keys_to_drop)
