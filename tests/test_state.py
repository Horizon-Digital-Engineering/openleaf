from __future__ import annotations

import threading

from openleaf.state import StateStore


def test_state_store_update_changes_fields() -> None:
    store = StateStore()
    store.update(soc_true=55.5)
    assert store.snapshot()["soc_true"] == 55.5


def test_snapshot_returns_copy() -> None:
    store = StateStore()
    snapshot = store.snapshot()
    snapshot["soc_true"] = 99.0
    assert store.snapshot()["soc_true"] == 0.0


def test_state_store_thread_safety_smoke() -> None:
    store = StateStore()

    def writer() -> None:
        for i in range(200):
            store.update(soc_true=float(i), soh=float(i))

    def reader() -> None:
        for _ in range(200):
            store.snapshot()

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert store.snapshot()["soc_true"] >= 0.0
