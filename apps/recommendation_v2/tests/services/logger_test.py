import asyncio
import logging

import pytest

from config import settings
from services.logger import StructuredLogger
from services.logger import call_id_context


# The number of concurrent "requests" to simulate. Large enough that, if state ever
# leaked, the interleaving would almost certainly surface a wrong value.
CONCURRENT_REQUEST_COUNT = 50


@pytest.mark.asyncio
async def test_call_id_context_is_isolated_across_concurrent_tasks():
    """
    Guards the core anti data sharing guarantee of the app in an async context.

    Each concurrent request must have its own call_id_context that never leaks to other requests.
    """

    async def handle_request(call_id: str) -> str:
        call_id_context.set(call_id)
        # Yield to the event loop so all other tasks run between the set and the read.
        await asyncio.sleep(0)
        return call_id_context.get()

    expected_call_ids = [f"call-{i}" for i in range(CONCURRENT_REQUEST_COUNT)]
    observed_call_ids = await asyncio.gather(*(handle_request(cid) for cid in expected_call_ids))

    # Each task observed only its own call_id — no value leaked across tasks.
    assert observed_call_ids == expected_call_ids


@pytest.mark.asyncio
async def test_structured_logger_tags_each_concurrent_log_with_its_own_call_id(monkeypatch):
    """
    Same isolation guarantee, but verified through the real `StructuredLogger`
    rather than the raw ContextVar.

    This proves the logger reads the call_id of the *currently running* request at
    the moment it logs — not a value captured once at import or shared between
    requests. Each concurrent task logs a message carrying its own call_id both in
    the context and as an echo inside `extra`; the two must always match.
    """
    # Force the non-local code path so `_format_log` returns a structured dict
    monkeypatch.setattr(settings, "IS_LOCAL", False)

    captured_payloads: list[dict] = []

    class _RecordingBaseLogger(logging.Logger):
        """Stand-in for the stdlib logger that just records what it was handed."""

        def __init__(self) -> None:
            super().__init__(name="recording")

        def info(self, payload: dict, *args, **kwargs) -> None:  # type: ignore[override]
            captured_payloads.append(payload)

    structured_logger = StructuredLogger(_RecordingBaseLogger())

    async def handle_request(call_id: str) -> None:
        call_id_context.set(call_id)
        await asyncio.sleep(0)
        structured_logger.info("processing request", extra={"call_id_echo": call_id})

    expected_call_ids = [f"call-{i}" for i in range(CONCURRENT_REQUEST_COUNT)]
    await asyncio.gather(*(handle_request(cid) for cid in expected_call_ids))

    assert len(captured_payloads) == CONCURRENT_REQUEST_COUNT
    # The call_id injected by the logger must match the one the task actually owned.
    for payload in captured_payloads:
        assert payload["call_id"] == payload["extra"]["call_id_echo"]
