#!/usr/bin/env python3
"""Background task helpers for Tk-based GUI work."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from queue import Empty, SimpleQueue
from typing import Generic, TypeVar

import tkinter as tk


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class TaskToken:
    family: str
    generation: int


@dataclass(slots=True)
class _TaskDelivery(Generic[T]):
    token: TaskToken
    callback: Callable[[TaskToken, T], None] | None
    payload: T


class RequestTracker:
    """Tracks UI request generations so stale worker results can be ignored."""

    def __init__(self) -> None:
        self._generations: dict[str, int] = {}

    def next(self, family: str) -> TaskToken:
        generation = self._generations.get(family, 0) + 1
        self._generations[family] = generation
        return TaskToken(family=family, generation=generation)

    def invalidate(self, family: str) -> int:
        return self.next(family).generation

    def current(self, family: str) -> int:
        return self._generations.get(family, 0)

    def is_current(self, token: TaskToken) -> bool:
        return self.current(token.family) == token.generation


class GuiTaskRunner:
    """Runs worker tasks off the Tk thread and delivers results back on it."""

    def __init__(self, root: tk.Misc, *, max_workers: int = 4, poll_interval_ms: int = 40) -> None:
        self.root = root
        self.poll_interval_ms = max(10, int(poll_interval_ms))
        self._queue: SimpleQueue[_TaskDelivery[object]] = SimpleQueue()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="cursorforge-gui")
        self._closed = False
        self._after_id: str | None = None
        self._schedule_drain()

    def submit(
        self,
        token: TaskToken,
        work: Callable[[], T],
        *,
        on_success: Callable[[TaskToken, T], None] | None,
        on_error: Callable[[TaskToken, BaseException], None] | None = None,
    ) -> None:
        if self._closed:
            return

        def run() -> None:
            try:
                result = work()
            except BaseException as exc:  # noqa: BLE001
                self._queue.put(_TaskDelivery(token=token, callback=on_error, payload=exc))
                return
            self._queue.put(_TaskDelivery(token=token, callback=on_success, payload=result))

        self._executor.submit(run)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _schedule_drain(self) -> None:
        if self._closed:
            return
        try:
            self._after_id = self.root.after(self.poll_interval_ms, self._drain)
        except tk.TclError:
            self.close()

    def _drain(self) -> None:
        self._after_id = None
        if self._closed:
            return
        while True:
            try:
                delivery = self._queue.get_nowait()
            except Empty:
                break
            callback = delivery.callback
            if callback is None:
                continue
            try:
                callback(delivery.token, delivery.payload)
            except tk.TclError:
                self.close()
                return
        self._schedule_drain()
