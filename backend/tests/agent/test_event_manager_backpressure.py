import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.agent.event_manager import EventManager


@pytest.mark.asyncio
async def test_thinking_token_metadata_does_not_store_accumulated_text():
    manager = EventManager(queue_max_size=10)
    manager.create_queue("task-1")

    await manager.add_event(
        task_id="task-1",
        event_type="thinking_token",
        sequence=1,
        metadata={"token": "abc", "accumulated": "abc" * 1000},
    )

    event = await manager._event_queues["task-1"].get()

    assert event["metadata"] == {"token": "abc"}


@pytest.mark.asyncio
async def test_queue_full_drops_low_priority_event_to_keep_terminal_event():
    manager = EventManager(queue_max_size=2)
    manager.create_queue("task-1")

    await manager.add_event(
        task_id="task-1",
        event_type="thinking_token",
        sequence=1,
        metadata={"token": "a"},
    )
    await manager.add_event(
        task_id="task-1",
        event_type="thinking_token",
        sequence=2,
        metadata={"token": "b"},
    )
    await manager.add_event(
        task_id="task-1",
        event_type="task_complete",
        sequence=3,
        message="done",
    )

    queued = []
    queue = manager._event_queues["task-1"]
    while not queue.empty():
        queued.append(queue.get_nowait())

    assert [event["event_type"] for event in queued] == ["thinking_token", "task_complete"]


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["runtime_done", "llm_complete", "dispatch_complete", "phase_complete", "phase_failed", "error", "task_complete", "runtime_error"])
async def test_runtime_token_flood_preserves_completion_events(event_type):
    manager = EventManager(queue_max_size=3)
    queue = manager.create_queue("task-1")
    for sequence in range(100):
        await manager.add_event(task_id="task-1", event_type="runtime_token", sequence=sequence)
    assert queue.qsize() == 3
    await manager.add_event(task_id="task-1", event_type=event_type, sequence=100)
    events = [queue.get_nowait() for _ in range(queue.qsize())]
    assert [event["sequence"] for event in events] == [1, 2, 100]
    for _ in events:
        queue.task_done()
    assert queue._unfinished_tasks == 0


@pytest.mark.asyncio
async def test_critical_events_evict_tokens_before_ordinary_events_and_keep_order():
    manager = EventManager(queue_max_size=3)
    queue = manager.create_queue("task-1")
    for sequence, event_type in enumerate(["info", "error", "runtime_token", "runtime_done", "phase_failed", "task_complete"]):
        await manager.add_event(task_id="task-1", event_type=event_type, sequence=sequence)
        if sequence == 3:
            assert [event["event_type"] for event in queue._queue] == ["info", "error", "runtime_done"]
    assert [event["event_type"] for event in queue._queue] == ["error", "runtime_done", "phase_failed", "task_complete"]
    await manager.add_event(task_id="task-1", event_type="runtime_token", sequence=6)
    assert queue.qsize() == 4  # Only critical events may exceed the traffic limit.
    while not queue.empty():
        queue.get_nowait()
        queue.task_done()
    assert queue._unfinished_tasks == 0
