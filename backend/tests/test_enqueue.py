"""Broker-tolerant Celery enqueue helpers (#274)."""
import pytest
from fastapi import HTTPException

from katalon.workers.enqueue import enqueue, enqueue_or_503


class _OkTask:
    name = "ok"

    def delay(self, *args, **kwargs):
        class _R:
            id = "tid-1"
        return _R()


class _BrokenTask:
    name = "broken"

    def delay(self, *args, **kwargs):
        raise ConnectionError("broker down")


def test_enqueue_returns_id_on_success() -> None:
    assert enqueue(_OkTask()) == "tid-1"


def test_enqueue_swallows_broker_error() -> None:
    # A broker outage must not break the request path — returns None, no raise.
    assert enqueue(_BrokenTask()) is None


def test_enqueue_or_503_returns_id() -> None:
    assert enqueue_or_503(_OkTask()) == "tid-1"


def test_enqueue_or_503_raises_503_on_broker_error() -> None:
    with pytest.raises(HTTPException) as exc:
        enqueue_or_503(_BrokenTask())
    assert exc.value.status_code == 503
