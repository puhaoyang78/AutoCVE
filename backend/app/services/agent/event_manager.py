"""
Agent 事件管理器
负责事件的创建、存储和推送
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

LOW_PRIORITY_EVENT_TYPES = {
    "thinking_token", "runtime_token", "heartbeat", "debug", "progress", "runtime_progress", "runtime_debug",
}
CRITICAL_EVENT_TYPES = {
    "runtime_done",
    "runtime_error",
    "llm_complete",
    "dispatch_complete",
    "phase_complete",
    "phase_failed",
    "error",
    "task_complete",
    "task_error",
    "task_cancel",
    "tool_result",
    "finding_new",
    "finding_verified",
}


@dataclass
class AgentEventData:
    """Agent 事件数据"""
    event_type: str
    phase: str | None = None
    message: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: dict[str, Any] | None = None
    tool_duration_ms: int | None = None
    finding_id: str | None = None
    tokens_used: int = 0
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.tokens_used or not isinstance(self.metadata, dict):
            return
        try:
            self.tokens_used = int(self.metadata.get("tokens_used") or 0)
        except (TypeError, ValueError):
            self.tokens_used = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "phase": self.phase,
            "message": self.message,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output,
            "tool_duration_ms": self.tool_duration_ms,
            "finding_id": self.finding_id,
            "tokens_used": self.tokens_used,
            "metadata": self.metadata,
        }


class AgentEventEmitter:
    """
    Agent 事件发射器
    用于在 Agent 执行过程中发射事件
    """

    def __init__(self, task_id: str, event_manager: 'EventManager'):
        self.task_id = task_id
        self.event_manager = event_manager
        self._sequence = 0
        self._current_phase = None

    async def emit(self, event_data: AgentEventData):
        """发射事件"""
        self._sequence += 1
        event_data.phase = event_data.phase or self._current_phase

        await self.event_manager.add_event(
            task_id=self.task_id,
            sequence=self._sequence,
            **event_data.to_dict()
        )

    async def emit_phase_start(self, phase: str, message: str | None = None):
        """发射阶段开始事件"""
        self._current_phase = phase
        await self.emit(AgentEventData(
            event_type="phase_start",
            phase=phase,
            message=message or f"开始 {phase} 阶段",
        ))

    async def emit_phase_complete(self, phase: str, message: str | None = None):
        """发射阶段完成事件"""
        await self.emit(AgentEventData(
            event_type="phase_complete",
            phase=phase,
            message=message or f"{phase} 阶段完成",
        ))

    async def emit_thinking(self, message: str, metadata: dict | None = None):
        """发射思考事件"""
        await self.emit(AgentEventData(
            event_type="thinking",
            message=message,
            metadata=metadata,
        ))

    async def emit_llm_thought(self, thought: str, iteration: int = 0):
        """发射 LLM 思考内容事件 - 核心！展示 LLM 在想什么"""
        display = thought[:500] + "..." if len(thought) > 500 else thought
        await self.emit(AgentEventData(
            event_type="llm_thought",
            message=f"💭 LLM 思考:\n{display}",
            metadata={"thought": thought, "iteration": iteration},
        ))

    async def emit_llm_decision(self, decision: str, reason: str = ""):
        """发射 LLM 决策事件"""
        await self.emit(AgentEventData(
            event_type="llm_decision",
            message=f"💡 LLM 决策: {decision}" + (f" ({reason})" if reason else ""),
            metadata={"decision": decision, "reason": reason},
        ))

    async def emit_llm_action(self, action: str, action_input: dict):
        """发射 LLM 动作事件"""
        input_str = json.dumps(action_input, ensure_ascii=False)[:200]
        await self.emit(AgentEventData(
            event_type="llm_action",
            message=f"⚡ LLM 动作: {action}\n   参数: {input_str}",
            metadata={"action": action, "action_input": action_input},
        ))

    async def emit_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        message: str | None = None,
    ):
        """发射工具调用事件"""
        await self.emit(AgentEventData(
            event_type="tool_call",
            tool_name=tool_name,
            tool_input=tool_input,
            message=message or f"调用工具: {tool_name}",
        ))

    async def emit_tool_result(
        self,
        tool_name: str,
        tool_output: Any,
        duration_ms: int,
        message: str | None = None,
    ):
        """发射工具结果事件"""
        # 处理输出，确保可序列化
        if hasattr(tool_output, 'to_dict'):
            output_data = tool_output.to_dict()
        elif isinstance(tool_output, str):
            output_data = {"result": tool_output[:2000]}  # 截断长输出
        else:
            output_data = {"result": str(tool_output)[:2000]}

        await self.emit(AgentEventData(
            event_type="tool_result",
            tool_name=tool_name,
            tool_output=output_data,
            tool_duration_ms=duration_ms,
            message=message or f"工具 {tool_name} 执行完成 ({duration_ms}ms)",
        ))

    async def emit_finding(
        self,
        finding_id: str,
        title: str,
        severity: str,
        vulnerability_type: str,
        is_verified: bool = False,
    ):
        """发射漏洞发现事件"""
        event_type = "finding_verified" if is_verified else "finding_new"
        await self.emit(AgentEventData(
            event_type=event_type,
            finding_id=finding_id,
            message=f"{'✅ 已验证' if is_verified else '🔍 新发现'}: [{severity.upper()}] {title}",
            metadata={
                "id": finding_id,  # 🔥 添加 id 字段供前端使用
                "title": title,
                "severity": severity,
                "vulnerability_type": vulnerability_type,
                "is_verified": is_verified,
            },
        ))

    async def emit_info(self, message: str, metadata: dict | None = None):
        """发射信息事件"""
        await self.emit(AgentEventData(
            event_type="info",
            message=message,
            metadata=metadata,
        ))

    async def emit_warning(self, message: str, metadata: dict | None = None):
        """发射警告事件"""
        await self.emit(AgentEventData(
            event_type="warning",
            message=message,
            metadata=metadata,
        ))

    async def emit_error(self, message: str, metadata: dict | None = None):
        """发射错误事件"""
        await self.emit(AgentEventData(
            event_type="error",
            message=message,
            metadata=metadata,
        ))

    async def emit_progress(
        self,
        current: int,
        total: int,
        message: str | None = None,
    ):
        """发射进度事件"""
        percentage = (current / total * 100) if total > 0 else 0
        await self.emit(AgentEventData(
            event_type="progress",
            message=message or f"进度: {current}/{total} ({percentage:.1f}%)",
            metadata={
                "current": current,
                "total": total,
                "percentage": percentage,
            },
        ))

    async def emit_task_complete(
        self,
        findings_count: int,
        duration_ms: int,
        message: str | None = None,
    ):
        """发射任务完成事件"""
        await self.emit(AgentEventData(
            event_type="task_complete",
            message=message or f"✅ 审计完成！发现 {findings_count} 个漏洞，耗时 {duration_ms/1000:.1f}秒",
            metadata={
                "findings_count": findings_count,
                "duration_ms": duration_ms,
            },
        ))

    async def emit_task_error(self, error: str, message: str | None = None):
        """发射任务错误事件"""
        await self.emit(AgentEventData(
            event_type="task_error",
            message=message or f"❌ 任务失败: {error}",
            metadata={"error": error},
        ))

    async def emit_task_cancelled(self, message: str | None = None):
        """发射任务取消事件"""
        await self.emit(AgentEventData(
            event_type="task_cancel",
            message=message or "⚠️ 任务已取消",
        ))


class EventManager:
    """
    事件管理器
    负责事件的存储和检索
    """

    def __init__(self, db_session_factory=None, queue_max_size: int | None = None, event_stream=None):
        self.db_session_factory = db_session_factory
        self.queue_max_size = max(1, int(queue_max_size or settings.AGENT_EVENT_QUEUE_MAX_SIZE))
        self.event_stream = event_stream
        self._event_queues: dict[str, asyncio.Queue] = {}
        self._event_callbacks: dict[str, list[Callable]] = {}

    async def add_event(
        self,
        task_id: str,
        event_type: str,
        sequence: int = 0,
        phase: str | None = None,
        message: str | None = None,
        tool_name: str | None = None,
        tool_input: dict | None = None,
        tool_output: dict | None = None,
        tool_duration_ms: int | None = None,
        finding_id: str | None = None,
        tokens_used: int = 0,
        metadata: dict | None = None,
    ):
        """添加事件"""
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC)
        metadata = self._normalize_event_metadata(event_type, metadata)
        if not tokens_used and isinstance(metadata, dict):
            try:
                tokens_used = int(metadata.get("tokens_used") or 0)
            except (TypeError, ValueError):
                tokens_used = 0

        event_data = {
            "id": event_id,
            "task_id": task_id,
            "event_type": event_type,
            "sequence": sequence,
            "phase": phase,
            "message": message,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "tool_duration_ms": tool_duration_ms,
            "finding_id": finding_id,
            "tokens_used": tokens_used,
            "metadata": metadata,
            "timestamp": timestamp.isoformat(),
        }

        # 保存到数据库（跳过高频事件如 thinking_token）
        skip_db_events = {"thinking_token", "runtime_token"}
        if self.db_session_factory and event_type not in skip_db_events:
            try:
                await self._save_event_to_db(event_data)
            except Exception as e:
                logger.error(f"Failed to save event to database: {e}")

        if self.event_stream:
            try:
                await self.event_stream.publish_event(task_id, event_data)
            except Exception as e:
                logger.warning(f"Failed to publish event stream for task {task_id}: {e}")

        # 推送到队列（非阻塞）
        if task_id in self._event_queues:
            queue = self._event_queues[task_id]
            if self._enqueue_event(queue, event_data):
                # 🔥 DEBUG: 记录重要事件被添加到队列
                if event_type in ["thinking_start", "thinking_end", "dispatch", "task_complete", "task_error", "tool_call", "tool_result", "llm_action"]:
                    logger.info(f"[EventQueue] Added {event_type} to queue for task {task_id}, queue size: {queue.qsize()}")
                elif event_type == "thinking_token":
                    # 每10个token记录一次
                    if sequence % 10 == 0:
                        logger.debug(f"[EventQueue] Added thinking_token #{sequence} to queue, size: {queue.qsize()}")
            elif event_type in LOW_PRIORITY_EVENT_TYPES:
                logger.debug(f"Event queue full for task {task_id}, dropping event: {event_type}")
            else:
                logger.warning(f"Event queue full for task {task_id}, dropping event: {event_type}")

        # 调用回调
        if task_id in self._event_callbacks:
            for callback in self._event_callbacks[task_id]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event_data)
                    else:
                        callback(event_data)
                except Exception as e:
                    logger.error(f"Event callback error: {e}")

        return event_id

    def _normalize_event_metadata(self, event_type: str, metadata: dict | None) -> dict | None:
        if not isinstance(metadata, dict):
            return metadata
        if event_type in {"thinking_token", "runtime_token"}:
            normalized = dict(metadata)
            normalized.pop("accumulated", None)
            return normalized
        return metadata

    def _enqueue_event(self, queue: asyncio.Queue, event_data: dict[str, Any]) -> bool:
        # Admission is bounded for ordinary traffic. Completion/error events
        # must remain deliverable even when no SSE consumer is connected.
        dropped_event = False
        if queue.qsize() >= self.queue_max_size:
            if event_data.get("event_type") not in CRITICAL_EVENT_TYPES:
                return False
            retained = []
            while not queue.empty():
                retained.append(queue.get_nowait())
            drop_index = next(
                (i for i, event in enumerate(retained) if event.get("event_type") in LOW_PRIORITY_EVENT_TYPES),
                None,
            )
            if drop_index is None:
                drop_index = next(
                    (i for i, event in enumerate(retained) if event.get("event_type") not in CRITICAL_EVENT_TYPES),
                    None,
                )
            if drop_index is not None:
                retained.pop(drop_index)
                dropped_event = True
            # An all-critical backlog cannot be bounded, lossless and
            # non-blocking at once. Retain it; never admit more ordinary traffic.
            for event in retained:
                queue.put_nowait(event)
                queue.task_done()
        queue.put_nowait(event_data)
        if dropped_event:
            queue.task_done()
        return True

    async def _save_event_to_db(self, event_data: dict):
        """保存事件到数据库"""
        from app.models.agent_task import AgentEvent

        # 🔥 清理无效的 UTF-8 字符（如二进制内容）
        def sanitize_string(s):
            """清理字符串中的无效 UTF-8 字符"""
            if s is None:
                return None
            if not isinstance(s, str):
                s = str(s)
            # 移除 NULL 字节和其他不可打印的控制字符（保留换行和制表符）
            return ''.join(
                char for char in s
                if char in '\n\r\t' or (ord(char) >= 32 and ord(char) != 127)
            )

        def sanitize_dict(d):
            """递归清理字典中的字符串值"""
            if d is None:
                return None
            if isinstance(d, dict):
                return {k: sanitize_dict(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [sanitize_dict(item) for item in d]
            elif isinstance(d, str):
                return sanitize_string(d)
            return d

        async with self.db_session_factory() as db:
            event = AgentEvent(
                id=event_data["id"],
                task_id=event_data["task_id"],
                event_type=event_data["event_type"],
                sequence=event_data["sequence"],
                phase=event_data["phase"],
                message=sanitize_string(event_data["message"]),  # 🔥 清理消息
                tool_name=event_data["tool_name"],
                tool_input=sanitize_dict(event_data["tool_input"]),  # 🔥 清理工具输入
                tool_output=sanitize_dict(event_data["tool_output"]),  # 🔥 清理工具输出
                tool_duration_ms=event_data["tool_duration_ms"],
                finding_id=event_data["finding_id"],
                tokens_used=event_data["tokens_used"],
                event_metadata=sanitize_dict(event_data["metadata"]),  # 🔥 清理元数据
            )
            db.add(event)
            await db.commit()

    def create_queue(self, task_id: str) -> asyncio.Queue:
        """创建或获取事件队列"""
        if task_id not in self._event_queues:
            # _enqueue_event enforces the traffic limit while retaining critical events.
            self._event_queues[task_id] = asyncio.Queue()
        return self._event_queues[task_id]

    def remove_queue(self, task_id: str):
        """移除事件队列"""
        if task_id in self._event_queues:
            del self._event_queues[task_id]

    def add_callback(self, task_id: str, callback: Callable):
        """添加事件回调"""
        if task_id not in self._event_callbacks:
            self._event_callbacks[task_id] = []
        self._event_callbacks[task_id].append(callback)

    def remove_callback(self, task_id: str, callback: Callable):
        """移除事件回调"""
        if task_id in self._event_callbacks:
            self._event_callbacks[task_id].remove(callback)

    async def get_events(
        self,
        task_id: str,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        """获取事件列表"""
        if not self.db_session_factory:
            return []

        from sqlalchemy.future import select

        from app.models.agent_task import AgentEvent

        async with self.db_session_factory() as db:
            result = await db.execute(
                select(AgentEvent)
                .where(AgentEvent.task_id == task_id)
                .where(AgentEvent.sequence > after_sequence)
                .order_by(AgentEvent.sequence)
                .limit(limit)
            )
            events = result.scalars().all()
            return [event.to_sse_dict() for event in events]

    async def stream_events(
        self,
        task_id: str,
        after_sequence: int = 0,
    ) -> AsyncGenerator[dict, None]:
        """流式获取事件

        🔥 重要: 此方法会先排空队列中已缓存的事件（在 SSE 连接前产生的），
        然后继续实时推送新事件。
        只返回序列号 > after_sequence 的事件。
        """
        logger.info(f"[StreamEvents] Task {task_id}: Starting stream with after_sequence={after_sequence}")

        # 获取现有队列（由 AgentRunner 在初始化时创建）
        queue = self._event_queues.get(task_id)
        if not queue:
            # 如果队列不存在，创建一个新的（回退逻辑）
            queue = self.create_queue(task_id)
            logger.warning(f"Queue not found for task {task_id}, created new one")

        # 🔥 CRITICAL FIX: 记录当前队列大小，只消耗这些已存在的事件
        # 之前的 bug: while not queue.empty() 会永远循环，因为 LLM 持续添加事件
        initial_queue_size = queue.qsize()
        logger.info(f"[StreamEvents] Task {task_id}: Draining {initial_queue_size} buffered events...")

        # 🔥 先排空队列中已缓存的事件（只消耗连接时已存在的事件数量）
        buffered_count = 0
        skipped_count = 0
        max_drain = initial_queue_size  # 只消耗这么多事件，避免无限循环

        for _ in range(max_drain):
            try:
                buffered_event = queue.get_nowait()

                # 🔥 过滤掉序列号 <= after_sequence 的事件
                event_sequence = buffered_event.get("sequence", 0)
                if event_sequence <= after_sequence:
                    skipped_count += 1
                    continue

                buffered_count += 1
                yield buffered_event

                # 🔥 取消人为延迟，防止队列堆积
                event_type = buffered_event.get("event_type")
                # if event_type == "thinking_token":
                #     await asyncio.sleep(0.005)
                # 其他事件不加延迟，快速发送

                # 检查是否是结束事件
                if event_type in ["task_complete", "task_error", "task_cancel"]:
                    logger.info(f"[StreamEvents] Task {task_id} already completed, sent {buffered_count} buffered events (skipped {skipped_count})")
                    return
            except asyncio.QueueEmpty:
                break

        if buffered_count > 0 or skipped_count > 0:
            logger.info(f"[StreamEvents] Task {task_id}: Drained {buffered_count} buffered events, skipped {skipped_count}")

        # 🔥 DEBUG: 记录进入实时循环
        logger.info(f"[StreamEvents] Task {task_id}: Entering real-time loop, queue size: {queue.qsize()}")

        # 然后实时推送新事件
        try:
            while True:
                try:
                    logger.debug(f"[StreamEvents] Task {task_id}: Waiting for next event from queue...")
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    logger.debug(f"[StreamEvents] Task {task_id}: Got event from queue: {event.get('event_type')}")

                    # 🔥 过滤掉序列号 <= after_sequence 的事件
                    event_sequence = event.get("sequence", 0)
                    if event_sequence <= after_sequence:
                        logger.debug(f"[StreamEvents] Task {task_id}: Skipping event seq={event_sequence} (after_sequence={after_sequence})")
                        continue

                    # 🔥 DEBUG: 记录重要事件被发送
                    event_type = event.get("event_type")
                    if event_type in ["thinking_start", "thinking_end", "dispatch", "task_complete", "task_error", "tool_call", "tool_result", "llm_action"]:
                        logger.info(f"[StreamEvents] Yielding {event_type} (seq={event_sequence}) for task {task_id}")

                    yield event

                    # 🔥 取消人为延迟，防止队列堆积
                    # if event_type == "thinking_token":
                    #     await asyncio.sleep(0.01)

                    # 检查是否是结束事件
                    if event.get("event_type") in ["task_complete", "task_error", "task_cancel"]:
                        break

                except TimeoutError:
                    # 发送心跳
                    yield {"event_type": "heartbeat", "timestamp": datetime.now(UTC).isoformat()}

        except GeneratorExit:
            # SSE 连接断开
            logger.debug(f"SSE stream closed for task {task_id}")
        # 🔥 不要移除队列，让 AgentRunner 管理队列的生命周期

    def create_emitter(self, task_id: str) -> AgentEventEmitter:
        """创建事件发射器"""
        return AgentEventEmitter(task_id, self)

    async def close(self):
        """关闭事件管理器，清理资源"""
        # 清理所有队列
        for task_id in list(self._event_queues.keys()):
            self.remove_queue(task_id)

        # 清理所有回调
        self._event_callbacks.clear()

        if self.event_stream and hasattr(self.event_stream, "close"):
            await self.event_stream.close()

        logger.debug("EventManager closed")

