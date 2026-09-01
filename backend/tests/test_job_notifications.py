# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from unittest.mock import MagicMock

from katalon.workers import batch_tasks, import_tasks


def test_import_notification_queues_only_for_a_known_user(monkeypatch) -> None:
    enqueue = MagicMock()
    monkeypatch.setattr(import_tasks, "enqueue", enqueue)
    result = {"created": 2, "updated": 1, "skipped": 0, "errors": [], "warnings": []}

    import_tasks._queue_import_notification("user-id", "object", result)
    import_tasks._queue_import_notification(None, "object", result)

    enqueue.assert_called_once()
    assert enqueue.call_args.args[:3] == (
        import_tasks.send_user_email,
        "user-id",
        "Katalon: Import abgeschlossen",
    )
    assert "Neu: 2" in enqueue.call_args.args[3]


def test_batch_notification_does_not_expose_worker_error(monkeypatch) -> None:
    enqueue = MagicMock()
    monkeypatch.setattr(batch_tasks, "enqueue", enqueue)

    batch_tasks._queue_batch_notification("user-id", "object", {"affected": 0, "errors": ["db secret"]})

    assert enqueue.call_args.args[:3] == (
        batch_tasks.send_user_email,
        "user-id",
        "Katalon: Batch-Bearbeitung fehlgeschlagen",
    )
    assert "db secret" not in enqueue.call_args.args[3]
