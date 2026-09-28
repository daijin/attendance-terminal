from datetime import datetime, timezone

from attendance_terminal.store import PunchStore


def test_store_queue_and_ack(tmp_path):
    store = PunchStore(str(tmp_path / "punches.db"), "pi-01")
    punch = store.add("a1b2", datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc))

    assert punch.uid == "A1B2"
    assert store.count_pending() == 1
    assert store.pending(10) == [punch]

    store.mark_uploaded([punch.event_id])
    assert store.count_pending() == 0
    assert store.pending(10) == []


def test_batch_limit(tmp_path):
    store = PunchStore(str(tmp_path / "punches.db"), "pi-01")
    store.add("01")
    store.add("02")
    assert len(store.pending(1)) == 1
